"""Scan-budget calculator (ADR-0022) — real numbers from usage_log.json,
not a theoretical formula.

Lives in `usage/`, alongside `log.py`, per ARCHITECTURE.md §3's existing
module boundary for scan-run telemetry.
"""

import calendar
from datetime import datetime, timezone

# ADR-0009: GitHub Actions' free tier for a private repo is 2,000
# minutes/month. Passed as a parameter to compute_usage_summary rather
# than hardcoded there, so a public-repo (unlimited) or a changed plan
# doesn't need a code change — but this is the real, current value `run.py`
# actually uses.
FREE_TIER_MONTHLY_MINUTES = 2000

# Session 31: GitHub Actions' billing-cycle reset date depends on Elad's
# personal account's billing cycle, confirmed via research to vary per
# account — NOT safely assumable as the 1st of the calendar month. This is
# the real value `run.py` uses today; same "small, explicit, editable
# constant" pattern as FREE_TIER_MONTHLY_MINUTES above, not a hardcoded
# literal buried in the calculation itself.
#
# Elad: check Settings -> Billing & plans on your real GitHub account for
# the actual reset day and correct this if it isn't 1.
GITHUB_BILLING_RESET_DAY_OF_MONTH = 1


def _next_reset_date(now, reset_day_of_month):
    """The next date on/after `now` that the billing cycle resets.

    Clamps to the real last day of a month when `reset_day_of_month`
    doesn't exist in it (e.g. 31 in a 30-day month, or in February) rather
    than letting naive date arithmetic roll over into the following month.
    If `now` itself is the reset date, that counts as "not yet passed" —
    the reset is today, not overdue.
    """

    def clamped(year, month):
        last_day = calendar.monthrange(year, month)[1]
        return datetime(year, month, min(reset_day_of_month, last_day), tzinfo=now.tzinfo)

    candidate = clamped(now.year, now.month)
    if candidate.date() >= now.date():
        return candidate
    next_month = now.month + 1 if now.month < 12 else 1
    next_year = now.year + 1 if now.month == 12 else now.year
    return clamped(next_year, next_month)


def compute_usage_summary(
    usage_log_entries,
    monthly_cap_minutes,
    now=None,
    reset_day_of_month=GITHUB_BILLING_RESET_DAY_OF_MONTH,
):
    """Compute this calendar month's Actions-minute usage against a cap.

    `usage_log_entries` is whatever `usage.log.load_usage_log()` returns —
    a plain list of {date, duration_minutes, company_count, track} dicts.
    `now` defaults to the real current UTC time; accepted as a parameter
    (not a hard datetime.now() call) so this stays deterministically
    testable, same pattern as `schedule/gate.py`'s `now_utc`.

    Real gap, checked empirically rather than assumed (this session):
    `usage_log.json` today only ever gets an entry from `record_scan_run`,
    which `run.py` only calls when it actually runs — and `run.py` itself
    only runs when `.github/workflows/scan.yml`'s gate-check says yes.
    The workflow's hourly "cheap check-in" skips (ADR-0028's own disclosed
    cost item — real Actions minutes, just not logged anywhere) are NOT
    represented in `usage_log_entries` at all, not because they're being
    filtered out here, but because nothing in this codebase writes them.
    `minutes_used_this_month` below is therefore an accurate sum of
    *logged* minutes, not a complete accounting of every Actions minute
    spent — that gap is surfaced explicitly via `includes_checkin_overhead`
    (always False today) rather than papered over with an estimate. If a
    future session makes the gate-check log a small entry on every skip,
    this function needs no change at all — it would just start summing
    genuinely complete data.

    `percent_used` is not clamped at 100 — going over the cap is exactly
    the useful signal this exists to surface, not an error state to hide.

    `reset_day_of_month` defaults to GITHUB_BILLING_RESET_DAY_OF_MONTH
    (Session 31) — passed as a parameter for the same reason
    `monthly_cap_minutes` is, and injectable independently of `now` so
    tests can hold one fixed while varying the other. `days_until_reset`
    and `reset_day_of_month` are both included in the returned dict so the
    PWA can display them without knowing this module's defaults.
    """
    now = now or datetime.now(timezone.utc)
    current_year_month = (now.year, now.month)

    minutes_used = 0.0
    for entry in usage_log_entries:
        entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
        if (entry_date.year, entry_date.month) == current_year_month:
            minutes_used += entry["duration_minutes"]

    days_until_reset = (_next_reset_date(now, reset_day_of_month).date() - now.date()).days

    return {
        "minutes_used_this_month": minutes_used,
        "minutes_cap": monthly_cap_minutes,
        "percent_used": (minutes_used / monthly_cap_minutes) * 100,
        "includes_checkin_overhead": False,
        "reset_day_of_month": reset_day_of_month,
        "days_until_reset": days_until_reset,
    }
