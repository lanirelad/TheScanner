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
        "reset_day_of_month": 1,
        "days_until_reset": 23,  # August 9 -> September 1
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


# --- days_until_reset (Session 31, ADR pending) --------------------------
# GitHub's real billing-cycle reset day varies per account (confirmed via
# research, not assumed) — reset_day_of_month is a parameter precisely so
# it never has to be. These pin down the two tricky cases: today being the
# reset day itself, and a reset day that doesn't exist in every month.


def test_days_until_reset_defaults_to_the_1st():
    summary = compute_usage_summary([], monthly_cap_minutes=2000, now=AUGUST_9)

    assert summary["reset_day_of_month"] == 1
    assert summary["days_until_reset"] == 23  # Aug 9 -> Sep 1


def test_days_until_reset_is_zero_when_today_is_the_reset_day():
    now = datetime(2026, 8, 1, tzinfo=timezone.utc)

    summary = compute_usage_summary([], monthly_cap_minutes=2000, now=now, reset_day_of_month=1)

    assert summary["days_until_reset"] == 0


def test_days_until_reset_counts_forward_to_a_mid_month_reset_day():
    now = datetime(2026, 8, 9, tzinfo=timezone.utc)

    summary = compute_usage_summary([], monthly_cap_minutes=2000, now=now, reset_day_of_month=15)

    assert summary["days_until_reset"] == 6


def test_days_until_reset_rolls_over_when_the_reset_day_already_passed_this_month():
    now = datetime(2026, 8, 20, tzinfo=timezone.utc)

    summary = compute_usage_summary([], monthly_cap_minutes=2000, now=now, reset_day_of_month=15)

    assert summary["days_until_reset"] == 26  # Aug 20 -> Sep 15


def test_days_until_reset_clamps_to_the_real_last_day_of_a_short_month():
    # February 2026 has 28 days — reset_day_of_month=31 must clamp to
    # Feb 28, not silently roll into March via naive date construction.
    now = datetime(2026, 2, 20, tzinfo=timezone.utc)

    summary = compute_usage_summary([], monthly_cap_minutes=2000, now=now, reset_day_of_month=31)

    assert summary["days_until_reset"] == 8  # Feb 20 -> Feb 28
