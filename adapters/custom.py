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
"""

import json
import re

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
    (ADR-0006). Extracts JSON from the `<script id="...">` tag named in
    `config["script_id"]`, finds the positions list nested somewhere under
    `config["positions_key"]`, and maps each position's fields per
    `config["field_map"]` (dotted paths for nested values) plus
    `config["url_template"]` (formatted with the position's own raw dict)
    to build absolute_url.

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


def load_custom_selectors(path):
    """Load custom_selectors.json — the config-driven map of company name
    to extraction config, same loading pattern as roles.json/locations.json.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)
