"""Async-specific tests for ComplianceAgent (ADR-0021).

Never touches the network — the underlying HTTP client is swapped for a
fake that records call timestamps, so the rate-limit/lock behavior can be
measured deterministically instead of trusted on faith.
"""

import asyncio
import json
import time

import pytest

from compliance.agent import ComplianceAgent, ComplianceError


class _FakeHTTPResponse:
    def __init__(self, status_code=200, text="", json_payload=None, url=""):
        self.status_code = status_code
        self.text = text
        self._json_payload = json_payload if json_payload is not None else {}
        self.url = url

    def json(self):
        return self._json_payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"fake HTTP {self.status_code}")


class _FakeHTTPClient:
    """Stands in for httpx.AsyncClient. Records every call with a timestamp
    so tests can assert on real elapsed spacing between calls, not just on
    call order."""

    def __init__(self, robots_txt_status=404, robots_txt_text="", robots_txt_status_sequence=None):
        self.calls = []
        self.robots_txt_status = robots_txt_status
        self.robots_txt_text = robots_txt_text
        # Session 22: lets a test simulate successive robots.txt checks
        # returning *different* statuses — e.g. [403, 404] for "blocked
        # once, then allowed on the immediate re-check" — one value
        # consumed per robots.txt call, falling back to robots_txt_status
        # once exhausted. 403/401 = disallowed, anything else (404 here)
        # = allowed (no robots.txt published), matching _check_robots_live's
        # own real status-code handling.
        self._robots_txt_status_sequence = list(robots_txt_status_sequence) if robots_txt_status_sequence else None

    async def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, time.monotonic()))
        if url.endswith("/robots.txt"):
            if self._robots_txt_status_sequence:
                status = self._robots_txt_status_sequence.pop(0)
            else:
                status = self.robots_txt_status
            text = self.robots_txt_text if status not in (401, 403) else ""
            return _FakeHTTPResponse(status_code=status, text=text, url=url)
        return _FakeHTTPResponse(status_code=200, json_payload={"jobs": []}, url=url)

    async def aclose(self):
        pass

    def non_robots_call_times(self):
        return [t for url, t in self.calls if not url.endswith("/robots.txt")]

    def robots_call_count(self):
        return sum(1 for url, _ in self.calls if url.endswith("/robots.txt"))


def _agent_with_fake_client(tmp_path, min_delay_seconds=0.3, blocked_recheck_delay_seconds=0, **kwargs):
    # blocked_recheck_delay_seconds defaults to 0 here (Session 22's real
    # default is a genuine 5s) so tests that happen to hit a blocked
    # domain don't pay a real 5-second sleep for no reason — the
    # double-check *timing* itself gets its own dedicated tests below.
    agent = ComplianceAgent(
        min_delay_seconds=min_delay_seconds,
        robots_cache_path=tmp_path / "robots_cache.json",
        blocked_recheck_delay_seconds=blocked_recheck_delay_seconds,
        **kwargs,
    )
    agent._client = _FakeHTTPClient()
    return agent


def test_lock_for_domain_is_shared_per_domain_and_distinct_across_domains(tmp_path):
    agent = _agent_with_fake_client(tmp_path)
    lock_a1 = agent._lock_for_domain("a.example")
    lock_a2 = agent._lock_for_domain("a.example")
    lock_b = agent._lock_for_domain("b.example")

    assert lock_a1 is lock_a2
    assert lock_a1 is not lock_b


async def test_same_domain_calls_are_spaced_by_min_delay(tmp_path):
    # This is the exact race Elad flagged: without the per-domain lock
    # spanning the rate-limit wait, two concurrent same-domain calls could
    # both see "no wait needed" and fire together. Measure real elapsed
    # time between the two actual fetches (excluding the one-time robots.txt
    # check) to prove the fix, not just trust the code.
    min_delay = 0.3
    agent = _agent_with_fake_client(tmp_path, min_delay_seconds=min_delay)

    await asyncio.gather(
        agent.fetch("https://same.example/a"),
        agent.fetch("https://same.example/b"),
    )

    fetch_times = sorted(agent._client.non_robots_call_times())
    assert len(fetch_times) == 2
    spacing = fetch_times[1] - fetch_times[0]
    assert spacing >= min_delay - 0.05, f"expected >= ~{min_delay}s spacing, got {spacing}s"
    # robots.txt for this brand-new domain should only ever be fetched once,
    # even though both concurrent calls needed a compliance decision for it.
    assert agent._client.robots_call_count() == 1


