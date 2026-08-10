"""Tests for EU-region domain support in GreenhouseAdapter/LeverAdapter
(Session 13, ADR-0019 exploratory calls).

Two parts: adapter unit tests (fake compliance agent, confirm which domain
each adapter actually calls for a given ats_region) and fixture-based tests
against real captured data from Optimove (Greenhouse, EU) and Mobileye
(Lever, EU).
"""

import json
from pathlib import Path

from adapters.greenhouse import GreenhouseAdapter
from adapters.greenhouse import parse_stage1_jobs as parse_greenhouse_stage1_jobs
from adapters.lever import LeverAdapter
from adapters.lever import parse_stage1_jobs as parse_lever_stage1_jobs
from core.filters import RoleLocationFilter

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _build_filter():
    return RoleLocationFilter(REPO_ROOT / "roles.json", REPO_ROOT / "locations.json")


def _job_by_title(jobs, title):
    for job in jobs:
        if job["title"] == title:
            return job
    raise AssertionError(f"no job titled {title!r} in fixture")


# --- Adapter unit tests: which domain does each ats_region resolve to? -----


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeComplianceAgent:
    def __init__(self, payload):
        self._payload = payload
        self.fetched_urls = []

    async def fetch(self, url, params=None):
        self.fetched_urls.append(url)
        return _FakeResponse(self._payload)


async def test_greenhouse_adapter_uses_global_domain_with_no_region():
    fake_agent = _FakeComplianceAgent({"jobs": []})
    adapter = GreenhouseAdapter(fake_agent)

    await adapter.fetch_stage1_jobs("wizinc")

    assert fake_agent.fetched_urls == ["https://boards-api.greenhouse.io/v1/boards/wizinc/jobs"]


async def test_greenhouse_adapter_uses_global_domain_even_with_eu_region():
    # The real empirical finding this session: Greenhouse's EU data
    # residency does not extend to a separate API domain. ats_region="eu"
    # must still resolve to the same global boards-api domain, not a
    # nonexistent boards-api.eu.greenhouse.io.
    fake_agent = _FakeComplianceAgent({"jobs": []})
    adapter = GreenhouseAdapter(fake_agent, ats_region="eu")

    await adapter.fetch_stage1_jobs("optimove")

    assert fake_agent.fetched_urls == ["https://boards-api.greenhouse.io/v1/boards/optimove/jobs"]


async def test_lever_adapter_uses_global_domain_with_no_region():
    fake_agent = _FakeComplianceAgent([])
    adapter = LeverAdapter(fake_agent)

    await adapter.fetch_stage1_jobs("palantir")

    assert fake_agent.fetched_urls == ["https://api.lever.co/v0/postings/palantir"]


async def test_lever_adapter_uses_eu_domain_when_region_is_eu():
    # Confirmed live: api.eu.lever.co is real and returns the same shape.
    fake_agent = _FakeComplianceAgent([])
    adapter = LeverAdapter(fake_agent, ats_region="eu")

    await adapter.fetch_stage1_jobs("mobileye")

    assert fake_agent.fetched_urls == ["https://api.eu.lever.co/v0/postings/mobileye"]


async def test_unknown_region_falls_back_to_default_domain_for_both_adapters():
    # A region with no entry in REGION_DOMAINS (not yet confirmed/mapped)
    # must fail safe to the default domain, not raise or construct a
    # broken URL — same "don't guess, fall back" spirit as everywhere else
    # in this project.
    gh_agent = _FakeComplianceAgent({"jobs": []})
    await GreenhouseAdapter(gh_agent, ats_region="apac").fetch_stage1_jobs("someslug")
    assert gh_agent.fetched_urls == ["https://boards-api.greenhouse.io/v1/boards/someslug/jobs"]

    lv_agent = _FakeComplianceAgent([])
    await LeverAdapter(lv_agent, ats_region="apac").fetch_stage1_jobs("someslug")
    assert lv_agent.fetched_urls == ["https://api.lever.co/v0/postings/someslug"]


# --- Optimove (Greenhouse, EU) — real fixture -------------------------------


def _load_optimove_jobs():
    raw = json.loads((FIXTURES_DIR / "optimove_stage1_raw.json").read_text(encoding="utf-8"))
    return parse_greenhouse_stage1_jobs(raw)


