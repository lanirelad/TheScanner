"""Playwright-based ATS discovery (ADR-0031) — discovery/onboarding
sessions only, never the production scan pipeline (ADR-0001 keeps that
on plain httpx).

Why this exists, confirmed not assumed: Sessions 18-20 each independently
landed in a low single-digit-percent hit rate discovering new companies'
ATS via a plain HTTP GET (see ARCHITECTURE.md §4a). The common cause,
diagnosed across all three: most real career pages are client-rendered
SPAs whose ATS integration (a redirect, an embedded link, an XHR/fetch
call to a known ATS API) only exists after JavaScript actually executes
— invisible to `httpx`, visible to an actual browser. This module is the
same detection target as `discover_round3.py`'s static method (URL
patterns, embedded links, redirect targets) applied to a page a headless
browser has actually rendered, plus one signal a static fetch can never
see at all: every network request the page itself made while loading.

Every page load here still goes through `ComplianceAgent.gate()` — the
same robots.txt check and per-domain rate limit as every other fetch in
this project (ADR-0002). The fetch *mechanism* changes for discovery;
the compliance *discipline* does not, and this module never duplicates
any of ComplianceAgent's own robots.txt/rate-limit logic to get that.
"""

import re

from playwright.async_api import async_playwright

# Broader than discover_round3.py's static-method regex on purpose:
# Playwright adds a signal that method never had access to at all — the
# page's own observed network requests — and a JS bundle realistically
# calls the JSON API domain directly (boards-api.greenhouse.io/v1/boards/
# {slug}/jobs), not the human-facing public page (job-boards.greenhouse.io/
# {slug}) a redirect or an embedded link would show. Matching both here
# means a network-request hit still resolves the right slug regardless of
# which of the two domains the observed request actually used.
GH_RE = re.compile(r"(?:job-boards|boards-api|boards)\.greenhouse\.io/(?:v1/boards/)?([a-zA-Z0-9_-]+)")
GH_EU_RE = re.compile(r"job-boards\.eu\.greenhouse\.io/([a-zA-Z0-9_-]+)")
LV_RE = re.compile(r"(?:jobs|api)\.lever\.co/(?:v0/postings/)?([a-zA-Z0-9_-]+)")
LV_EU_RE = re.compile(r"jobs\.eu\.lever\.co/([a-zA-Z0-9_-]+)")
CM_RE = re.compile(r"comeet\.com/jobs/([a-zA-Z0-9_-]+)/([a-zA-Z0-9.]+)")

# Session 35: the comeet.co gap flagged in Session 32 — Comeet's own
# widget-serving domain (comeet.co, not comeet.com) never matched CM_RE
# above at all, which is exactly why 7 of the real Comeet companies
# found this session (Coralogix, Guesty, Overwolf, Artlist, Claroty,
# DriveNets, Upwind) needed manual web research instead of being caught
# automatically. This regex catches the specific shape confirmed
# empirically this session across three companies' real white-labeled
# Comeet integrations (a WordPress plugin proxying Comeet under the
# company's own domain, e.g. coralogix.com/careers/co/.../4B.75E/...):
# every one of them exposes a `company-uid=` query parameter on a
# comeet.co request (the apply/social iframe URLs, or the widget's own
# api.js init call) even though the surrounding page never shows a
# public comeet.com/jobs/{slug}/{uid} link anywhere. Deliberately
# returns `slug: None` — a company-uid alone is enough to *recognize*
# the company as Comeet-backed, but the real public comeet.com URL still
# needs a slug, which this pattern never reveals (Coralogix's white-label
# plugin serves jobs from its own domain, not comeet.com, precisely so
# the public page doesn't need to exist at all) — confirming the slug
# still takes one manual guess-and-verify step against the real
# ComeetAdapter, same as every other company this session, just with
# the uid already known instead of needing to be found too.
CM_WIDGET_UID_RE = re.compile(r"comeet\.co/[^\s\"']*[?&]company-uid=([a-zA-Z0-9.]+)")

