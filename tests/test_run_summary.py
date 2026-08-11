"""Fixture-based test for run.py's build_summary() — the CLI run's
counting/grouping logic. No network, no adapters, no real fetches: this
exercises exactly the pure function a live run also calls once its
network phase is already done, with synthetic fetch_results standing in
for what fetch_company() would have returned.
"""

import json
from pathlib import Path

from core.filters import RoleLocationFilter
from core.schema import compute_job_id
from run import build_latest_scan_export, build_summary, write_json_file

REPO_ROOT = Path(__file__).resolve().parent.parent


def _role_filter():
    return RoleLocationFilter(REPO_ROOT / "roles.json", REPO_ROOT / "locations.json")


def _job(title, location, absolute_url, department=None):
    return {"title": title, "department": department, "location": location, "absolute_url": absolute_url}


def test_companies_attempted_succeeded_and_failed_are_counted_independently():
    # One company's failure must not affect another's outcome or count.
    fetch_results = [
        {"company": "Wiz", "status": "ok", "jobs": [], "error": None},
        {"company": "BrokenCo", "status": "error", "jobs": [], "error": "ComplianceError: robots.txt disallows fetching ..."},
        {"company": "Playtika", "status": "ok", "jobs": [], "error": None},
    ]

    summary = build_summary(fetch_results, _role_filter(), known_job_ids=set(), run_timestamp="2026-08-09T00:00:00Z")

    assert summary["companies_attempted"] == 3
    assert summary["companies_succeeded"] == 2
    assert summary["companies_failed"] == [{"company": "BrokenCo", "error": "ComplianceError: robots.txt disallows fetching ..."}]


def test_only_matching_jobs_from_successful_companies_are_included():
    fetch_results = [
        {
            "company": "Wiz",
            "status": "ok",
            "jobs": [
                _job("DevOps Engineer", "Tel Aviv", "https://example.com/wiz/1"),  # matches
                _job("Executive Assistant", "Tel Aviv", "https://example.com/wiz/2"),  # no tag match
                _job("DevOps Engineer", "Washington, D.C.", "https://example.com/wiz/3"),  # no location match
            ],
            "error": None,
        },
        {
            "company": "BrokenCo",
            "status": "error",
            "jobs": [_job("DevOps Engineer", "Tel Aviv", "https://example.com/broken/1")],  # must be ignored
            "error": "some fetch error",
        },
    ]

    summary = build_summary(fetch_results, _role_filter(), known_job_ids=set(), run_timestamp="2026-08-09T00:00:00Z")

    assert len(summary["matches"]) == 1
    match = summary["matches"][0]
    assert match["company"] == "Wiz"
    assert match["title"] == "DevOps Engineer"
    assert match["role_category"] == "devops"
    assert match["source_url"] == "https://example.com/wiz/1"


def test_new_vs_still_open_split_matches_known_job_ids():
    already_known_url = "https://example.com/wiz/already-known"
    new_url = "https://example.com/wiz/brand-new"
    already_known_id = compute_job_id("Wiz", already_known_url)

    fetch_results = [
        {
            "company": "Wiz",
            "status": "ok",
            "jobs": [
                _job("DevOps Engineer", "Tel Aviv", already_known_url),
                _job("Site Reliability Engineer", "Tel Aviv", new_url),
            ],
            "error": None,
        }
    ]

    summary = build_summary(
        fetch_results, _role_filter(), known_job_ids={already_known_id}, run_timestamp="2026-08-09T00:00:00Z"
    )

    assert summary["new_count"] == 1
    assert summary["still_open_count"] == 1
    statuses_by_url = {m["source_url"]: m["scan_status"] for m in summary["matches"]}
    assert statuses_by_url[already_known_url] == "still_open"
    assert statuses_by_url[new_url] == "new"


