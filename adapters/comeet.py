"""Comeet ATS adapter — Stage 1 only (ADR-0016).

Empirically confirmed this session (Session 5), not assumed from
Greenhouse or Lever: for both companies checked (AT&T Israel R&D Center,
Enlight Renewable Energy), Comeet has no dedicated public JSON API
endpoint at all. The public career page
(https://www.comeet.com/jobs/{slug}/{uid}) is server-rendered HTML with
the full job list embedded directly as a JavaScript variable assignment —
`COMPANY_POSITIONS_DATA = [...]` — inside a <script> tag near the top of
the page. No JavaScript execution/headless browser is needed: this data is
present in the initial HTML response itself, straight-line server-
templated (not built up by client-side JS after page load).

Same situation as Lever (see ARCHITECTURE.md §1's per-ATS caveats): there
is no separate lightweight-vs-full-content mode. The embedded data already
includes full HTML job descriptions in `custom_fields.details` for every
position — Stage 1 here is a parsing-layer distinction (we extract and
keep only 4 fields), not a fetch-cost saving the way it is for Greenhouse.
"""

import json
import re

from adapters.base import Adapter

CAREER_PAGE_URL_TEMPLATE = "https://www.comeet.com/jobs/{slug}/{uid}"

_POSITIONS_DATA_PATTERN = re.compile(r"COMPANY_POSITIONS_DATA\s*=\s*(\[.*?\]);", re.S)


class ComeetAdapter(Adapter):
    """Adapter for career pages hosted on Comeet.

    Implements the same Adapter contract as GreenhouseAdapter/LeverAdapter
    (ADR-0018) — a third, structurally different real user of the base
    class (HTML with embedded JS state, instead of a JSON API), and it
    still held up with no changes needed to adapters/base.py.

    Comeet URLs need both a company slug and a separate "uid" (see
    companies.json's ats_uid field) — unlike Greenhouse/Lever, which only
    need one slug. fetch_stage1_jobs's signature still takes a single
    `ats_slug` argument to match the Adapter contract exactly; ats_uid is
    supplied at construction time instead, since it's fixed per company for
    as long as this adapter instance is used, same lifetime as
    compliance_agent.
    """

    def __init__(self, compliance_agent, ats_uid):
        super().__init__(compliance_agent)
        self.ats_uid = ats_uid

    async def fetch_stage1_jobs(self, ats_slug):
        """Fetch and parse the Stage 1 job list for a Comeet career page.

        Routed through self.compliance_agent, per ARCHITECTURE.md §6.
        """
        url = CAREER_PAGE_URL_TEMPLATE.format(slug=ats_slug, uid=self.ats_uid)
        response = await self.compliance_agent.fetch(url)
        return parse_stage1_jobs(response.text)


def parse_stage1_jobs(html):
    """Convert a raw Comeet career page HTML response into the Stage 1 shape.

    Pure function, no network — fixture-based tests call this directly
    (ADR-0006). Extracts the `COMPANY_POSITIONS_DATA` JS array embedded in
    a <script> tag (see module docstring) and maps Comeet's field names
    onto the shared Stage 1 shape:

    - title <- position["name"]. Comeet calls the title field "name", not
      "title" — a third distinct field name for the same concept
      (Greenhouse: "title", Lever: "text", Comeet: "name").
    - department <- position["department"]. Unlike Greenhouse (always None
      at Stage 1) and Lever (company-configurable, often missing), both
      companies checked here populate this cleanly and consistently.
    - location <- position["location"]["name"], a human-readable string
      (e.g. "Airport City/ ToHa, Tel Aviv") — same nested-object-with-a-
      "name"-field shape Greenhouse uses for location.
    - absolute_url <- position["url_active_page"]. Comeet actually returns
      three URL variants per position (url_comeet_hosted_page,
      url_recruit_hosted_page, url_active_page), identical for every
      position checked across both companies this session, so the choice
      couldn't be empirically disambiguated. Picked url_active_page on the
      assumption its name signals "the current canonical URL" (relevant if
      a company later migrates off a comeet.com-hosted page to a custom
      domain) — flagging this as a judgment call, not something the data
      forced, same spirit as Session 3's hostedUrl-vs-applyUrl call for
      Lever.

    Returns an empty list, not an error, if `COMPANY_POSITIONS_DATA` can't
    be found in the page or is an empty array — both AT&T Israel and
    Enlight had real open positions by the time this session actually
    fetched them (the task's premise that both were at zero had gone stale
    between task-writing and execution), so this path is covered by a
    synthetic fixture rather than a captured live response — see
    tests/test_comeet_adapter.py for why that's disclosed rather than
    silently substituted.
    """
    match = _POSITIONS_DATA_PATTERN.search(html)
    if match is None:
        return []

    positions = json.loads(match.group(1))
    jobs = []
    for position in positions:
        location = position.get("location") or {}
        jobs.append(
            {
                "title": position.get("name"),
                "department": position.get("department"),
                "location": location.get("name"),
                "absolute_url": position.get("url_active_page"),
            }
        )
    return jobs
