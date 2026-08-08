"""Schedule gate-check logic (ADR-0028).

Own small package, not folded into `core/` (canonical schema/dedup/keyword
filter — none of which this is) or anywhere else: same reasoning
ARCHITECTURE.md §13 already applied to `usage/` for scan-run telemetry —
a distinct cross-cutting concern gets its own module rather than being
wedged into an existing one it doesn't really belong to.

The workflow's registered cron trigger stays fixed and cheap (e.g. hourly)
— that is NOT the real scan schedule. The real schedule lives entirely in
`schedule_config.json` and can change without ever touching the workflow
file. This module is what actually reads that config and decides whether
a given check-in should run a full scan or exit at near-zero cost.
"""

from datetime import datetime, timezone

DEFAULT_TOLERANCE_MINUTES = 10
MINUTES_PER_DAY = 24 * 60


def _parse_hhmm(value):
    hours, minutes = value.split(":")
    return int(hours), int(minutes)


def _minutes_since_midnight(hour, minute):
    return hour * 60 + minute


def should_run_full_scan(trigger, config, now_utc=None, tolerance_minutes=DEFAULT_TOLERANCE_MINUTES):
    """Decide whether this workflow check-in should run a full scan.

    `trigger` is "workflow_dispatch" (the manual "Run now" button) or
    "schedule" (the workflow's own frequent, fixed cron check-in) — these
    match GitHub Actions' own `github.event_name` values exactly, so the
    workflow can pass that straight through with no translation.

    `config` is schedule_config.json's parsed contents.

    `now_utc` defaults to the real current UTC time; accepted as a
    parameter (not computed internally as a hard default) so this stays
    deterministically unit-testable without any wall-clock dependency.

    A manual trigger always runs, regardless of config — explicit human
    intent overrides the schedule. A scheduled check-in only runs a full
    scan if `config["mode"] == "scheduled"` AND the current time falls
    within `tolerance_minutes` of one of `config["times_utc"]`;
    `mode == "on_demand"` always skips scheduled check-ins, leaving only
    the manual button as a way to run a scan at all.

    The tolerance window exists because GitHub Actions' cron scheduling
    isn't guaranteed to fire at the exact minute requested (documented
    platform behavior, especially under load) — an exact-minute-only
    comparison would risk silently never matching.
    """
    if trigger == "workflow_dispatch":
        return True

    if config.get("mode") != "scheduled":
        return False

    now_utc = now_utc or datetime.now(timezone.utc)
    now_minutes = _minutes_since_midnight(now_utc.hour, now_utc.minute)

    for time_str in config.get("times_utc", []):
        hour, minute = _parse_hhmm(time_str)
        scheduled_minutes = _minutes_since_midnight(hour, minute)
        diff = abs(now_minutes - scheduled_minutes)
        diff = min(diff, MINUTES_PER_DAY - diff)  # midnight wraparound
        if diff <= tolerance_minutes:
            return True

    return False