async def test_different_domains_do_not_block_each_other(tmp_path):
    # Use a deliberately large min_delay: if domains incorrectly serialized
    # on a shared lock, total elapsed would be forced above min_delay. Real
    # concurrent (non-blocking) domains should finish in a small fraction
    # of that, since the fake client has no real network latency.
    min_delay = 1.0
    agent = _agent_with_fake_client(tmp_path, min_delay_seconds=min_delay)

    start = time.monotonic()
    await asyncio.gather(
        agent.fetch("https://domain-a.example/x"),
        agent.fetch("https://domain-b.example/y"),
    )
    elapsed = time.monotonic() - start

    assert elapsed < min_delay / 2, f"expected fast concurrent fetch, took {elapsed}s"


async def test_robots_cache_is_persisted_and_reused_across_agent_instances(tmp_path):
    cache_path = tmp_path / "robots_cache.json"
    agent1 = ComplianceAgent(min_delay_seconds=0.0, robots_cache_path=cache_path)
    agent1._client = _FakeHTTPClient()

    await agent1.fetch("https://cached.example/first")
    assert agent1._client.robots_call_count() == 1

    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    assert "cached.example" in cache
    entry = cache["cached.example"]
    assert set(entry.keys()) == {"domain", "allowed", "checked_at"}
    assert entry["allowed"] is True

    # A second, independent agent instance pointed at the same cache file
    # should trust the persisted decision and never re-check robots.txt.
    agent2 = ComplianceAgent(min_delay_seconds=0.0, robots_cache_path=cache_path)
    agent2._client = _FakeHTTPClient()

    await agent2.fetch("https://cached.example/second")
    assert agent2._client.robots_call_count() == 0


async def test_robots_cache_entry_older_than_ttl_is_refreshed(tmp_path):
    cache_path = tmp_path / "robots_cache.json"
    stale_checked_at = time.time() - (8 * 24 * 60 * 60)  # 8 days ago, past the 7-day TTL
    cache_path.write_text(
        json.dumps({"stale.example": {"domain": "stale.example", "allowed": True, "checked_at": stale_checked_at}}),
        encoding="utf-8",
    )

    agent = ComplianceAgent(min_delay_seconds=0.0, robots_cache_path=cache_path)
    agent._client = _FakeHTTPClient()

    await agent.fetch("https://stale.example/path")

    assert agent._client.robots_call_count() == 1
    refreshed = json.loads(cache_path.read_text(encoding="utf-8"))["stale.example"]
    assert refreshed["checked_at"] > stale_checked_at


async def test_fetch_raises_compliance_error_when_robots_txt_disallows(tmp_path):
    agent = ComplianceAgent(
        min_delay_seconds=0.0, robots_cache_path=tmp_path / "robots_cache.json", blocked_recheck_delay_seconds=0
    )
    agent._client = _FakeHTTPClient(
        robots_txt_status=200,
        robots_txt_text="User-agent: *\nDisallow: /\n",
    )

    with pytest.raises(ComplianceError):
        await agent.fetch("https://blocked.example/jobs")


# --- gate() (Session 21) -----------------------------------------------
#
# fetch() is now just gate() wrapped around one httpx call — the tests
# above already prove fetch()'s end-to-end behavior is unchanged by that
# refactor. These tests exercise gate() directly, since ADR-0031's actual
# point is that a *different* fetch mechanism (Playwright, for discovery)
# can sit inside this same context manager and get identical compliance
# discipline without ever touching ComplianceAgent's internals itself.


