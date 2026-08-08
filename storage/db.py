"""SQLite storage for matched jobs — shared, same for every install
(ARCHITECTURE.md §9-11).

Deliberately excludes `application_status`: that field is device-local
only (ADR-0011/ADR-0014) and must never exist in shared/backend storage.
Said explicitly, not just omitted quietly, so a future change copy-pasting
the full canonical schema from ARCHITECTURE.md §2 doesn't reintroduce it
by accident — that would be the ADR-0011 boundary being violated.

Schema is the task-scoped subset of ARCHITECTURE.md §2 that this session's
adapters can actually populate: `source_ats`, `posted_at`, `on_linkedin`,
and `raw_description_hash` aren't in this table because nothing upstream
produces them yet (no per-adapter ATS tag on the Stage 1 shape, no posted
date from any adapter, no LinkedIn Cross-Reference Agent, no description
content retained past Stage 1 to hash). Adding those columns before
anything populates them would just be dead schema.
"""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "scan_results.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    role_category TEXT NOT NULL,
    matched_tag TEXT NOT NULL,
    source_url TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
"""


def connect(path=DEFAULT_DB_PATH):
    """Open (creating if needed) the shared SQLite database and ensure the
    jobs table exists. One call per run is enough — sqlite3 connections
    are cheap and this isn't a concurrent-writer scenario (writes only
    happen once, after the concurrent fetch phase has already finished).
    """
    conn = sqlite3.connect(path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def get_known_job_ids(conn):
    """Return every job_id already present before this run.

    This is the entire "memory" a scan run needs to tell new from
    still_open — core.dedup.compute_scan_status takes exactly this set,
    nothing SQLite-specific, so dedup logic itself never has to know
    storage is SQLite at all.
    """
    rows = conn.execute("SELECT job_id FROM jobs").fetchall()
    return {row[0] for row in rows}


def upsert_jobs(conn, matches):
    """Insert new jobs; update `last_seen_at` for jobs already known.

    `matches` are dicts shaped like core.dedup's output: job_id, company,
    title, location, role_category, matched_tag, source_url,
    first_seen_at, last_seen_at. On conflict (job_id already exists), only
    `last_seen_at` is overwritten — `first_seen_at` never changes once
    set, which is what makes "new" mean "first time this job_id was ever
    seen," not "first time seen this run."
    """
    conn.executemany(
        """
        INSERT INTO jobs
            (job_id, company, title, location, role_category, matched_tag, source_url, first_seen_at, last_seen_at)
        VALUES
            (:job_id, :company, :title, :location, :role_category, :matched_tag, :source_url, :first_seen_at, :last_seen_at)
        ON CONFLICT(job_id) DO UPDATE SET last_seen_at = excluded.last_seen_at
        """,
        matches,
    )
    conn.commit()
