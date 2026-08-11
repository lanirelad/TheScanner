"""Scan-budget usage log (ADR-0022).

Self-tracked instead of querying GitHub's billing API — see ADR-0022 for
why (mainly: no new credentials needed, and it's exactly as accurate for
projecting from real observed run durations). One entry is appended per
completed scan run; never overwritten, so a monthly total and a
frequency/scale projection can both be computed from the same file later.

Lives in its own `usage/` package, parallel to adapters/core/compliance/
storage (ARCHITECTURE.md §3, §13): scan-run telemetry is a distinct
concern from `storage/`'s job-posting data (scoped by ADR-0003), so
keeping them separate means this module's eventual reader/projection
logic can't accidentally end up reasoning about job data, and vice versa.
"""

import json
import time
from pathlib import Path

# usage_log.json itself stays at the repo root, alongside robots_cache.json
# and the eventual scan results — this module's code lives one level
# deeper in usage/, but the data file it manages does not.
DEFAULT_USAGE_LOG_PATH = Path(__file__).resolve().parent.parent / "usage_log.json"


def load_usage_log(path=DEFAULT_USAGE_LOG_PATH):
    """Read every entry currently in the usage log.

    Returns an empty list if the file doesn't exist yet or is unreadable
    — same fallback `record_scan_run` already relied on internally, now
    shared so `usage/budget.py`'s summarizer doesn't have to duplicate it.
    """
    path = Path(path)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def record_scan_run(duration_minutes, company_count, track="stable", path=DEFAULT_USAGE_LOG_PATH, date=None):
    """Append one entry for a completed scan run.

    `track` is "stable" for every run today — the full-sweep/onboarding
    track (ADR-0020) doesn't exist yet, but the field is included now so
    this log's shape doesn't need a breaking change once it does.

    `date` defaults to today's UTC date if not given; accepting it as a
    parameter (rather than always computing it internally) keeps this
    function easy to test deterministically.

    Returns the entry that was written.
    """
    path = Path(path)
    entries = load_usage_log(path)

    entry = {
        "date": date or time.strftime("%Y-%m-%d", time.gmtime()),
        "duration_minutes": duration_minutes,
        "company_count": company_count,
        "track": track,
    }
    entries.append(entry)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)

    return entry
