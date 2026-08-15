"""Tests for discovery/playwright_probe.py (Session 21, ADR-0031).

Never launches a real browser or touches the network — Playwright's
async API is stood in for with a small hand-rolled fake (same spirit as
test_compliance_agent.py's fake HTTP client), so the ATS-detection logic
and the compliance-gate integration are both provable without needing
Chromium present in every environment that runs this suite.
"""

import pytest

from compliance.agent import ComplianceAgent, ComplianceError
from discovery.playwright_probe import PlaywrightProbe, _detect_ats


# --- _detect_ats: pure function, same detection targets as the static
# discovery method, just applied to whatever a real browser rendered. ---


def test_detect_ats_finds_greenhouse_link():
    hit = _detect_ats("some html ... https://job-boards.greenhouse.io/acmeco/jobs/123 ... more html")
    assert hit == {"ats": "greenhouse", "slug": "acmeco"}


def test_detect_ats_finds_greenhouse_eu_link():
    hit = _detect_ats("https://job-boards.eu.greenhouse.io/acmeco")
    assert hit == {"ats": "greenhouse", "slug": "acmeco", "region": "eu"}


def test_detect_ats_finds_lever_link():
    hit = _detect_ats("https://jobs.lever.co/acmeco")
    assert hit == {"ats": "lever", "slug": "acmeco"}


def test_detect_ats_finds_greenhouse_api_domain_from_a_network_request():
    # The realistic shape of an actual observed network request — a JS
    # bundle fetching the JSON API directly — differs from the public
    # page URL a redirect/embedded link would show.
    hit = _detect_ats("https://boards-api.greenhouse.io/v1/boards/acmeco/jobs")
    assert hit == {"ats": "greenhouse", "slug": "acmeco"}


def test_detect_ats_finds_lever_api_domain_from_a_network_request():
    hit = _detect_ats("https://api.lever.co/v0/postings/acmeco")
    assert hit == {"ats": "lever", "slug": "acmeco"}


def test_detect_ats_finds_comeet_link_with_slug_and_uid():
    hit = _detect_ats("https://www.comeet.com/jobs/acmeco/12.345")
    assert hit == {"ats": "comeet", "slug": "acmeco", "uid": "12.345"}


def test_detect_ats_returns_none_when_nothing_matches():
    assert _detect_ats("<html><body>just a normal careers page, no ATS mentioned</body></html>") is None


# --- PlaywrightProbe: compliance-gate integration ------------------------


class _FakeRequest:
    def __init__(self, url):
        self.url = url


class _FakePage:
    def __init__(self, final_url, html="", observed_request_urls=()):
        self.url = final_url
        self._html = html
        self._observed_request_urls = observed_request_urls
        self._request_handler = None
        self.closed = False

    def on(self, event, handler):
        if event == "request":
            self._request_handler = handler

    async def goto(self, url, wait_until=None, timeout=None):
        for request_url in self._observed_request_urls:
            if self._request_handler is not None:
                self._request_handler(_FakeRequest(request_url))

    async def content(self):
        return self._html

    async def close(self):
        self.closed = True


class _FakeBrowser:
    """Stands in for a real Chromium browser: hands back one canned
    page per probe() call, same shape the real Playwright API returns.
    """

    def __init__(self, page):
        self._page = page
        self.new_page_calls = 0

    async def new_page(self):
        self.new_page_calls += 1
        return self._page


def _allowing_agent(tmp_path, min_delay_seconds=0.0):
    return ComplianceAgent(min_delay_seconds=min_delay_seconds, robots_cache_path=tmp_path / "robots_cache.json")


def _blocking_agent(tmp_path):
    """A ComplianceAgent whose gate() always raises — reuses the real
    gate() logic against a fake HTTP client that disallows everything,
    rather than a hand-rolled stand-in, so this test exercises the same
    code path a real blocked domain would hit.
    """
    from tests.test_compliance_agent import _FakeHTTPClient

    agent = ComplianceAgent(min_delay_seconds=0.0, robots_cache_path=tmp_path / "robots_cache.json")
    agent._client = _FakeHTTPClient(robots_txt_status=200, robots_txt_text="User-agent: *\nDisallow: /\n")
    return agent


def _probe_with_fake_browser(agent, page):
    probe = PlaywrightProbe.__new__(PlaywrightProbe)  # skip __aenter__: no real Chromium needed
    probe.compliance_agent = agent
    probe.wait_timeout_ms = 8000
    probe._playwright = None
    probe._browser = _FakeBrowser(page)
    return probe


async def test_probe_never_touches_the_browser_when_compliance_blocks(tmp_path):
    agent = _blocking_agent(tmp_path)
    probe = _probe_with_fake_browser(agent, page=None)  # would AttributeError if ever touched

    with pytest.raises(ComplianceError):
        await probe.probe("https://blocked.example/careers")

    assert probe._browser.new_page_calls == 0


