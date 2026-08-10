"""Greenhouse ATS adapter — Stage 1 only (ADR-0016).

Stage 1 is the cheap, lightweight job list: title, department, location,
and the application URL — no full description. That keeps the per-company
fetch cost to a single request regardless of how many roles a company has
open.
"""

from adapters.base import Adapter

JOBS_URL_TEMPLATE = "https://{domain}/v1/boards/{slug}/jobs"
DEFAULT_DOMAIN = "boards-api.greenhouse.io"

# Region -> API domain (Session 13, ADR-0019 exploratory calls). Deliberately
# empty today: Greenhouse's EU data-residency setting was verified live
# (Optimove, an EU-hosted board) to affect only the public *page* domain
# (job-boards.eu.greenhouse.io) — the read-only JSON API is served from the
# same global boards-api.greenhouse.io domain regardless of region. A
# boards-api.eu.greenhouse.io domain does not exist (confirmed: DNS doesn't
# resolve it). Adding an "eu" entry pointing there would break every
# EU-hosted company, not fix anything. A future region that genuinely does
# get its own Greenhouse API domain just needs one line added here — no
# code change — same mechanism Lever's REGION_DOMAINS below already uses.
REGION_DOMAINS = {}


class GreenhouseAdapter(Adapter):
    """Adapter for boards hosted on Greenhouse's public JSON API.

    Implements the Adapter contract (adapters/base.py, ADR-0018) so Lever/
    Comeet adapters (later sessions) follow the same shape.
    """

    def __init__(self, compliance_agent, ats_region=None):
        super().__init__(compliance_agent)
        self.ats_region = ats_region

    async def fetch_stage1_jobs(self, ats_slug):
        """Fetch and parse the Stage 1 job list for a Greenhouse board.

        Async (ADR-0021) — the fetch is routed through
        `self.compliance_agent`, no direct HTTP client call here, per
        ARCHITECTURE.md §6. `content=true` is deliberately never passed:
        that would pull full descriptions for every open role at every
        company, which is exactly the wasted cost ADR-0016's two-stage
        fetch exists to avoid. `parse_stage1_jobs` itself stays a plain
        synchronous function — there's no I/O in it, only async where
        network is actually involved.
        """
        domain = REGION_DOMAINS.get(self.ats_region, DEFAULT_DOMAIN)
        url = JOBS_URL_TEMPLATE.format(domain=domain, slug=ats_slug)
        response = await self.compliance_agent.fetch(url)
        return parse_stage1_jobs(response.json())


def parse_stage1_jobs(raw_response_json):
    """Convert a raw Greenhouse `/jobs` response into the Stage 1 shape.

    Pure function, no network and no dependency on ComplianceAgent — this
    is what fixture-based tests call directly so they never need a live
    request (ADR-0006).
    """
    jobs = []
    for job in raw_response_json.get("jobs", []):
        location = job.get("location") or {}
        jobs.append(
            {
                "title": job.get("title"),
                "department": _first_department_name(job),
                "location": location.get("name"),
                "absolute_url": job.get("absolute_url"),
            }
        )
    return jobs


def _first_department_name(job):
    # Confirmed against live data (Session 1 smoke test): Greenhouse's
    # lightweight /jobs endpoint doesn't actually include a `departments`
    # field without content=true, so this is None for essentially every
    # job today. Kept as a field anyway since some boards do populate it,
    # and Stage 2 work shouldn't have to add it later.
    departments = job.get("departments") or []
    if departments:
        return departments[0].get("name")
    return None
