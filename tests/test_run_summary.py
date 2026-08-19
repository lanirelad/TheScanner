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
from run import _role_label, build_latest_scan_export, build_summary, print_summary, write_json_file

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
    # Exactly these eight fields — no matched_tag, first_seen_at/
    # last_seen_at (internal bookkeeping), and definitely no
    # application_status (ADR-0011/ADR-0014, device-local only, never
    # written by the backend). label_en (Session 17) rides alongside
    # role_category as the display string the UI should actually show.
    # job_id (Session 28) is the one internal field that DOES ship — the
    # PWA's mark-as-applied feature needs a stable per-job key to store
    # application_status against in the device's own local storage.
    assert set(match.keys()) == {
        "job_id", "company", "title", "location", "role_category", "label_en", "source_url", "scan_status"
    }
    assert match == {
        "job_id": compute_job_id("Wiz", "https://example.com/1"),
        "company": "Wiz",
        "title": "DevOps Engineer",
        "location": "Tel Aviv",
        "role_category": "devops",
        "label_en": "DevOps Engineer",
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


# --- Failure visibility (Session 18) -----------------------------------


def test_latest_scan_export_carries_a_failures_list_with_real_error_text():
    # Elad's real complaint: a bare "failed" count in the console/export
    # gave no way to see *why* a company failed short of the Actions log.
    # A synthetic ReadTimeout-shaped message must survive intact into the
    # export, not get flattened away like companies_failed already is.
    fetch_results = [
        {"company": "Wiz", "status": "ok", "jobs": [], "error": None},
        {
            "company": "Palantir Technologies",
            "status": "error",
            "jobs": [],
            "error": "ReadTimeout: The read operation timed out",
        },
    ]
    summary = build_summary(fetch_results, _role_filter(), known_job_ids=set(), run_timestamp="2026-08-09T00:00:00Z")

    export = build_latest_scan_export(summary, generated_at="2026-08-09T00:00:00Z")

    assert export["failures"] == [
        {"company": "Palantir Technologies", "error": "ReadTimeout: The read operation timed out"}
    ]


def test_latest_scan_export_failures_list_is_empty_when_nothing_failed():
    fetch_results = [{"company": "Wiz", "status": "ok", "jobs": [], "error": None}]
    summary = build_summary(fetch_results, _role_filter(), known_job_ids=set(), run_timestamp="2026-08-09T00:00:00Z")

    export = build_latest_scan_export(summary, generated_at="2026-08-09T00:00:00Z")

    assert export["failures"] == []


def test_print_summary_prints_the_real_error_message_per_failure(capsys):
    fetch_results = [
        {
            "company": "Palantir Technologies",
            "status": "error",
            "jobs": [],
            "error": "ReadTimeout: The read operation timed out",
        }
    ]
    summary = build_summary(fetch_results, _role_filter(), known_job_ids=set(), run_timestamp="2026-08-09T00:00:00Z")

    print_summary(summary)

    captured = capsys.readouterr()
    assert "[Palantir Technologies] FAILED — ReadTimeout: The read operation timed out" in captured.out


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


# --- _role_label (Session 17) -----------------------------------------------


def test_role_label_returns_label_en_for_a_known_category():
    assert _role_label(_role_filter(), "technical_support") == "Technical Support Engineer"


def test_role_label_falls_back_to_raw_key_for_an_unknown_category():
    # Fail-safe, not a crash: a scan run shouldn't blow up over a
    # roles.json edit that removes a category label_en was expecting.
    assert _role_label(_role_filter(), "made_up_category") == "made_up_category"