def test_run_timestamp_is_used_for_first_and_last_seen_on_new_matches():
    fetch_results = [
        {"company": "Wiz", "status": "ok", "jobs": [_job("DevOps Engineer", "Tel Aviv", "https://example.com/1")], "error": None}
    ]

    summary = build_summary(fetch_results, _role_filter(), known_job_ids=set(), run_timestamp="2026-08-09T00:00:00Z")

    match = summary["matches"][0]
    assert match["first_seen_at"] == "2026-08-09T00:00:00Z"
    assert match["last_seen_at"] == "2026-08-09T00:00:00Z"


def test_no_matches_and_no_failures_summarizes_cleanly():
    fetch_results = [{"company": "Wiz", "status": "ok", "jobs": [], "error": None}]

    summary = build_summary(fetch_results, _role_filter(), known_job_ids=set(), run_timestamp="2026-08-09T00:00:00Z")

    assert summary["companies_attempted"] == 1
    assert summary["companies_succeeded"] == 1
    assert summary["companies_failed"] == []
    assert summary["matches"] == []
    assert summary["new_count"] == 0
    assert summary["still_open_count"] == 0


# --- build_latest_scan_export (Session 14) ----------------------------------


def test_latest_scan_export_shape_excludes_internal_and_device_local_fields():
    fetch_results = [
        {"company": "Wiz", "status": "ok", "jobs": [_job("DevOps Engineer", "Tel Aviv", "https://example.com/1")], "error": None}
    ]
    summary = build_summary(fetch_results, _role_filter(), known_job_ids=set(), run_timestamp="2026-08-09T00:00:00Z")

    export = build_latest_scan_export(summary, generated_at="2026-08-09T00:00:00Z")

    assert export["generated_at"] == "2026-08-09T00:00:00Z"
    assert export["companies_attempted"] == 1
    assert export["companies_succeeded"] == 1
    assert export["companies_failed"] == 0
    assert len(export["matches"]) == 1
    match = export["matches"][0]
    # Exactly these six fields — no job_id, matched_tag, first_seen_at/
    # last_seen_at (internal bookkeeping), and definitely no
    # application_status (ADR-0011/ADR-0014, device-local only, never
    # written by the backend).
    assert set(match.keys()) == {"company", "title", "location", "role_category", "source_url", "scan_status"}
    assert match == {
        "company": "Wiz",
        "title": "DevOps Engineer",
        "location": "Tel Aviv",
        "role_category": "devops",
        "source_url": "https://example.com/1",
        "scan_status": "new",
    }


def test_latest_scan_export_companies_failed_is_a_count_not_the_error_list():
    fetch_results = [
        {"company": "Wiz", "status": "ok", "jobs": [], "error": None},
        {"company": "BrokenCo", "status": "error", "jobs": [], "error": "some fetch error"},
    ]
    summary = build_summary(fetch_results, _role_filter(), known_job_ids=set(), run_timestamp="2026-08-09T00:00:00Z")

    export = build_latest_scan_export(summary, generated_at="2026-08-09T00:00:00Z")

    assert export["companies_failed"] == 1
    assert isinstance(export["companies_failed"], int)


def test_latest_scan_export_is_json_serializable():
    fetch_results = [
        {"company": "Wiz", "status": "ok", "jobs": [_job("DevOps Engineer", "Tel Aviv", "https://example.com/1")], "error": None}
    ]
    summary = build_summary(fetch_results, _role_filter(), known_job_ids=set(), run_timestamp="2026-08-09T00:00:00Z")

    export = build_latest_scan_export(summary, generated_at="2026-08-09T00:00:00Z")

    round_tripped = json.loads(json.dumps(export, ensure_ascii=False))
    assert round_tripped == export


def test_write_json_file_round_trips(tmp_path):
    path = tmp_path / "out.json"
    data = {"a": 1, "b": [1, 2, 3]}

    write_json_file(data, path)

    assert json.loads(path.read_text(encoding="utf-8")) == data
