"""Tests for schedule/gate.py's should_run_full_scan (ADR-0028).

Pure function, no I/O, no live calls — every "current time" is injected
explicitly so this stays deterministic.
"""

from datetime import datetime, timezone

from schedule.gate import should_run_full_scan

SCHEDULED_CONFIG = {"mode": "scheduled", "scans_per_day": 2, "times_utc": ["06:00", "18:00"]}
ON_DEMAND_CONFIG = {"mode": "on_demand", "scans_per_day": 0, "times_utc": []}


def _utc(hour, minute, day=9):
    return datetime(2026, 8, day, hour, minute, tzinfo=timezone.utc)


def test_schedule_trigger_at_exact_scheduled_time_runs():
    assert should_run_full_scan("schedule", SCHEDULED_CONFIG, now_utc=_utc(6, 0)) is True


def test_schedule_trigger_within_tolerance_of_scheduled_time_runs():
    assert should_run_full_scan("schedule", SCHEDULED_CONFIG, now_utc=_utc(6, 4)) is True
    assert should_run_full_scan("schedule", SCHEDULED_CONFIG, now_utc=_utc(17, 51)) is True  # 9 min before 18:00


def test_schedule_trigger_well_outside_any_scheduled_time_skips():
    assert should_run_full_scan("schedule", SCHEDULED_CONFIG, now_utc=_utc(12, 0)) is False


def test_schedule_trigger_just_outside_tolerance_skips():
    assert should_run_full_scan("schedule", SCHEDULED_CONFIG, now_utc=_utc(6, 15)) is False


def test_on_demand_mode_always_skips_scheduled_trigger_even_at_a_configured_time():
    assert should_run_full_scan("schedule", ON_DEMAND_CONFIG, now_utc=_utc(6, 0)) is False


def test_manual_trigger_always_runs_regardless_of_config():
    assert should_run_full_scan("workflow_dispatch", SCHEDULED_CONFIG, now_utc=_utc(12, 0)) is True
    assert should_run_full_scan("workflow_dispatch", ON_DEMAND_CONFIG, now_utc=_utc(12, 0)) is True


def test_midnight_wraparound_is_handled():
    config = {"mode": "scheduled", "scans_per_day": 1, "times_utc": ["00:00"]}
    assert should_run_full_scan("schedule", config, now_utc=_utc(23, 55)) is True
    assert should_run_full_scan("schedule", config, now_utc=_utc(0, 5)) is True
    assert should_run_full_scan("schedule", config, now_utc=_utc(12, 0)) is False


def test_missing_mode_key_defaults_to_not_running():
    assert should_run_full_scan("schedule", {"times_utc": ["06:00"]}, now_utc=_utc(6, 0)) is False


def test_custom_tolerance_is_respected():
    assert should_run_full_scan("schedule", SCHEDULED_CONFIG, now_utc=_utc(6, 20), tolerance_minutes=30) is True
