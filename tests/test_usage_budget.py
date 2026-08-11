"""Tests for usage/budget.py's compute_usage_summary (ADR-0022, Session 14).

Pure function, no file/network dependency in the test itself — entries are
injected directly, same pattern as schedule/gate.py's tests.
"""

from datetime import datetime, timezone

from usage.budget import compute_usage_summary

AUGUST_9 = datetime(2026, 8, 9, tzinfo=timezone.utc)


def test_fresh_month_with_no_entries_is_zero_percent():
    summary = compute_usage_summary([], monthly_cap_minutes=2000, now=AUGUST_9)

    assert summary == {
        "minutes_used_this_month": 0.0,
        "minutes_cap": 2000,
        "percent_used": 0.0,
        "includes_checkin_overhead": False,
    }


def test_only_current_month_entries_are_counted_across_a_month_boundary():
    entries = [
        {"date": "2026-07-31", "duration_minutes": 100.0, "company_count": 9, "track": "stable"},  # July — excluded
        {"date": "2026-08-01", "duration_minutes": 10.0, "company_count": 9, "track": "stable"},  # August — included
        {"date": "2026-08-09", "duration_minutes": 5.0, "company_count": 9, "track": "stable"},  # August — included
    ]

    summary = compute_usage_summary(entries, monthly_cap_minutes=2000, now=AUGUST_9)

    assert summary["minutes_used_this_month"] == 15.0


def test_percent_used_over_cap_is_not_clamped():
    # Going over the cap is the useful signal, not an error state to hide.
    entries = [{"date": "2026-08-01", "duration_minutes": 2500.0, "company_count": 9, "track": "stable"}]

    summary = compute_usage_summary(entries, monthly_cap_minutes=2000, now=AUGUST_9)

    assert summary["minutes_used_this_month"] == 2500.0
    assert summary["percent_used"] == 125.0


def test_includes_checkin_overhead_is_always_false_today():
    # Checked empirically this session, not assumed: usage_log.json only
    # ever gets entries from record_scan_run, which only runs when the
    # workflow's gate-check says yes — the hourly cheap-check-in skips are
    # real Actions minutes (ADR-0028) but are never logged anywhere. This
    # flag exists so that gap is visible in usage_summary.json itself,
    # not just buried in a code comment.
    summary = compute_usage_summary(
        [{"date": "2026-08-01", "duration_minutes": 1.0, "company_count": 9, "track": "stable"}],
        monthly_cap_minutes=2000,
        now=AUGUST_9,
    )
    assert summary["includes_checkin_overhead"] is False


def test_entries_from_a_different_year_same_month_are_excluded():
    # Guards against a naive "just compare month number" bug that would
    # incorrectly count August 2025 toward August 2026.
    entries = [{"date": "2025-08-09", "duration_minutes": 999.0, "company_count": 9, "track": "stable"}]

    summary = compute_usage_summary(entries, monthly_cap_minutes=2000, now=AUGUST_9)

    assert summary["minutes_used_this_month"] == 0.0
