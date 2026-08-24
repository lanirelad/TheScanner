"""Resumable harvesting checkpoint (Session 39).

Real incident this exists to prevent: Session 38's Wikipedia-list
research was delegated to a background agent that hit an org spend
limit partway through and returned nothing usable — none of its
partial progress survived anywhere. Separately, Session 37/38's own
per-candidate dispositions (added / confirmed-unscannable / checked-
but-genuinely-unresolved / not yet touched) only ever lived in prose
inside PROGRESS.md and `companies.json`'s own per-company `note`
fields — real, but not something a future session could mechanically
resume from without re-reading and re-deriving it from scratch every
time.

`harvesting_checkpoint.json` (repo root, alongside `companies.json`)
is the fix: one real, structured, durable record of every candidate
name's disposition, per source list, written to disk after *every*
single candidate is processed — not batched until session end — so an
interruption at any point (a spend limit, a crash, Elad stopping a
session) leaves the file accurately reflecting everything actually
done up to that exact moment. A future session's first move should be
`load_checkpoint()` and picking up the real `not_yet_checked` entries,
not re-deriving state from a handoff's prose.

Shape:
```json
{
  "_note": "...",
  "sources": {
    "wikipedia_153": {
      "description": "...",
      "candidates": {
        "Adallom": {"status": "unresolved", "resolved_to": null, "reason": "...", "checked_at": "2026-08-24T12:00:00Z"}
      }
    }
  }
}
```
`status` is one of `added` / `unscannable` / `unresolved` /
`not_yet_checked` — deliberately the same four-value vocabulary the
task itself specifies, not a richer enum, so this file stays a simple
index rather than duplicating `companies.json`/
`companies_unscannable.json`'s own real detail (which stays the
source of truth for *why* — this file only tracks *whether checked*
and *what it resolved to*, pointing back at the real company name for
detail).
"""

import json
from pathlib import Path

DEFAULT_CHECKPOINT_PATH = Path(__file__).resolve().parent.parent / "harvesting_checkpoint.json"

VALID_STATUSES = {"added", "unscannable", "unresolved", "not_yet_checked"}


def load_checkpoint(path=DEFAULT_CHECKPOINT_PATH):
    """Load the real, current checkpoint file. Raises if it doesn't
    exist yet — unlike `companies_unscannable.json`'s optional-feeling
    shape, a harvesting session should never silently start from an
    empty checkpoint; that's exactly the "lost track of progress"
    failure mode this file exists to prevent.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_checkpoint(data, path=DEFAULT_CHECKPOINT_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def update_candidate(source_key, name, status, resolved_to=None, reason=None, checked_at=None, path=DEFAULT_CHECKPOINT_PATH):
    """Read-modify-write the real, current file on disk for exactly one
    candidate, then save immediately — this is the whole point of the
    module. Called once per candidate as it's actually resolved during
    a live session, not batched, so the file on disk is never more
    than one candidate behind real progress.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid checkpoint status: {status!r} (must be one of {sorted(VALID_STATUSES)})")

    data = load_checkpoint(path)
    source = data["sources"][source_key]
    source["candidates"][name] = {
        "status": status,
        "resolved_to": resolved_to,
        "reason": reason,
        "checked_at": checked_at,
    }
    save_checkpoint(data, path)
    return data


def summarize(path=DEFAULT_CHECKPOINT_PATH):
    """Real counts per source/status — what a session should print at
    startup (and a human reading this file's own summary should trust
    over any prose elsewhere describing progress)."""
    data = load_checkpoint(path)
    result = {}
    for source_key, source in data["sources"].items():
        counts = {status: 0 for status in VALID_STATUSES}
        for candidate in source["candidates"].values():
            counts[candidate["status"]] += 1
        result[source_key] = counts
    return result


def not_yet_checked(source_key, path=DEFAULT_CHECKPOINT_PATH):
    """The real, current list of names in `source_key` still needing a
    real check — what a resuming session should actually iterate over.
    """
    data = load_checkpoint(path)
    return [
        name
        for name, candidate in data["sources"][source_key]["candidates"].items()
        if candidate["status"] == "not_yet_checked"
    ]
