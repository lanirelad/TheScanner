"""Storage layer — SQLite persistence + dedup state.

See storage/db.py for the schema and functions. Deliberately excludes
`application_status` (ADR-0011/ADR-0014, device-local only) — see db.py's
module docstring for why that's stated explicitly rather than just omitted.
"""

from .db import DEFAULT_DB_PATH, connect, get_known_job_ids, upsert_jobs

__all__ = ["DEFAULT_DB_PATH", "connect", "get_known_job_ids", "upsert_jobs"]
