"""Custom/non-ATS fallback adapter (ARCHITECTURE.md §4a's "custom scraper"
bucket) — config-driven, not one Python subclass per company.

Empirically confirmed this session (Session 6), not assumed: monday.com's
career page (a genuinely custom, in-house page with UUID-based job URLs,
no known ATS fingerprint) does NOT require JavaScript execution. A plain
HTTP GET already returns a server-rendered page containing a
`<script id="__NEXT_DATA__">` tag — Next.js's standard SSR data-hydration
mechanism — with the full position list embedded as JSON inside it,
nested under an opaque, presumably per-deploy-generated UUID key (e.g.
`props.pageProps.dynamicData.<uuid>.positions`). No headless browser was
needed to find or extract this.

`CustomAdapter` is one class driven entirely by a per-company config dict
(loaded from `custom_selectors.json`, same config-driven philosophy as
`roles.json`/`locations.json`) rather than a bespoke `MondayComAdapter`.
This scales via configuration *only* for companies sharing the same
rendering pattern this adapter knows how to read: a script tag containing
JSON, with the positions list found by searching for a named key anywhere
inside it (deliberately not a fixed path, since the wrapping UUID key
isn't safe to hardcode in config — see `_find_list_by_key`). A company
using a genuinely different pattern (a different framework's hydration
blob, a fully static DOM with position data only in HTML attributes and no
JSON blob at all, or one that truly does need JS execution) would need
this adapter to grow a second extraction strategy, not just a new config
entry — an honest limit, not a design gap: one algorithm can't cover every
possible custom page by construction.

Interesting side-observation, not acted on this session: monday.com's
embedded position data includes `"source": "ashby"` for every position —
Ashby is a real, named ATS platform being proxied through monday.com's own
page rather than linked out to a separate ashby.com domain. If this
pattern (an ATS's data embedded in an otherwise-custom page) turns out to
be common across other "custom" companies, a dedicated Ashby-aware
strategy might be worth more than treating every one of them as fully
bespoke — flagged for a future onboarding session, not decided here.

Second strategy added Session 36 — `css_selectors`, driven by
`config["strategy"]` (now a required field; monday.com's own config was
updated to say `"json_blob"` explicitly rather than leaving it as an
implicit default). Confirmed empirically against 3 real companies
(ForSight Robotics, AIR, Quantum Art — all flagged in Session 35 as
genuinely custom with real job data CustomAdapter's original strategy
couldn't reach at all) that this is a *second*, genuinely different
rendering pattern, not a variant of the first: plain, already-server-
rendered HTML (a Webflow CMS collection in every case checked so far),
no JSON blob anywhere on the page. Confirmed directly against a plain
`httpx` GET for all three (not just a browser-rendered DOM) before
trusting this — Webflow's CMS collections render their real content
server-side for SEO, so no headless browser is needed here either, same
as the JSON-blob strategy's own monday.com finding. Real per-company
quirks the config schema had to accommodate, not idealized away:
- A field can be genuinely absent for one company but present for
  another (Quantum Art's own `.career-location` element exists but is
  empty for every position — `w-dyn-bind-empty` is Webflow's own marker
  for an unbound CMS field) — `_select_text` returns `None`, not an
  error, same "safe empty field" philosophy as the JSON strategy's
  `_get_path`.
- A company can have no per-position URL at all (AIR's listings open a
  JS-driven modal via a `data-popup` attribute, not a real link — zero
  `<a>` tags anywhere inside any of its job items, confirmed directly)
  — `url_selector` is optional; when absent, or when present but the
  selected element has no real `href`, every position's `absolute_url`
  falls back to the company's own `career_page_url` itself, which is
  still honest and actionable (a real place to go looking for that
  exact role), rather than fabricating a fake per-position URL.
"""

import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from adapters.base import Adapter


class CustomAdapter(Adapter):
    """Adapter for genuinely custom (non-ATS) career pages.

    Configured per company via a dict (see module docstring and
    custom_selectors.json) passed at construction time, mirroring how
    ComeetAdapter takes ats_uid — the difference is this adapter needs a
    handful of config values, not just one extra identifier, since there's
    no shared platform behavior to fall back on.
    """

    def __init__(self, compliance_agent, config):
        super().__init__(compliance_agent)
        self.config = config

    async def fetch_stage1_jobs(self, ats_slug):
        """Fetch and parse the Stage 1 job list for a custom career page.

        `ats_slug` is unused — kept only so this adapter's method signature
        matches the Adapter contract exactly. Custom companies have no
        slug-based URL scheme the way Greenhouse/Lever/Comeet do; the
        actual URL comes entirely from `self.config["career_page_url"]`.
        """
        url = self.config["career_page_url"]
        response = await self.compliance_agent.fetch(url)
        return parse_stage1_jobs(response.text, self.config)