# Session 32 (Growth playbook Phase 1): recognition-only signatures for
# three platforms this project has no adapter for — Workday,
# SmartRecruiters, iCIMS. Each pattern was checked against real
# documentation and empirically verified against one live real-world
# example before being trusted (see PROGRESS.md's Session 32 addendum):
#   - Workday: nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite
#   - SmartRecruiters: careers.smartrecruiters.com/TheNielsenCompany
#   - iCIMS: careers-wcpss.icims.com
# Deliberately kept separate from _detect_ats()/GH_RE/LV_RE/CM_RE above —
# this project has no adapter for any of these three, so a match here
# must never be mistaken for something the scan pipeline can fetch jobs
# from. It only feeds `companies_unscannable.json` (ARCHITECTURE.md §14),
# a record of *why* a company can't be scanned yet, not a new ATS this
# codebase can act on.
WORKDAY_RE = re.compile(r"([a-zA-Z0-9_-]+\.wd\d+\.myworkdayjobs\.com)")
SMARTRECRUITERS_RE = re.compile(r"(?:careers|jobs|api)\.smartrecruiters\.com/(?:v1/companies/)?([a-zA-Z0-9_-]+)")
ICIMS_RE = re.compile(r"([a-zA-Z0-9_-]+\.icims\.com)")

DEFAULT_WAIT_TIMEOUT_MS = 8000


def _detect_ats(haystack):
    """Same detection targets as discover_round3.py's static method —
    only the input (a real, rendered page's data) differs. Comeet is
    checked first since its URL shape is the most specific (both a slug
    and a uid), same ordering reasoning as the static version.
    """
    m = CM_RE.search(haystack)
    if m:
        return {"ats": "comeet", "slug": m.group(1), "uid": m.group(2)}
    m = GH_EU_RE.search(haystack)
    if m:
        return {"ats": "greenhouse", "slug": m.group(1), "region": "eu"}
    m = GH_RE.search(haystack)
    if m:
        return {"ats": "greenhouse", "slug": m.group(1)}
    m = LV_EU_RE.search(haystack)
    if m:
        return {"ats": "lever", "slug": m.group(1), "region": "eu"}
    m = LV_RE.search(haystack)
    if m:
        return {"ats": "lever", "slug": m.group(1)}
    m = CM_WIDGET_UID_RE.search(haystack)
    if m:
        return {"ats": "comeet", "slug": None, "uid": m.group(1)}
    return None


def _detect_unsupported_platform(haystack):
    """Recognition only (Session 32) — identifies a company as using
    Workday, SmartRecruiters, or iCIMS without this project having any
    ability to actually fetch jobs from it. Only ever consulted by
    `probe()` below after `_detect_ats()` has already found nothing —
    if a page somehow matched both, the real, supported ATS always wins.
    Returns {"platform", "identifier"} or None.
    """
    m = WORKDAY_RE.search(haystack)
    if m:
        return {"platform": "workday", "identifier": m.group(1)}
    m = SMARTRECRUITERS_RE.search(haystack)
    if m:
        return {"platform": "smartrecruiters", "identifier": m.group(1)}
    m = ICIMS_RE.search(haystack)
    if m:
        return {"platform": "icims", "identifier": m.group(1)}
    return None