async def test_probe_detects_ats_from_a_client_side_redirect(tmp_path):
    # The exact case a static httpx GET can miss: the page's *rendered*
    # final URL (after client-side JS navigation) is the real ATS link,
    # even though nothing in this fake's HTML mentions it at all.
    agent = _allowing_agent(tmp_path)
    page = _FakePage(final_url="https://job-boards.greenhouse.io/acmeco", html="<html>loading...</html>")
    probe = _probe_with_fake_browser(agent, page)

    hit = await probe.probe("https://acme.example/careers")

    assert hit["ats"] == "greenhouse"
    assert hit["slug"] == "acmeco"
    assert hit["evidence"] == "redirect_target"
    assert probe._browser.new_page_calls == 1


async def test_probe_detects_ats_from_rendered_html_when_url_itself_is_unchanged(tmp_path):
    agent = _allowing_agent(tmp_path)
    page = _FakePage(
        final_url="https://acme.example/careers",
        html='<a href="https://jobs.lever.co/acmeco">Apply</a>',
    )
    probe = _probe_with_fake_browser(agent, page)

    hit = await probe.probe("https://acme.example/careers")

    assert hit == {
        "ats": "lever",
        "slug": "acmeco",
        "source_url": "https://acme.example/careers",
        "final_url": "https://acme.example/careers",
        "evidence": "rendered_dom",
        "network_requests_observed": 0,
    }


async def test_probe_detects_ats_from_an_observed_network_request(tmp_path):
    # The signal a static fetch structurally cannot see at all: a
    # post-load JS fetch() call to the real ATS API, with nothing in the
    # static HTML or the page's own URL hinting at it.
    agent = _allowing_agent(tmp_path)
    page = _FakePage(
        final_url="https://acme.example/careers",
        html="<html><body>Loading jobs...</body></html>",
        observed_request_urls=[
            "https://acme.example/static/app.js",
            "https://boards-api.greenhouse.io/v1/boards/acmeco/jobs",
            "https://fonts.googleapis.com/css",
        ],
    )
    probe = _probe_with_fake_browser(agent, page)

    hit = await probe.probe("https://acme.example/careers")

    assert hit["ats"] == "greenhouse"
    assert hit["slug"] == "acmeco"
    assert hit["evidence"] == "network_request"
    assert hit["network_requests_observed"] == 3


async def test_probe_returns_none_when_nothing_matches_anywhere(tmp_path):
    agent = _allowing_agent(tmp_path)
    page = _FakePage(final_url="https://acme.example/careers", html="<html>no ATS here</html>")
    probe = _probe_with_fake_browser(agent, page)

    assert await probe.probe("https://acme.example/careers") is None


async def test_probe_closes_the_page_even_if_goto_raises(tmp_path):
    class _RaisingPage(_FakePage):
        async def goto(self, url, wait_until=None, timeout=None):
            raise TimeoutError("page never went network-idle")

    agent = _allowing_agent(tmp_path)
    page = _RaisingPage(final_url="https://acme.example/careers", html="<html>partial render</html>")
    probe = _probe_with_fake_browser(agent, page)

    # A goto() timeout is swallowed, not propagated — a slow/never-fully-
    # idle SPA still leaves a real DOM worth inspecting.
    await probe.probe("https://acme.example/careers")

    assert page.closed is True


async def test_probe_survives_content_raising_after_a_goto_timeout(tmp_path):
    # Real bug hit live during this session: a goto() timeout can leave
    # the page still mid-navigation, and content() then raises its own
    # separate "page is navigating" error right after — not just goto()
    # itself. The network-request evidence (captured via the listener
    # regardless of what content() does) must still come through.
    class _RaisingPage(_FakePage):
        async def goto(self, url, wait_until=None, timeout=None):
            for request_url in self._observed_request_urls:
                if self._request_handler is not None:
                    self._request_handler(_FakeRequest(request_url))
            raise TimeoutError("page never went network-idle")

        async def content(self):
            raise RuntimeError("Page.content: page is navigating and changing the content")

    agent = _allowing_agent(tmp_path)
    page = _RaisingPage(
        final_url="https://acme.example/careers",
        html="<html>unreachable</html>",
        observed_request_urls=["https://boards-api.greenhouse.io/v1/boards/acmeco/jobs"],
    )
    probe = _probe_with_fake_browser(agent, page)

    hit = await probe.probe("https://acme.example/careers")

    assert hit["ats"] == "greenhouse"
    assert hit["slug"] == "acmeco"
    assert hit["evidence"] == "network_request"
    assert page.closed is True
