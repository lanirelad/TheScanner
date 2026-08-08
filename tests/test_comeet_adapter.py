"""Fixture-based tests for ComeetAdapter (ADR-0006).

Runs entirely against cached HTML fixtures — never makes a live network
call. tests/fixtures/att_stage1_raw.html and enlight_stage1_raw.html are
real Stage 1 responses captured from a one-time manual smoke test against
AT&T Israel R&D Center and Enlight Renewable Energy's Comeet career pages
(Session 5).

New file rather than folding into tests/test_filters.py, which already
covers Greenhouse and Lever and was flagged in Sessions 2 and 3 as getting
large — starting the split here rather than growing that file further.
"""

import json
from pathlib import Path

from adapters.comeet import ComeetAdapter, parse_stage1_jobs
from core.filters import RoleLocationFilter

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# The task that motivated this session described both AT&T Israel and
# Enlight as having zero open positions live. By the time this session
# actually fetched them, that had gone stale — AT&T had 7 and Enlight had
# 18 real postings. That's a real, useful positive-data-shape fixture, but
# it means the "zero open positions parses as an empty list" case has no
# genuine live capture available this session. Rather than silently skip
# that requirement or claim a synthetic string is "real," this is a
# hand-built HTML snippet matching the exact real template structure found
# on both companies' actual pages (unconditional `var COMPANY_POSITIONS_DATA;`
# declaration followed by a straight-line assignment — see
# adapters/comeet.py's module docstring) with the array emptied out. It
# proves the parsing logic handles an empty array correctly; it does not
# prove Comeet actually renders `[]` rather than omitting the variable
# entirely when a company has zero postings, which remains unverified.
_SYNTHETIC_ZERO_POSITIONS_HTML = """
<html><head><script type="text/javascript">
   var serverVersion="rc-307-5";
   var COMPANY_DATA ;
   var COMPANY_POSITIONS_DATA ;
   COMPANY_DATA = {"name": "Synthetic Test Co", "location": "Israel"};
   COMPANY_POSITIONS_DATA = [];
</script></head><body></body></html>
"""

_HTML_WITH_NO_COMEET_DATA_AT_ALL = "<html><body>not a comeet page</body></html>"


def _build_filter():
    return RoleLocationFilter(REPO_ROOT / "roles.json", REPO_ROOT / "locations.json")


def _load_fixture_jobs(name):
    html = (FIXTURES_DIR / f"{name}_stage1_raw.html").read_text(encoding="utf-8")
    return parse_stage1_jobs(html)


def _job_by_title(jobs, title):
    for job in jobs:
        if job["title"] == title:
            return job
    raise AssertionError(f"no job titled {title!r} in fixture")


def test_att_israel_role_without_matching_tag_is_rejected():
    role_filter = _build_filter()
    jobs = _load_fixture_jobs("att")

    job = _job_by_title(jobs, "Cyber Security Lead")
    assert job["location"] == "Airport City/ ToHa, Tel Aviv"
    assert job["department"] == "Leadership"

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_enlight_non_israel_location_is_rejected():
    role_filter = _build_filter()
    jobs = _load_fixture_jobs("enlight")

    job = _job_by_title(jobs, "Strategic Projects & Integration Manager (Enlight USA)")
    assert job["location"] == "United States"

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_enlight_israel_role_without_matching_tag_is_rejected():
    # "Operational Technology Manager" is a genuine near-miss worth locking
    # in explicitly: it's Israel-located and technology-adjacent, but
    # doesn't contain any devops/technical_support tag.
    role_filter = _build_filter()
    jobs = _load_fixture_jobs("enlight")

    job = _job_by_title(jobs, "Operational Technology Manager")
    assert job["location"] == "Israel"

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_att_and_enlight_fixtures_have_five_matches_after_roles_json_expansion():
    # Was "no matches" through Session 8. roles.json's project_manager and
    # software_development categories (added after Session 8, real config
    # evolution per ADR-0007) now match 3 AT&T postings and 2 Enlight
    # postings — not a regression.
    role_filter = _build_filter()
    jobs = _load_fixture_jobs("att") + _load_fixture_jobs("enlight")

    matches = [role_filter.match(job) for job in jobs]
    assert sum(1 for result in matches if result["matched"]) == 5


def test_comeet_stage1_output_discards_full_content_fields():
    # The embedded COMPANY_POSITIONS_DATA blob includes full HTML job
    # descriptions in custom_fields.details (see adapters/comeet.py's
    # module docstring — no lightweight mode exists). This locks in that
    # parse_stage1_jobs still only returns the four Stage 1 fields.
    jobs = _load_fixture_jobs("att")
    for job in jobs:
        assert set(job.keys()) == {"title", "department", "location", "absolute_url"}


def test_stage1_job_shape_is_json_serializable_for_comeet():
    # Mobile-client-awareness (ADR-0018), same check as the other two
    # adapters — including Hebrew text, since Enlight's fixture contains
    # Hebrew in some description fields (not in the Stage 1 fields
    # themselves, but worth confirming the round-trip holds regardless).
    jobs = _load_fixture_jobs("att") + _load_fixture_jobs("enlight")
    round_tripped = json.loads(json.dumps(jobs, ensure_ascii=False))
    assert round_tripped == jobs


def test_parse_stage1_jobs_returns_empty_list_for_zero_positions():
    jobs = parse_stage1_jobs(_SYNTHETIC_ZERO_POSITIONS_HTML)
    assert jobs == []


def test_parse_stage1_jobs_returns_empty_list_when_positions_data_missing_entirely():
    jobs = parse_stage1_jobs(_HTML_WITH_NO_COMEET_DATA_AT_ALL)
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


async def test_comeet_adapter_builds_url_from_slug_and_uid():
    html = (FIXTURES_DIR / "att_stage1_raw.html").read_text(encoding="utf-8")
    fake_agent = _FakeComplianceAgent(html)
    adapter = ComeetAdapter(fake_agent, ats_uid="38.00A")

    jobs = await adapter.fetch_stage1_jobs("joinattil")

    assert jobs == parse_stage1_jobs(html)
    assert fake_agent.fetched_urls == ["https://www.comeet.com/jobs/joinattil/38.00A"]
