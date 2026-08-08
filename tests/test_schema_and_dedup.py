"""Tests for core/schema.py (job_id) and core/dedup.py (scan_status)."""

from core.dedup import compute_scan_status
from core.schema import compute_job_id


def test_job_id_is_stable_for_the_same_inputs():
    a = compute_job_id("Wiz", "https://www.wiz.io/careers/job/4667217006")
    b = compute_job_id("Wiz", "https://www.wiz.io/careers/job/4667217006")
    assert a == b


def test_job_id_differs_by_source_identifier_even_with_same_title_and_company():
    # The exact Session 3 scenario: Palantir posts the identical title
    # across many cities. title+location alone isn't a safe key; the
    # per-posting absolute_url is what actually disambiguates them.
    tel_aviv = compute_job_id("Palantir Technologies", "https://jobs.lever.co/palantir/c4442730-israel")
    warsaw = compute_job_id("Palantir Technologies", "https://jobs.lever.co/palantir/a57a2864-warsaw")
    assert tel_aviv != warsaw


def test_job_id_differs_by_company_even_with_identical_source_identifier():
    # Guards against two different companies' URL schemes ever coincidentally
    # producing the same identifier string.
    a = compute_job_id("Company A", "https://example.com/jobs/123")
    b = compute_job_id("Company B", "https://example.com/jobs/123")
    assert a != b


def test_scan_status_is_new_when_job_id_not_previously_known():
    assert compute_scan_status("abc123", known_job_ids=set()) == "new"
    assert compute_scan_status("abc123", known_job_ids={"other-id"}) == "new"


def test_scan_status_is_still_open_when_job_id_previously_known():
    assert compute_scan_status("abc123", known_job_ids={"abc123", "other-id"}) == "still_open"
