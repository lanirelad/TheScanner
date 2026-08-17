"""Compliance Agent — the non-negotiable gate for every outbound fetch.

Per ADR-0002 / ARCHITECTURE.md §6: every adapter call must pass through
this agent. It checks robots.txt for the target domain and enforces a
per-domain minimum delay between requests. No adapter should call an HTTP
client directly.

Async retrofit (ADR-0021): built on httpx.AsyncClient rather than aiohttp.
httpx's request/response API mirrors `requests` (the library this
replaces) closely — same `.json()`, `.status_code`, `.raise_for_status()`
surface — so adapters and tests written against `requests`-shaped
responses needed almost no changes. httpx also ships one client class that
supports both sync and async, with no separate session-lifecycle contract
to get right; aiohttp requires its ClientSession to be created inside a
running event loop and explicitly closed, which is one more thing to get
wrong for no benefit here.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger("compliance")

DEFAULT_USER_AGENT = "TheScannerBot/0.1 (+https://github.com/; job-board scan, respects robots.txt)"
# ADR-0002 requires *some* per-domain rate limit; 1.5s is our own chosen
# value within that requirement (the task brief suggested a 1-2s range),
# not a number mandated by the ADR itself.
DEFAULT_MIN_DELAY_SECONDS = 1.5
DEFAULT_TIMEOUT_SECONDS = 10
# robots.txt essentially never changes (PLAN.md "Robots.txt cache
# persistence — chosen approach"), so a week-long TTL trades a
# theoretical staleness window for not re-fetching it on every single run.
# Session 22: this long TTL is deliberately asymmetric now — it only
# applies to `allowed: true` cache entries. Being wrong about "allowed"
# is low-risk (we just fetch normally, which is always safe); a week is
# a fine price for not re-checking a domain that's never given us any
# trouble.
ROBOTS_CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
# A cached `allowed: false` gets trusted for a much shorter window. Real
# incident this session responds to: MorphiSec got cached as
# "disallowed" from what a fresh check later showed was a transient
# glitch (its real robots.txt has no Disallow rules at all) — a wrong
# "blocked" silently skips a real company for the entire cache window,
# every single scan run, with no visible symptom at all. An hour bounds
# that blast radius to "this run and maybe the next," not "a full week
# of missed postings," while still avoiding a live re-check on every
# single fetch to a domain that's actually, genuinely blocked.
ROBOTS_CACHE_BLOCKED_TTL_SECONDS = 60 * 60
DEFAULT_ROBOTS_CACHE_PATH = Path(__file__).resolve().parent.parent / "robots_cache.json"
# How long to wait before re-checking a fresh "disallowed" result before
# trusting it enough to cache. A few seconds is enough that a one-time
# glitch (a momentary bot-protection challenge, a flaky response) almost
# never repeats immediately after; a genuine, real Disallow rule always
# will, since robots.txt content doesn't change on that timescale.
DEFAULT_BLOCKED_RECHECK_DELAY_SECONDS = 5


class ComplianceError(Exception):
    """Raised when a fetch is blocked by robots.txt or another compliance rule."""


class ComplianceAgent:
    """Gate that every adapter fetch must go through.

    One instance is meant to be shared across a scan run so the per-domain
    rate limit and robots.txt cache actually apply across all calls to the
    same domain, not just within a single adapter invocation. Supports
    `async with ComplianceAgent() as agent:` so the underlying HTTP client
    is always closed cleanly.
    """

    def __init__(
        self,
        min_delay_seconds=DEFAULT_MIN_DELAY_SECONDS,
        user_agent=DEFAULT_USER_AGENT,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        robots_cache_path=DEFAULT_ROBOTS_CACHE_PATH,
        blocked_recheck_delay_seconds=DEFAULT_BLOCKED_RECHECK_DELAY_SECONDS,
    ):
        self.min_delay_seconds = min_delay_seconds
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.robots_cache_path = Path(robots_cache_path)
        # Session 22: overridable mainly so tests can drive this down to
        # ~0 instead of waiting a real 5 seconds per blocked-domain test.
        self.blocked_recheck_delay_seconds = blocked_recheck_delay_seconds
        self._domain_locks = {}
        self._last_request_at = {}
        # Guards robots_cache.json specifically, separate from the
        # per-domain fetch locks below: that file is shared across every
        # domain, so two *different* domains' tasks could otherwise race
        # on reading, updating, and writing it back. See _check_robots for
        # why one lock is enough even though it's held across a network
        # call.
        self._robots_cache_lock = asyncio.Lock()
        self._client = httpx.AsyncClient()

    async def aclose(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        await self.aclose()

    def _lock_for_domain(self, domain):
        """Get-or-create the asyncio.Lock serializing fetches to one domain.

        Safe without its own guard even though it's a "check, then create"
        sequence: asyncio is single-threaded and cooperative, and there is
        no `await` between the dict lookup and the dict write, so no other
        task can be interleaved in between and create a second Lock for the
        same domain. This would NOT be safe under real OS threads — the
        exact reason ADR-0021 is async/await, not threads+locks.
        """
        lock = self._domain_locks.get(domain)
        if lock is None:
            lock = asyncio.Lock()
            self._domain_locks[domain] = lock
        return lock

    def _read_robots_cache(self):
        if not self.robots_cache_path.exists():
            return {}
        try:
            with open(self.robots_cache_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_robots_cache(self, cache):
        with open(self.robots_cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)

    async def _is_allowed(self, domain, scheme, url):
        """Return whether `url` may be fetched.

        Checks the persisted, domain-level robots_cache.json first (PLAN.md
        "Robots.txt cache persistence — chosen approach": entries shaped
        {domain, allowed, checked_at}) before ever re-fetching robots.txt
        live. This is deliberately domain-level, not per-path: every
        adapter today hits exactly one URL pattern per domain
        (Greenhouse's /v1/boards/{slug}/jobs, Lever's /v0/postings/{slug}),
        so a single cached decision per domain is accurate for every call
        we actually make. A future adapter hitting multiple differently-
        permissioned paths on the same domain would need to make this
        per-path instead — flagging that limitation here rather than
        silently building past it.

        Session 22, two changes in response to a real incident (MorphiSec
        — see ARCHITECTURE.md §6): the TTL is asymmetric
        (ROBOTS_CACHE_TTL_SECONDS for `allowed: true`,
        ROBOTS_CACHE_BLOCKED_TTL_SECONDS — much shorter — for
        `allowed: false`), and a fresh "disallowed" result is re-checked
        once, a few seconds later, before being trusted enough to cache;
        only two agreeing checks get persisted as `false`. Both changes
        target the same asymmetry: a wrong `allowed: true` costs nothing
        (we just fetch, which is always safe), while a wrong
        `allowed: false` silently skips a real company for as long as
        the cache trusts it — that risk deserves a short leash and a
        second opinion, not a week and blind trust.

        self._robots_cache_lock guards only the brief, synchronous file
        read/write steps below, not the live robots.txt network fetch(es)
        in between. Holding it across the network call too would have
        been simpler to reason about, but it would also have forced
        every domain's first-ever robots.txt check to queue behind
        whichever domain got there first — exactly the cross-domain
        blocking ADR-0021 exists to avoid. Two different domains hitting
        a cold cache at the same time can now fetch robots.txt fully
        concurrently; only their (near-instant, local-disk) writes to
        the shared cache file are serialized. Same-domain calls can't
        race here at all regardless, since fetch()/gate() already hold
        that domain's own lock around this entire method.
        """
        async with self._robots_cache_lock:
            cache = self._read_robots_cache()
            entry = cache.get(domain)
            now = time.time()
            if entry is not None:
                ttl = ROBOTS_CACHE_TTL_SECONDS if entry["allowed"] else ROBOTS_CACHE_BLOCKED_TTL_SECONDS
                if (now - entry["checked_at"]) < ttl:
                    return entry["allowed"]

        allowed = await self._check_robots_live(domain, scheme, url)

        if not allowed:
            # Don't trust a single "disallowed" result enough to cache
            # it — a transient glitch (a momentary bot-protection
            # challenge, a flaky response) almost never repeats a few
            # seconds later; a genuine block always will, since real
            # robots.txt content doesn't change on that timescale.
            await asyncio.sleep(self.blocked_recheck_delay_seconds)
            allowed = await self._check_robots_live(domain, scheme, url)

        async with self._robots_cache_lock:
            cache = self._read_robots_cache()
            cache[domain] = {"domain": domain, "allowed": allowed, "checked_at": time.time()}
            self._write_robots_cache(cache)

        return allowed

    async def _check_robots_live(self, domain, scheme, url):
        """Fetch and evaluate robots.txt for one URL.

        Mirrors urllib.robotparser.RobotFileParser.read()'s own HTTP-status
        handling (its source is the reference here, not a guess): 401/403
        on robots.txt itself means the site is explicitly restricting
        access to it, so RobotFileParser treats that as disallow-everything;
        any other 4xx (typically 404, no robots.txt published) means
        allow-everything; a network failure or 5xx falls through to
        RobotFileParser's own default of allow (no rules were ever parsed).
        We replicate this by hand because httpx.AsyncClient doesn't have a
        drop-in async equivalent of RobotFileParser.read().
        """
        robots_url = f"{scheme}://{domain}/robots.txt"
        try:
            response = await self._client.get(robots_url, timeout=self.timeout_seconds)
        except httpx.HTTPError:
            return True

        if response.status_code in (401, 403):
            return False
        if response.status_code >= 400:
            return True

        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser.can_fetch(self.user_agent, url)

    async def _wait_for_rate_limit(self, domain):
        last_at = self._last_request_at.get(domain)
        if last_at is not None:
            elapsed = time.monotonic() - last_at
            remaining = self.min_delay_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)

    @asynccontextmanager
    async def gate(self, url):
        """Check robots.txt and enforce the per-domain rate limit for
        `url`, without performing any fetch itself.

        Session 21: extracted out of fetch() (which is now just this
        gate wrapped around one httpx call) so a different fetch
        mechanism — a Playwright-driven page load, for discovery
        sessions per ADR-0031 — can get the exact same compliance
        discipline (robots.txt honored, same per-domain rate limit, same
        atomic check-wait-fetch-record sequence under one lock) without
        duplicating any of this logic. The fetch mechanism is the only
        thing that should ever change between production scanning and
        discovery; the compliance gate must not.

        Raises ComplianceError if robots.txt disallows `url` — before
        the rate-limit wait, so a blocked fetch never consumes a
        rate-limit slot. On successful entry, the caller performs its
        own fetch inside the `async with` block; the domain's completion
        timestamp is recorded only after that block returns normally —
        matching fetch()'s original ordering exactly (spacing is
        measured between actual completed fetches, not from when a
        fetch was merely allowed to start; a failed fetch inside the
        block, same as before this refactor, does not get recorded).
        """
        parsed = urlparse(url)
        domain = parsed.netloc

        lock = self._lock_for_domain(domain)
        async with lock:
            allowed = await self._is_allowed(domain, parsed.scheme, url)
            if not allowed:
                logger.info("BLOCKED by robots.txt: %s", url)
                raise ComplianceError(f"robots.txt disallows fetching {url}")

            await self._wait_for_rate_limit(domain)

            yield

            self._last_request_at[domain] = time.monotonic()

    async def fetch(self, url, params=None):
        """Fetch `url` after checking robots.txt and enforcing rate limits.

        Returns the httpx.Response. Raises ComplianceError if robots.txt
        disallows the URL for our user agent. See gate() for the actual
        robots.txt/rate-limit mechanics — this is now just that gate
        wrapped around a single httpx call, with the response's own
        status logged and raised on afterward.
        """
        async with self.gate(url):
            response = await self._client.get(
                url,
                params=params,
                headers={"User-Agent": self.user_agent},
                timeout=self.timeout_seconds,
            )

        logger.info(
            "ALLOWED fetch: %s -> status %s",
            response.url,
            response.status_code,
        )

        response.raise_for_status()
        return response
