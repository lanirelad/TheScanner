"""Tests for the scan-budget usage log writer (ADR-0022)."""

import json

from usage.log import load_usage_log, record_scan_run


def test_record_scan_run_appends_without_overwriting(tmp_path):
    path = tmp_path / "usage_log.json"

    first = record_scan_run(duration_minutes=2.5, company_count=4, path=path, date="2026-08-08")
    second = record_scan_run(duration_minutes=3.1, company_count=4, path=path, date="2026-08-09")

    entries = json.loads(path.read_text(encoding="utf-8"))
    assert entries == [first, second]
    assert first == {
        "date": "2026-08-08",
        "duration_minutes": 2.5,
        "company_count": 4,
        "track": "stable",
    }


def test_record_scan_run_defaults_track_to_stable(tmp_path):
    path = tmp_path / "usage_log.json"

    entry = record_scan_run(duration_minutes=1.0, company_count=2, path=path, date="2026-08-08")

    assert entry["track"] == "stable"


def test_record_scan_run_supports_full_sweep_track_for_future_use(tmp_path):
    # The full-sweep/onboarding track (ADR-0020) isn't built yet, but the
    # log format must already accept it without a schema change later.
    path = tmp_path / "usage_log.json"

    entry = record_scan_run(duration_minutes=90.0, company_count=8500, track="full-sweep", path=path, date="2026-08-08")

    assert entry["track"] == "full-sweep"


def test_load_usage_log_returns_empty_list_when_file_does_not_exist(tmp_path):
    assert load_usage_log(tmp_path / "does_not_exist.json") == []


def test_load_usage_log_reads_back_what_record_scan_run_wrote(tmp_path):
    path = tmp_path / "usage_log.json"
    record_scan_run(duration_minutes=1.0, company_count=4, path=path, date="2026-08-08")
    record_scan_run(duration_minutes=2.0, company_count=4, path=path, date="2026-08-09")

    entries = load_usage_log(path)

    assert len(entries) == 2
    assert [e["duration_minutes"] for e in entries] == [1.0, 2.0]