async def test_gate_raises_compliance_error_before_the_caller_ever_runs(tmp_path):
    agent = _agent_with_fake_client(tmp_path)
    agent._client = _FakeHTTPClient(robots_txt_status=200, robots_txt_text="User-agent: *\nDisallow: /\n")

    entered = False
    with pytest.raises(ComplianceError):
        async with agent.gate("https://blocked.example/jobs"):
            entered = True

    assert entered is False


async def test_gate_records_timestamp_only_after_the_caller_finishes(tmp_path):
    agent = _agent_with_fake_client(tmp_path)

    assert "gated.example" not in agent._last_request_at
    async with agent.gate("https://gated.example/jobs"):
        # Not recorded yet — the point of recording after, not before, is
        # that spacing is measured between real completed work, matching
        # fetch()'s original ordering.
        assert "gated.example" not in agent._last_request_at

    assert "gated.example" in agent._last_request_at


async def test_gate_does_not_record_timestamp_if_the_caller_raises(tmp_path):
    agent = _agent_with_fake_client(tmp_path)

    with pytest.raises(RuntimeError):
        async with agent.gate("https://failing.example/jobs"):
            raise RuntimeError("caller's own fetch mechanism failed")

    assert "failing.example" not in agent._last_request_at


async def test_gate_enforces_the_same_per_domain_spacing_as_fetch(tmp_path):
    # Proves gate() alone (no httpx call inside it at all) reuses the
    # exact same rate-limit mechanics fetch() does — this is the whole
    # point of extracting it: a Playwright page load standing in for the
    # "do the real work" step below still gets real per-domain spacing.
    min_delay = 0.3
    agent = _agent_with_fake_client(tmp_path, min_delay_seconds=min_delay)

    async def probe(n):
        async with agent.gate(f"https://same-gated.example/{n}"):
            pass

    start = time.monotonic()
    await asyncio.gather(probe(1), probe(2))
    elapsed = time.monotonic() - start

    assert elapsed >= min_delay - 0.05, f"expected >= ~{min_delay}s spacing, got {elapsed}s"


# --- Asymmetric robots_cache TTL + double-check before persisting a
# blocked result (Session 22) -------------------------------------------
#
# Real incident this responds to: MorphiSec got cached as "disallowed"
# from what a fresh check later showed was a transient glitch (its real
# robots.txt has no Disallow rules at all) — see ARCHITECTURE.md §6. A
# wrong "blocked" silently skips a real company for as long as the cache
# trusts it, so it gets a short leash (an hour, not a week) and a second
# opinion before being trusted enough to cache at all.


def _write_cache_entry(cache_path, domain, allowed, age_seconds):
    cache_path.write_text(
        json.dumps({domain: {"domain": domain, "allowed": allowed, "checked_at": time.time() - age_seconds}}),
        encoding="utf-8",
    )


async def test_cached_false_older_than_the_short_ttl_triggers_a_recheck(tmp_path):
    from compliance.agent import ROBOTS_CACHE_BLOCKED_TTL_SECONDS

    cache_path = tmp_path / "robots_cache.json"
    _write_cache_entry(cache_path, "recently-blocked.example", allowed=False, age_seconds=ROBOTS_CACHE_BLOCKED_TTL_SECONDS + 60)

    agent = ComplianceAgent(min_delay_seconds=0.0, robots_cache_path=cache_path, blocked_recheck_delay_seconds=0)
    agent._client = _FakeHTTPClient(robots_txt_status=404)  # live re-check says allowed now

    await agent.fetch("https://recently-blocked.example/jobs")

    assert agent._client.robots_call_count() >= 1
    refreshed = json.loads(cache_path.read_text(encoding="utf-8"))["recently-blocked.example"]
    assert refreshed["allowed"] is True