def test_optimove_fixture_shape_matches_standard_greenhouse_shape():
    jobs = _load_optimove_jobs()
    assert len(jobs) == 9
    for job in jobs:
        assert set(job.keys()) == {"title", "department", "location", "absolute_url"}


def test_optimove_has_no_matches_with_default_enabled_categories():
    # Real live data (Session 13): Optimove's 9 postings are Account
    # Executive/Billing/CRM/Customer Success/Onboarding PM/ProdOps &
    # Support Engineer/Senior Product Manager, across US/UK/Scotland/
    # Brazil/Colombia/Estonia/Tel Aviv. None are Israel-located AND
    # devops/technical_support-tagged under the current default config.
    # Note: the task that motivated this session expected a "Site
    # Reliability Engineer" match here — no such title exists in the
    # live data at verification time; flagged as normal listing drift
    # (same category of thing as every prior session's live-data checks),
    # not a bug in the adapter or filter.
    role_filter = _build_filter()
    jobs = _load_optimove_jobs()

    matches = [role_filter.match(job) for job in jobs]
    assert not any(result["matched"] for result in matches)


def test_optimove_json_serializable():
    jobs = _load_optimove_jobs()
    round_tripped = json.loads(json.dumps(jobs, ensure_ascii=False))
    assert round_tripped == jobs


# --- Mobileye (Lever, EU) — real fixture ------------------------------------


def _load_mobileye_jobs():
    raw = json.loads((FIXTURES_DIR / "mobileye_stage1_raw.json").read_text(encoding="utf-8"))
    return parse_lever_stage1_jobs(raw)


def test_mobileye_fixture_shape_matches_standard_lever_shape():
    jobs = _load_mobileye_jobs()
    assert len(jobs) == 138
    for job in jobs:
        assert set(job.keys()) == {"title", "department", "location", "absolute_url"}


def test_mobileye_devops_and_infrastructure_engineer_matches():
    role_filter = _build_filter()
    jobs = _load_mobileye_jobs()

    job = _job_by_title(jobs, "DevOps & Infrastructure Engineer")
    assert job["location"] == "Ramat Gan, Israel"

    result = role_filter.match(job)
    assert result == {"matched": True, "role_category": "devops", "matched_tag": "devops"}


def test_mobileye_senior_sre_matches():
    role_filter = _build_filter()
    jobs = _load_mobileye_jobs()

    job = _job_by_title(jobs, "Senior SRE & Linux Infrastructure Engineer")
    assert job["location"] == "Jerusalem, Israel"

    result = role_filter.match(job)
    assert result == {"matched": True, "role_category": "devops", "matched_tag": "sre"}


def test_mobileye_data_platform_engineer_matches_via_platform_engineer_tag():
    # A genuine loose-match case, worth locking in explicitly: "Data
    # Platform Engineer" isn't a devops title on its face, but "platform
    # engineer" is a devops tag and is a real substring of this title.
    role_filter = _build_filter()
    jobs = _load_mobileye_jobs()

    job = _job_by_title(jobs, "Data Platform Engineer")
    assert job["location"] == "Petah Tikva, Israel"

    result = role_filter.match(job)
    assert result == {"matched": True, "role_category": "devops", "matched_tag": "platform engineer"}


def test_mobileye_exactly_five_matches_with_default_enabled_categories():
    # Locks in the real total so a future regression shows up as a
    # changed number here: DevOps & Infrastructure Engineer, Senior SRE &
    # Linux Infrastructure Engineer, Data Platform Engineer, and two
    # "Field Engineer ... Relocation" postings (technical_support's
    # "field engineer" tag) whose location field is Jerusalem, Israel
    # despite the relocation destination named in the title.
    role_filter = _build_filter()
    jobs = _load_mobileye_jobs()

    matches = [role_filter.match(job) for job in jobs]
    assert sum(1 for result in matches if result["matched"]) == 5


def test_mobileye_json_serializable():
    jobs = _load_mobileye_jobs()
    round_tripped = json.loads(json.dumps(jobs, ensure_ascii=False))
    assert round_tripped == jobs
