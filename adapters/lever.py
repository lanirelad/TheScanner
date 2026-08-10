"""Lever ATS adapter — Stage 1 only (ADR-0016).

Empirically confirmed this session (Session 3), rather than assumed from
Greenhouse's shape: Lever's public `/v0/postings/{slug}` endpoint has no
lightweight-vs-full-content mode to choose between. A `content=false`
query param was tried against a live board and made zero difference —
identical byte size, identical keys — to the default response, which
always includes the full description, `descriptionBody`, `lists`, and
`additional` fields for every posting. There is no equivalent of
Greenhouse's `content=true` flag to omit here; unlike Greenhouse, the
network/bandwidth cost of Stage 1 vs. a full fetch is identical on Lever.

This adapter still honors ADR-0016's actual intent (never parse, store, or
pass along full description text past Stage 1): `parse_stage1_jobs` below
extracts only the four Stage 1 fields and discards everything else before
it leaves this module.
"""

from adapters.base import Adapter

POSTINGS_URL_TEMPLATE = "https://{domain}/v0/postings/{slug}"
DEFAULT_DOMAIN = "api.lever.co"

# Region -> API domain (Session 13, ADR-0019 exploratory calls). Confirmed
# live against Mobileye (an EU-hosted Lever board): api.eu.lever.co exists,
# responds 200, and returns byte-for-byte the same shape (categories, text,
# hostedUrl, etc.) as the global api.lever.co domain — unlike Greenhouse,
# Lever's EU region genuinely does get its own API domain. A future region
# just needs one more entry here, no code change.
REGION_DOMAINS = {
    "eu": "api.eu.lever.co",
}


class LeverAdapter(Adapter):
    """Adapter for boards hosted on Lever's public JSON API.

    Implements the same Adapter contract as GreenhouseAdapter (ADR-0018) —
    this is the second real user of that base class, and it held up: the
    only method required is fetch_stage1_jobs(ats_slug), same signature,
    same ComplianceAgent dependency injection, same output shape.
    """

    def __init__(self, compliance_agent, ats_region=None):
        super().__init__(compliance_agent)
        self.ats_region = ats_region

    async def fetch_stage1_jobs(self, ats_slug):
        """Fetch and parse the Stage 1 job list for a Lever board.

        Async (ADR-0021), routed through self.compliance_agent — no direct
        HTTP client call here, per ARCHITECTURE.md section 6.
        """
        domain = REGION_DOMAINS.get(self.ats_region, DEFAULT_DOMAIN)
        url = POSTINGS_URL_TEMPLATE.format(domain=domain, slug=ats_slug)
        response = await self.compliance_agent.fetch(url)
        return parse_stage1_jobs(response.json())


def parse_stage1_jobs(raw_response_json):
    """Convert Lever's raw postings list into the Stage 1 shape.

    Pure function, no network — same pattern as
    adapters.greenhouse.parse_stage1_jobs, so fixture-based tests never
    need a live request (ADR-0006).

    Field mapping decisions, each confirmed against real Palantir/Smarsh
    data rather than assumed:

    - title <- job["text"]. Lever's posting title field is called "text",
      not "title" — easy to get wrong by assumption.
    - location <- job["categories"]["location"]. This is a single
      canonical string present on every posting observed from both
      companies (there's also an "allLocations" list for postings spanning
      multiple offices, not used here since RoleLocationFilter only checks
      one location string per job, same as it does for Greenhouse).
    - department <- job["categories"].get("department"). Lever's
      "categories" object is company-configurable, not a fixed schema:
      Palantir's postings have no "department" key at all (only
      commitment/location/team/allLocations), while Smarsh's do. So this
      is best-effort and often None here too — same expected-not-a-bug
      situation as Greenhouse's department field (see
      adapters/greenhouse.py's _first_department_name).
    - absolute_url <- job["hostedUrl"], not job["applyUrl"]. hostedUrl is
      the public posting page (matches Greenhouse's absolute_url, which
      also points at the posting, not straight into an application form).
      applyUrl skips directly to Lever's application form — flagging this
      choice explicitly since it's a judgment call about what "the
      posting's URL" means, not an empirically forced answer.
    """
    jobs = []
    for job in raw_response_json:
        categories = job.get("categories") or {}
        jobs.append(
            {
                "title": job.get("text"),
                "department": categories.get("department"),
                "location": categories.get("location"),
                "absolute_url": job.get("hostedUrl"),
            }
        )
    return jobs
