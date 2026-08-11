"""Scan-budget calculator (ADR-0022) — real numbers from usage_log.json,
not a theoretical formula.

Lives in `usage/`, alongside `log.py`, per ARCHITECTURE.md §3's existing
module boundary for scan-run telemetry.
"""

from datetime import datetime, timezone

# ADR-0009: GitHub Actions' free tier for a private repo is 2,000
# minutes/month. Passed as a parameter to compute_usage_summary rather
# than hardcoded there, so a public-repo (unlimited) or a changed plan
# doesn't need a code change — but this is the real, current value `run.py`
# actually uses.
FREE_TIER_MONTHLY_MINUTES = 2000


def compute_usage_summary(usage_log_entries, monthly_cap_minutes, now=None):
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
    """
    now = now or datetime.now(timezone.utc)
    current_year_month = (now.year, now.month)

    minutes_used = 0.0
    for entry in usage_log_entries:
        entry_date = datetime.strptime(entry["date"], "%Y-%m-%d")
        if (entry_date.year, entry_date.month) == current_year_month:
            minutes_used += entry["duration_minutes"]

    return {
        "minutes_used_this_month": minutes_used,
        "minutes_cap": monthly_cap_minutes,
        "percent_used": (minutes_used / monthly_cap_minutes) * 100,
        "includes_checkin_overhead": False,
    }
