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
from usage.budget import FREE_TIER_MONTHLY_MINUTES, compute_usage_summary
from usage.log import DEFAULT_USAGE_LOG_PATH, load_usage_log, record_scan_run

REPO_ROOT = Path(__file__).resolve().parent

# Session 15: these two now live inside pwa/ (wrangler.jsonc's
# assets.directory), not the repo root Session 14 originally used. Cloudflare
# Workers-with-static-assets snapshots assets.directory at deploy time, and
# the Git-integration flow redeploys on every push to the watched branch —
# since .github/workflows/scan.yml pushes its own commit after every real
# scan, putting these two files inside pwa/ is what makes that push also
# refresh the *deployed* data, not just the repo's data. Outside pwa/, the
# PWA could never fetch() them at all once deployed (a static-assets
# deployment only serves what's inside assets.directory — nothing else in
# the repo is reachable over HTTP).
DEFAULT_LATEST_SCAN_PATH = REPO_ROOT / "pwa" / "latest_scan.json"
DEFAULT_USAGE_SUMMARY_PATH = REPO_ROOT / "pwa" / "usage_summary.json"


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


def _role_label(role_filter, role_category):
    """Display label for a matched role category (Session 17).

    `roles.json`'s `label_en` field exists specifically for this — proper
    capitalization/spacing ("Technical Support Engineer"), not a generic
    underscore-to-space transform on the raw key ("technical_support").
    Reads `role_filter.roles_config` directly rather than changing
    `RoleLocationFilter.match()`'s return shape: `match()` already has
    broad test coverage asserting its exact `{matched, role_category,
    matched_tag}` shape across every adapter's test file, and this label
    is a display concern for the summary/export layer, not the matching
    logic itself. Falls back to the raw key if `label_en` is ever missing
    — same fail-safe spirit as the rest of this project, not a reason to
    crash a scan run over a config oversight.
    """
    return role_filter.roles_config.get(role_category, {}).get("label_en", role_category)


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
                    "label_en": _role_label(role_filter, match["role_category"]),
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


def build_latest_scan_export(summary, generated_at):
    """Shape this run's summary into the flat JSON a future PWA will
    `fetch()` directly — no database driver needed client-side.

    Pure function, no I/O — deliberately excludes `application_status`
    (ADR-0011/ADR-0014: device-local only, never written by the backend)
    and every internal bookkeeping field a client doesn't need to render
    a job list (`job_id`, `matched_tag`, `first_seen_at`/`last_seen_at` —
    `scan_status` already captures what those two mean for display).
    `companies_failed` is flattened to a count here, not the per-company
    error list `build_summary` keeps internally — a client rendering a
    job list has no use for adapter exception text.

    `label_en` (Session 17) rides alongside `role_category` rather than
    replacing it: `role_category` is still the stable key (useful for
    future client-side filtering by category), `label_en` is purely the
    human-readable string the UI should actually display.
    """
    return {
        "generated_at": generated_at,
        "companies_attempted": summary["companies_attempted"],
        "companies_succeeded": summary["companies_succeeded"],
        "companies_failed": len(summary["companies_failed"]),
        "matches": [
            {
                "company": m["company"],
                "title": m["title"],
                "location": m["location"],
                "role_category": m["role_category"],
                "label_en": m["label_en"],
                "source_url": m["source_url"],
                "scan_status": m["scan_status"],
            }
            for m in summary["matches"]
        ],
    }


def write_json_file(data, path):
    """Shared plain-JSON writer for latest_scan.json/usage_summary.json —
    both are meant to be read directly by a future browser client, so
    kept as plain, flat, human-readable JSON rather than anything
    Python-specific.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
    latest_scan_path=DEFAULT_LATEST_SCAN_PATH,
    usage_summary_path=DEFAULT_USAGE_SUMMARY_PATH,
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

    write_json_file(build_latest_scan_export(summary, run_timestamp), latest_scan_path)

    # Recomputed and rewritten on every real run of this function, not
    # cached or computed once — a gate-check-only skip (the workflow's
    # hourly cheap check-in) never reaches this line at all, so
    # usage_summary.json simply doesn't change during a stretch of those;
    # the next real run recomputes it fresh from the complete, current
    # usage_log.json, which is what keeps it accurate rather than stale.
    usage_summary = compute_usage_summary(load_usage_log(usage_log_path), FREE_TIER_MONTHLY_MINUTES)
    write_json_file(usage_summary, usage_summary_path)

    print_summary(summary)
    return summary


if __name__ == "__main__":
    asyncio.run(run())