async def test_cached_true_within_the_long_ttl_does_not_trigger_a_recheck_even_past_the_short_ttl(tmp_path):
    from compliance.agent import ROBOTS_CACHE_BLOCKED_TTL_SECONDS

    cache_path = tmp_path / "robots_cache.json"
    # Deliberately older than the short (blocked) TTL but well within the
    # long (allowed) TTL — proves the two TTLs are genuinely asymmetric,
    # not just the same number applied to both outcomes.
    _write_cache_entry(cache_path, "long-trusted.example", allowed=True, age_seconds=ROBOTS_CACHE_BLOCKED_TTL_SECONDS + 60)

    agent = ComplianceAgent(min_delay_seconds=0.0, robots_cache_path=cache_path)
    agent._client = _FakeHTTPClient(robots_txt_status=403)  # would flip the result if it were ever consulted

    await agent.fetch("https://long-trusted.example/jobs")

    assert agent._client.robots_call_count() == 0


async def test_a_single_transient_block_followed_by_allowed_persists_true(tmp_path):
    agent = ComplianceAgent(min_delay_seconds=0.0, robots_cache_path=tmp_path / "robots_cache.json", blocked_recheck_delay_seconds=0)
    agent._client = _FakeHTTPClient(robots_txt_status_sequence=[403, 404])

    # Must NOT raise — the one-time glitch shouldn't block the fetch.
    await agent.fetch("https://glitchy.example/jobs")

    assert agent._client.robots_call_count() == 2
    cache = json.loads((tmp_path / "robots_cache.json").read_text(encoding="utf-8"))
    assert cache["glitchy.example"]["allowed"] is True


async def test_two_consecutive_blocked_responses_persist_false(tmp_path):
    agent = ComplianceAgent(min_delay_seconds=0.0, robots_cache_path=tmp_path / "robots_cache.json", blocked_recheck_delay_seconds=0)
    agent._client = _FakeHTTPClient(robots_txt_status_sequence=[403, 403])

    with pytest.raises(ComplianceError):
        await agent.fetch("https://really-blocked.example/jobs")

    assert agent._client.robots_call_count() == 2
    cache = json.loads((tmp_path / "robots_cache.json").read_text(encoding="utf-8"))
    assert cache["really-blocked.example"]["allowed"] is False


async def test_the_recheck_waits_the_configured_delay_before_trying_again(tmp_path):
    delay = 0.2
    agent = ComplianceAgent(min_delay_seconds=0.0, robots_cache_path=tmp_path / "robots_cache.json", blocked_recheck_delay_seconds=delay)
    agent._client = _FakeHTTPClient(robots_txt_status_sequence=[403, 404])

    await agent.fetch("https://slow-recheck.example/jobs")

    robots_call_times = sorted(t for url, t in agent._client.calls if url.endswith("/robots.txt"))
    assert len(robots_call_times) == 2
    spacing = robots_call_times[1] - robots_call_times[0]
    assert spacing >= delay - 0.05, f"expected >= ~{delay}s between the two robots.txt checks, got {spacing}s"


# --- Connection limit (Session 36): a deliberate httpx.Limits value,
# not the library's implicit default. These tests inspect the *real*
# httpx.AsyncClient ComplianceAgent constructs — not a fake — since the
# whole point is confirming the configured value actually reaches
# httpx's own connection pool, not just that it's stored as an unused
# instance attribute. httpx has no public API for reading a client's
# configured Limits back out; `_transport._pool._max*` is the only way
# to see what was actually applied, confirmed directly against the
# installed httpx version before relying on it here.


async def test_default_connection_limits_are_actually_applied_to_the_real_client(tmp_path):
    agent = ComplianceAgent(robots_cache_path=tmp_path / "robots_cache.json")
    try:
        pool = agent._client._transport._pool
        assert pool._max_connections == 200
        assert pool._max_keepalive_connections == 20
    finally:
        await agent.aclose()


async def test_custom_connection_limits_are_actually_applied_to_the_real_client(tmp_path):
    agent = ComplianceAgent(
        robots_cache_path=tmp_path / "robots_cache.json",
        max_connections=50,
        max_keepalive_connections=5,
    )
    try:
        pool = agent._client._transport._pool
        assert pool._max_connections == 50
        assert pool._max_keepalive_connections == 5
    finally:
        await agent.aclose()