class PlaywrightProbe:
    """Headless-browser probe for a batch of company career pages.

    One instance's browser is meant to be reused across many probe()
    calls in a discovery batch — the same "one instance shared across a
    run" pattern ComplianceAgent itself already uses. Launching a fresh
    Chromium process per company would be pure overhead; each probe()
    call opens its own page/tab against the shared browser instead.

    `async with PlaywrightProbe(compliance_agent) as probe:` mirrors
    `async with ComplianceAgent() as agent:` deliberately, so both
    lifecycles read the same way at a call site that needs both.
    """

    def __init__(self, compliance_agent, wait_timeout_ms=DEFAULT_WAIT_TIMEOUT_MS):
        self.compliance_agent = compliance_agent
        self.wait_timeout_ms = wait_timeout_ms
        self._playwright = None
        self._browser = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch()
        return self

    async def __aexit__(self, *exc_info):
        await self._browser.close()
        await self._playwright.stop()

    async def probe(self, url):
        """Load `url` with the shared headless browser, wait for it to
        actually settle, and look for a real ATS signal.

        "Settle" is `wait_until="networkidle"` (no network connections
        for 500ms) — a real signal Playwright observes, not a fixed
        `asyncio.sleep()` guess at how long a page takes to render.
        `page.goto()`'s own timeout is caught, not propagated: a slow or
        never-fully-idle page (some SPAs poll continuously) still leaves
        a real rendered DOM and a real list of network requests worth
        inspecting, so a timeout here means "inspect what actually
        loaded," not "this candidate failed."

        The whole page load happens inside `self.compliance_agent.gate(url)`
        — robots.txt and the per-domain rate limit apply to this exactly
        as they would to an httpx GET of the same URL; ComplianceError
        propagates out of this method unchanged if the domain is
        disallowed, before the browser ever navigates anywhere.

        Returns a dict describing what was found (ats/slug/uid/region,
        plus which evidence source matched — the final URL after any
        client-side redirect, the rendered HTML, or an observed network
        request) or None if nothing matched. This only ever *observes*
        network requests the page made to other domains — it never
        fetches them directly; confirming a discovered slug against the
        real ATS API is a separate, ordinary ComplianceAgent.fetch()
        call, so every real request this project makes — Playwright's
        page loads included — still goes through the same gate.
        """
        requests_seen = []

        async with self.compliance_agent.gate(url):
            page = await self._browser.new_page()
            try:
                page.on("request", lambda request: requests_seen.append(request.url))
                try:
                    await page.goto(url, wait_until="networkidle", timeout=self.wait_timeout_ms)
                except Exception:
                    pass

                final_url = page.url

                # A goto() that timed out can leave the page still mid-
                # navigation for a moment — content() (and even .url, in
                # principle) can raise its own separate "page is
                # navigating" error right after, not just goto() itself.
                # Every network request was already captured via the
                # listener above regardless, so an unreadable DOM here
                # still leaves two of the three evidence sources intact.
                try:
                    html = await page.content()
                except Exception:
                    html = ""
            finally:
                await page.close()

        hit = _detect_ats(final_url)
        evidence = "redirect_target"
        if hit is None:
            hit = _detect_ats(html)
            evidence = "rendered_dom"
        if hit is None:
            for request_url in requests_seen:
                hit = _detect_ats(request_url)
                if hit is not None:
                    evidence = "network_request"
                    break

        if hit is not None:
            hit["source_url"] = url
            hit["final_url"] = final_url
            hit["evidence"] = evidence
            hit["network_requests_observed"] = len(requests_seen)
            return hit

        # Session 32: only reached once every supported-ATS check above
        # has already come back empty — a real ATS match always wins over
        # an unsupported-platform recognition, since those are the two
        # meaningfully different outcomes ("this project can act on this"
        # vs. "this project can only note this down").
        unsupported = _detect_unsupported_platform(final_url)
        evidence = "redirect_target"
        if unsupported is None:
            unsupported = _detect_unsupported_platform(html)
            evidence = "rendered_dom"
        if unsupported is None:
            for request_url in requests_seen:
                unsupported = _detect_unsupported_platform(request_url)
                if unsupported is not None:
                    evidence = "network_request"
                    break

        if unsupported is None:
            return None

        return {
            "ats": None,
            "unsupported_platform": unsupported["platform"],
            "platform_identifier": unsupported["identifier"],
            "source_url": url,
            "final_url": final_url,
            "evidence": evidence,
            "network_requests_observed": len(requests_seen),
        }