def _get_path(obj, dotted_path):
    """Look up a possibly-nested value via a dotted path, e.g. "location.name"."""
    for key in dotted_path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _find_list_by_key(obj, key):
    """Recursively search a parsed JSON structure for the first list found
    under a dict key matching `key`.

    Confirmed empirically against monday.com's real __NEXT_DATA__ blob that
    "positions" appears exactly once in the entire structure (checked by
    counting raw occurrences of the key before trusting this approach), so
    a plain first-match search is safe here — not just convenient. Search-
    by-key instead of a fixed path means config never needs to know the
    wrapping UUID key at all, which also isn't confirmed stable across
    deploys.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, list):
                return v
            found = _find_list_by_key(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_list_by_key(item, key)
            if found is not None:
                return found
    return None


def parse_stage1_jobs(html, config):
    """Convert a raw custom career page HTML response into the Stage 1 shape.

    Pure function, no network — fixture-based tests call this directly
    (ADR-0006). Dispatches on `config["strategy"]` — a required field
    (Session 36) rather than an implicit default, since a second real
    strategy now exists and guessing which one a config means would be
    exactly the kind of silent ambiguity this project avoids elsewhere.
    """
    strategy = config["strategy"]
    if strategy == "json_blob":
        return _parse_json_blob_jobs(html, config)
    if strategy == "css_selectors":
        return _parse_css_selectors_jobs(html, config)
    raise ValueError(f"unknown custom_selectors strategy: {strategy!r}")


def _parse_json_blob_jobs(html, config):
    """Session 6's original strategy: a `<script id="...">` tag holding a
    JSON blob (monday.com's Next.js `__NEXT_DATA__` pattern). Extracts JSON
    from the tag named in `config["script_id"]`, finds the positions list
    nested somewhere under `config["positions_key"]`, and maps each
    position's fields per `config["field_map"]` (dotted paths for nested
    values) plus `config["url_template"]` (formatted with the position's
    own raw dict) to build absolute_url.

    Returns an empty list, not an error, if the named script tag is
    missing or the positions key can't be found — a company page redesign
    breaking this extraction should show up as "zero jobs found," which is
    at least a safe, quiet failure mode, not a crash.
    """
    script_id = config["script_id"]
    pattern = re.compile(r'<script id="' + re.escape(script_id) + r'"[^>]*>(.*?)</script>', re.S)
    match = pattern.search(html)
    if match is None:
        return []

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    positions = _find_list_by_key(data, config["positions_key"])
    if positions is None:
        return []

    field_map = config["field_map"]
    url_template = config["url_template"]
    jobs = []
    for position in positions:
        jobs.append(
            {
                "title": _get_path(position, field_map["title"]),
                "department": _get_path(position, field_map["department"]),
                "location": _get_path(position, field_map["location"]),
                "absolute_url": url_template.format(**position),
            }
        )
    return jobs


def _select_text(item, selector):
    """Select the first element matching `selector` within `item` and
    return its stripped text, or None if nothing matches or the matched
    element has no real text (Webflow's own `w-dyn-bind-empty` marker on
    an unbound CMS field renders as a real, present, but text-empty
    element — confirmed against Quantum Art's real `.career-location`
    this session; empty string and "missing entirely" are treated the
    same way here, since neither carries real data).
    """
    if selector is None:
        return None
    el = item.select_one(selector)
    if el is None:
        return None
    text = el.get_text(strip=True)
    return text or None


def _parse_css_selectors_jobs(html, config):
    """Session 36's second strategy: real job data sitting in plain,
    already-server-rendered HTML with no JSON blob anywhere (confirmed
    against a plain `httpx` GET, not just a browser-rendered DOM, for
    every company this strategy has actually been verified against — see
    the module docstring). `config["item_selector"]` finds each job's
    container element; `config["field_selectors"]["title"/"department"/
    "location"]` are each resolved *relative to that one item* (not the
    whole document), so two jobs' titles never accidentally cross-match.

    `config["url_selector"]` (optional) picks the element whose `href`
    becomes `absolute_url`, resolved against `config["career_page_url"]`
    via `urljoin` (every real example found so far uses a site-relative
    `href`, e.g. "/positions/position-c5_07f"). When it's absent, or the
    selected element has no `href`, `absolute_url` falls back to
    `config["career_page_url"]` itself — confirmed necessary, not a
    theoretical edge case: AIR's real listings open a JS `data-popup`
    modal instead of linking anywhere at all.

    Returns an empty list, not an error, if `item_selector` matches
    nothing — same "quiet, safe failure on a redesign" philosophy as the
    JSON-blob strategy.
    """
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select(config["item_selector"])

    field_selectors = config["field_selectors"]
    url_selector = config.get("url_selector")
    career_page_url = config["career_page_url"]

    jobs = []
    for item in items:
        href = None
        if url_selector is not None:
            link = item.select_one(url_selector)
            if link is not None:
                href = link.get("href")
        absolute_url = urljoin(career_page_url, href) if href else career_page_url

        jobs.append(
            {
                "title": _select_text(item, field_selectors.get("title")),
                "department": _select_text(item, field_selectors.get("department")),
                "location": _select_text(item, field_selectors.get("location")),
                "absolute_url": absolute_url,
            }
        )
    return jobs


def load_custom_selectors(path):
    """Load custom_selectors.json — the config-driven map of company name
    to extraction config, same loading pattern as roles.json/locations.json.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)
