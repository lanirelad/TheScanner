"""Tests for storage/db.py — uses a real SQLite file in tmp_path, never the
shared repo-root database, and never touches the network."""

from storage.db import connect, get_known_job_ids, upsert_jobs


def _job(job_id, **overrides):
    job = {
        "job_id": job_id,
        "company": "Wiz",
        "title": "DevOps Engineer",
        "location": "Tel Aviv",
        "role_category": "devops",
        "matched_tag": "devops",
        "source_url": "https://example.com/jobs/1",
        "first_seen_at": "2026-08-09T00:00:00Z",
        "last_seen_at": "2026-08-09T00:00:00Z",
    }
    job.update(overrides)
    return job


def test_schema_never_includes_application_status(tmp_path):
    # ADR-0011/ADR-0014: application_status is device-local only and must
    # never exist in shared storage. Asserted directly against the actual
    # table columns, not just "no code writes it" — a real regression test
    # for the boundary the task explicitly warned about.
    conn = connect(tmp_path / "test.db")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    assert "application_status" not in columns
    assert columns == {
        "job_id",
        "company",
        "title",
        "location",
        "role_category",
        "matched_tag",
        "source_url",
        "first_seen_at",
        "last_seen_at",
    }


def test_get_known_job_ids_empty_on_fresh_database(tmp_path):
    conn = connect(tmp_path / "test.db")
    assert get_known_job_ids(conn) == set()


def test_upsert_inserts_new_job(tmp_path):
    conn = connect(tmp_path / "test.db")
    upsert_jobs(conn, [_job("job-1")])

    assert get_known_job_ids(conn) == {"job-1"}
    row = conn.execute("SELECT title, first_seen_at, last_seen_at FROM jobs WHERE job_id = 'job-1'").fetchone()
    assert row == ("DevOps Engineer", "2026-08-09T00:00:00Z", "2026-08-09T00:00:00Z")


def test_upsert_on_existing_job_id_only_updates_last_seen_at(tmp_path):
    conn = connect(tmp_path / "test.db")
    upsert_jobs(conn, [_job("job-1", first_seen_at="2026-08-01T00:00:00Z", last_seen_at="2026-08-01T00:00:00Z")])

    # Same job seen again on a later run — first_seen_at must never change,
    # only last_seen_at, which is what makes "new" mean "first time ever,"
    # not "first time this run."
    upsert_jobs(conn, [_job("job-1", first_seen_at="2026-08-09T00:00:00Z", last_seen_at="2026-08-09T00:00:00Z")])

    row = conn.execute("SELECT first_seen_at, last_seen_at FROM jobs WHERE job_id = 'job-1'").fetchone()
    assert row == ("2026-08-01T00:00:00Z", "2026-08-09T00:00:00Z")


def test_upsert_handles_a_batch_of_new_and_existing_jobs_together(tmp_path):
    conn = connect(tmp_path / "test.db")
    upsert_jobs(conn, [_job("job-1"), _job("job-2")])

    upsert_jobs(conn, [_job("job-2", last_seen_at="2026-08-09T12:00:00Z"), _job("job-3")])

    assert get_known_job_ids(conn) == {"job-1", "job-2", "job-3"}
