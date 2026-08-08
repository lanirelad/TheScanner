"""Dedup / scan-status logic.

Lives in core/, not a new top-level module: ARCHITECTURE.md §3 already
names this exact responsibility as core/'s ("core/ — canonical schema,
dedup logic, keyword filter. No network calls. No adapter-specific
knowledge."), and this logic genuinely has none of its own — it only needs
a job_id and a set of already-known job_ids, both plain values, not
database objects. Keeping it storage-agnostic means the same function
works whether "known job_ids" came from SQLite (this session), a
different backend later, or a test's plain set literal.
"""


def compute_scan_status(job_id, known_job_ids):
    """Return "new" if job_id wasn't already known before this run, else
    "still_open" — matches ARCHITECTURE.md §2's field definition exactly:
    new = first_seen_at == this run.
    """
    return "still_open" if job_id in known_job_ids else "new"
