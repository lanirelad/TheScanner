"""Fixture-based tests for CustomAdapter (ADR-0006).

Runs entirely against a cached HTML fixture — never makes a live network
call. tests/fixtures/monday_stage1_raw.html is a real Stage 1 response
captured from a one-time manual smoke test against monday.com's careers
page (Session 6).
"""

import json
from pathlib import Path

from adapters.custom import CustomAdapter, load_custom_selectors, parse_stage1_jobs
from core.filters import RoleLocationFilter

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _monday_config():
    selectors = load_custom_selectors(REPO_ROOT / "custom_selectors.json")
    return selectors["monday.com"]


def _load_fixture_jobs():
    html = (FIXTURES_DIR / "monday_stage1_raw.html").read_text(encoding="utf-8")
    return parse_stage1_jobs(html, _monday_config())


def _job_by_title(jobs, title):
    for job in jobs:
        if job["title"] == title:
            return job
    raise AssertionError(f"no job titled {title!r} in fixture")


def _build_filter():
    return RoleLocationFilter(REPO_ROOT / "roles.json", REPO_ROOT / "locations.json")


def test_devops_tech_lead_tel_aviv_matches():
    # This is the real, currently-live positive match that motivated this
    # session — confirming it end-to-end (extraction + filter) is the main
    # point of this test file, not an afterthought.
    role_filter = _build_filter()
    jobs = _load_fixture_jobs()

    job = _job_by_title(jobs, "DevOps Tech Lead (BigBrain)")
    assert job["location"] == "Tel Aviv"

    result = role_filter.match(job)
    assert result == {
        "matched": True,
        "role_category": "devops",
        "matched_tag": "devops",
    }


def test_non_israel_location_is_rejected():
    role_filter = _build_filter()
    jobs = _load_fixture_jobs()

    job = _job_by_title(jobs, "Americas Controller")
    assert job["location"] == "New York"

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_israel_role_without_matching_tag_is_rejected():
    role_filter = _build_filter()
    jobs = _load_fixture_jobs()

    job = _job_by_title(jobs, "Application Security Group Lead")
    assert job["location"] == "Tel Aviv"

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_exactly_one_match_in_current_live_data():
    # Locks in the real count so a future regression (e.g. an
    # over-permissive tag) shows up as a changed number here.
    role_filter = _build_filter()
    jobs = _load_fixture_jobs()

    matches = [role_filter.match(job) for job in jobs]
    assert sum(1 for result in matches if result["matched"]) == 1


def test_custom_stage1_output_shape():
    jobs = _load_fixture_jobs()
    assert len(jobs) == 22
    for job in jobs:
        assert set(job.keys()) == {"title", "department", "location", "absolute_url"}


def test_stage1_job_shape_is_json_serializable_for_custom():
    jobs = _load_fixture_jobs()
    round_tripped = json.loads(json.dumps(jobs, ensure_ascii=False))
    assert round_tripped == jobs


def test_absolute_url_uses_uid_from_position():
    jobs = _load_fixture_jobs()
    job = _job_by_title(jobs, "DevOps Tech Lead (BigBrain)")
    assert job["absolute_url"] == "https://monday.com/careers/6b945ea6-f095-42b4-a83d-b9b5f407feae"


def test_find_list_by_key_locates_positions_nested_under_an_arbitrary_wrapper_key():
    # The real monday.com data nests "positions" under an opaque UUID key
    # (props.pageProps.dynamicData.<uuid>.positions) that isn't safe to
    # hardcode in config. This proves the recursive search isn't just
    # coincidentally working because of that specific real shape — any
    # wrapper key name works, at any depth.
    synthetic_html = """
    <html><head><script id="__NEXT_DATA__">
    {"some": {"deeply": {"nested": {"randomKey123": {"positions": [
        {"name": "Test Role", "department": "Test Dept", "location": {"name": "Tel Aviv"}, "uid": "abc-123"}
    ]}}}}}
    </script></head><body></body></html>
    """
    config = {
        "script_id": "__NEXT_DATA__",
        "positions_key": "positions",
        "field_map": {"title": "name", "department": "department", "location": "location.name"},
        "url_template": "https://example.com/careers/{uid}",
    }

    jobs = parse_stage1_jobs(synthetic_html, config)

    assert jobs == [
        {
            "title": "Test Role",
            "department": "Test Dept",
            "location": "Tel Aviv",
            "absolute_url": "https://example.com/careers/abc-123",
        }
    ]


def test_parse_stage1_jobs_returns_empty_list_when_script_tag_missing():
    config = _monday_config()
    jobs = parse_stage1_jobs("<html><body>no next data here</body></html>", config)
    assert jobs == []


def test_parse_stage1_jobs_returns_empty_list_when_positions_key_absent():
    config = _monday_config()
    html = '<html><head><script id="__NEXT_DATA__">{"props": {"unrelated": true}}</script></head></html>'
    jobs = parse_stage1_jobs(html, config)
    assert jobs == []


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeComplianceAgent:
    def __init__(self, text):
        self._text = text
        self.fetched_urls = []

    async def fetch(self, url, params=None):
        self.fetched_urls.append(url)
        return _FakeResponse(self._text)


async def test_custom_adapter_uses_injected_compliance_agent_and_config():
    html = (FIXTURES_DIR / "monday_stage1_raw.html").read_text(encoding="utf-8")
    config = _monday_config()
    fake_agent = _FakeComplianceAgent(html)
    adapter = CustomAdapter(fake_agent, config)

    jobs = await adapter.fetch_stage1_jobs(ats_slug="unused")

    assert jobs == parse_stage1_jobs(html, config)
    assert fake_agent.fetched_urls == ["https://monday.com/careers"]
