"""End-to-end CLI run (Session 8): fetch every company in companies.json
concurrently (ADR-0021), filter through RoleLocationFilter, dedup against
prior storage state, log this run's cost (ADR-0022), and print a summary.

This is the first thing that actually ties adapters/, compliance/, core/,
storage/, and usage/ together into one real run — none of those existed
as a single pipeline before this session.
"""

import asyncio
import json
import time
from pathlib import Path

from adapters.comeet import ComeetAdapter
from adapters.custom import CustomAdapter, load_custom_selectors
from adapters.greenhouse import GreenhouseAdapter
from adapters.lever import LeverAdapter
from compliance.agent import ComplianceAgent
from core.dedup import compute_scan_status
from core.filters import RoleLocationFilter
from core.schema import compute_job_id
from storage.db import DEFAULT_DB_PATH, connect, get_known_job_ids, upsert_jobs
from usage.log import DEFAULT_USAGE_LOG_PATH, record_scan_run

REPO_ROOT = Path(__file__).resolve().parent


def load_companies(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["companies"]


def _build_adapter(company, compliance_agent, custom_selectors):
    """Construct the right adapter for one company's `ats` field.

    Returns (adapter, ats_slug) — ats_slug is None for CustomAdapter, whose
    fetch_stage1_jobs ignores it (see adapters/custom.py's docstring).
    """
    ats = company["ats"]
    if ats == "greenhouse":
        return GreenhouseAdapter(compliance_agent, ats_region=company.get("ats_region")), company["ats_slug"]
    if ats == "lever":
        return LeverAdapter(compliance_agent, ats_region=company.get("ats_region")), company["ats_slug"]
    if ats == "comeet":
        return ComeetAdapter(compliance_agent, ats_uid=company["ats_uid"]), company["ats_slug"]
    if ats == "custom":
        config = custom_selectors[company["name"]]
        return CustomAdapter(compliance_agent, config), None
    raise ValueError(f"unknown ats {ats!r} for company {company['name']!r}")


async def fetch_company(company, compliance_agent, custom_selectors):
    """Fetch one company's Stage 1 jobs, isolating failures per company.

    Broad `except Exception` is deliberate here, not laziness: this is a
    per-company isolation boundary in a batch of otherwise-independent
    fetches, and the realistic failure modes are genuinely heterogeneous
    (ComplianceError from a robots.txt block — see Session 7 — network
    errors from httpx, or a parsing error from an unexpected page shape).
    Any one of those must report as that company's failure, never crash
    the whole run and silently drop every other company's results with it.

    Returns {"company": name, "status": "ok"|"error", "jobs": [...], "error": str|None}.
    """
    name = company["name"]
    try:
        adapter, ats_slug = _build_adapter(company, compliance_agent, custom_selectors)
        jobs = await adapter.fetch_stage1_jobs(ats_slug)
        return {"company": name, "status": "ok", "jobs": jobs, "error": None}
    except Exception as exc:
        return {"company": name, "status": "error", "jobs": [], "error": f"{type(exc).__name__}: {exc}"}


def build_summary(fetch_results, role_filter, known_job_ids, run_timestamp):
    """Pure function: given per-company fetch results and prior storage
    state, compute matches (with dedup status) and per-company counts.

    No network, no file I/O — this is exactly what the fixture-based test
    exercises directly, and what a live run also calls after its network
    phase is already done.
    """
    companies_attempted = len(fetch_results)
    companies_failed = [
        {"company": r["company"], "error": r["error"]} for r in fetch_results if r["status"] == "error"
    ]
    companies_succeeded = companies_attempted - len(companies_failed)

    matches = []
    for result in fetch_results:
        if result["status"] != "ok":
            continue
        company = result["company"]
        for job in result["jobs"]:
            match = role_filter.match(job)
            if not match["matched"]:
                continue
            job_id = compute_job_id(company, job["absolute_url"])
            scan_status = compute_scan_status(job_id, known_job_ids)
            matches.append(
                {
                    "job_id": job_id,
                    "company": company,
                    "title": job["title"],
                    "location": job["location"],
                    "role_category": match["role_category"],
                    "matched_tag": match["matched_tag"],
                    "source_url": job["absolute_url"],
                    "scan_status": scan_status,
                    "first_seen_at": run_timestamp,
                    "last_seen_at": run_timestamp,
                }
            )

    new_count = sum(1 for m in matches if m["scan_status"] == "new")
    still_open_count = sum(1 for m in matches if m["scan_status"] == "still_open")

    return {
        "companies_attempted": companies_attempted,
        "companies_succeeded": companies_succeeded,
        "companies_failed": companies_failed,
        "matches": matches,
        "new_count": new_count,
        "still_open_count": still_open_count,
    }


def print_summary(summary):
    """Human-readable console report."""
    print(f"Companies attempted: {summary['companies_attempted']}")
    print(f"Companies succeeded: {summary['companies_succeeded']}")
    print(f"Companies failed: {len(summary['companies_failed'])}")
    for failure in summary["companies_failed"]:
        print(f"  - {failure['company']}: {failure['error']}")

    print()
    print(
        f"Total matches: {len(summary['matches'])} "
        f"(new: {summary['new_count']}, still_open: {summary['still_open_count']})"
    )

    for status in ("new", "still_open"):
        group = [m for m in summary["matches"] if m["scan_status"] == status]
        if not group:
            continue
        print(f"\n-- {status} ({len(group)}) --")
        for m in group:
            print(f"  [{m['company']}] {m['title']} | {m['location']} | {m['source_url']}")


async def run(
    companies_path=REPO_ROOT / "companies.json",
    roles_path=REPO_ROOT / "roles.json",
    locations_path=REPO_ROOT / "locations.json",
    custom_selectors_path=REPO_ROOT / "custom_selectors.json",
    db_path=DEFAULT_DB_PATH,
    usage_log_path=DEFAULT_USAGE_LOG_PATH,
    run_timestamp=None,
):
    run_timestamp = run_timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    companies = load_companies(companies_path)
    role_filter = RoleLocationFilter(roles_path, locations_path)
    custom_selectors = load_custom_selectors(custom_selectors_path)

    start = time.monotonic()
    async with ComplianceAgent() as agent:
        fetch_results = await asyncio.gather(
            *[fetch_company(company, agent, custom_selectors) for company in companies]
        )
    elapsed_seconds = time.monotonic() - start

    conn = connect(db_path)
    known_job_ids = get_known_job_ids(conn)
    summary = build_summary(fetch_results, role_filter, known_job_ids, run_timestamp)
    upsert_jobs(conn, summary["matches"])

    record_scan_run(
        duration_minutes=elapsed_seconds / 60,
        company_count=summary["companies_attempted"],
        track="stable",
        path=usage_log_path,
    )

    print_summary(summary)
    return summary


if __name__ == "__main__":
    asyncio.run(run())
