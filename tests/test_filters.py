"""Fixture-based tests for the adapters and the Stage 1 filter (ADR-0006).

Runs entirely against cached JSON fixtures — never makes a live network
call. Fixtures are real Stage 1 responses captured from one-time manual
smoke tests: Wiz/Playtika (Greenhouse, Session 1) and Palantir/Smarsh
(Lever, Session 3).
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


def _load_raw_fixture(name):
    return json.loads((FIXTURES_DIR / f"{name}_stage1_raw.json").read_text(encoding="utf-8"))


def _load_greenhouse_fixture_jobs(name):
    return parse_greenhouse_stage1_jobs(_load_raw_fixture(name))


def _load_lever_fixture_jobs(name):
    return parse_lever_stage1_jobs(_load_raw_fixture(name))


def _job_by_title(jobs, title):
    for job in jobs:
        if job["title"] == title:
            return job
    raise AssertionError(f"no job titled {title!r} in fixture")


def _job_by_title_and_location(jobs, title, location):
    # Some Lever companies (Palantir in particular) post the exact same
    # title across many cities — title alone doesn't uniquely identify a
    # posting the way it did for every Greenhouse fixture in this repo.
    for job in jobs:
        if job["title"] == title and job["location"] == location:
            return job
    raise AssertionError(f"no job titled {title!r} at {location!r} in fixture")


# --- Greenhouse (Wiz, Playtika) ---------------------------------------------


def test_wiz_devops_tel_aviv_matches():
    role_filter = _build_filter()
    jobs = _load_greenhouse_fixture_jobs("wiz")

    job = _job_by_title(jobs, "DevOps Engineer")
    result = role_filter.match(job)

    assert result == {
        "matched": True,
        "role_category": "devops",
        "matched_tag": "devops",
    }


def test_wiz_non_israel_location_is_rejected():
    role_filter = _build_filter()
    jobs = _load_greenhouse_fixture_jobs("wiz")

    job = _job_by_title(jobs, "Account Executive, Federal Civilian")
    assert job["location"] == "Washington, D.C."

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_wiz_israel_role_without_matching_tag_is_rejected():
    # "Backend Engineer" used to be the example here, but roles.json grew
    # a "software_development" category (tags including "backend engineer")
    # since Session 8 — real, intentional config evolution (ADR-0007), not
    # a regression. "Incident Responder" is confirmed still non-matching
    # under the current roles.json. Wiz posts it in two cities, so this
    # needs the title+location lookup, not title alone.
    role_filter = _build_filter()
    jobs = _load_greenhouse_fixture_jobs("wiz")

    job = _job_by_title_and_location(jobs, "Incident Responder", "Tel Aviv")

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_wiz_backend_engineer_now_matches_software_development():
    # Locks in the current, correct behavior after roles.json's
    # software_development category was added: this used to be a
    # deliberate non-match example (see the test above) before that
    # config change.
    role_filter = _build_filter()
    jobs = _load_greenhouse_fixture_jobs("wiz")

    job = _job_by_title(jobs, "Backend Engineer")
    assert job["location"] == "Tel Aviv"

    result = role_filter.match(job)
    assert result == {
        "matched": True,
        "role_category": "software_development",
        "matched_tag": "backend engineer",
    }


def test_playtika_devsecops_is_not_a_devops_tag_match():
    role_filter = _build_filter()
    jobs = _load_greenhouse_fixture_jobs("playtika")

    job = _job_by_title(jobs, "DevSecOps")
    assert job["location"] == "Herzliya"

    # "devsecops" is not a substring match for the "devops" tag —
    # confirms the matcher isn't accidentally over-matching.
    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_playtika_fixture_matches_after_roles_json_expansion():
    # Was "no matches yet" through Session 8. roles.json's new
    # project_manager category (added after Session 8, real config
    # evolution per ADR-0007) now matches 2 of Playtika's real postings.
    role_filter = _build_filter()
    jobs = _load_greenhouse_fixture_jobs("playtika")

    matches = {job["title"]: role_filter.match(job) for job in jobs}
    matched_titles = {title for title, result in matches.items() if result["matched"]}
    assert matched_titles == {" HRIS Project Manager - Maternity leave replacement ", "Tech Program Manager"}
    assert matches["Tech Program Manager"]["role_category"] == "project_manager"


# --- Lever (Palantir, Smarsh) ------------------------------------------------


def test_palantir_non_israel_location_is_rejected():
    role_filter = _build_filter()
    jobs = _load_lever_fixture_jobs("palantir")

    job = _job_by_title(jobs, "Administrative Business Partner")
    assert job["location"] == "London, United Kingdom"

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_palantir_israel_role_now_matches_software_development():
    # Real live data (Session 3): Palantir has exactly one Israel-located
    # posting. "Forward Deployed Software Engineer" is also posted under
    # many other cities, so this must be looked up by title+location
    # together, not title alone (a genuine difference from every
    # Greenhouse fixture in this repo, where title alone was unique).
    # Through Session 8 this was a deliberate non-match example; roles.json
    # grew a software_development category (tag "software engineer") since
    # then, so it now correctly matches — real config evolution (ADR-0007),
    # not a regression.
    role_filter = _build_filter()
    jobs = _load_lever_fixture_jobs("palantir")

    job = _job_by_title_and_location(jobs, "Forward Deployed Software Engineer", "Tel Aviv, Israel")
    assert job["department"] is None  # Palantir's categories have no "department" key at all

    result = role_filter.match(job)
    assert result == {
        "matched": True,
        "role_category": "software_development",
        "matched_tag": "software engineer",
    }


def test_smarsh_israel_roles_without_matching_tag_are_rejected():
    role_filter = _build_filter()
    jobs = _load_lever_fixture_jobs("smarsh")

    for title in ("Java Developer", "Mobile Developer"):
        job = _job_by_title(jobs, title)
        assert job["location"] == "Israel"
        assert job["department"] == "Divisions"  # Smarsh's categories do set "department"

        result = role_filter.match(job)
        assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_lever_fixtures_have_exactly_one_match_after_roles_json_expansion():
    # Was "no matches" through Session 8 (see
    # test_palantir_israel_role_now_matches_software_development for why).
    # Smarsh still has none.
    role_filter = _build_filter()
    jobs = _load_lever_fixture_jobs("palantir") + _load_lever_fixture_jobs("smarsh")

    matches = [role_filter.match(job) for job in jobs]
    assert sum(1 for result in matches if result["matched"]) == 1


# --- Cross-adapter shape checks ----------------------------------------------


def test_stage1_job_shape_is_json_serializable():
    # Mobile-client-awareness (ADR-0018): the Stage 1 shape is what the PWA
    # will eventually read directly, so it must round-trip through JSON
    # cleanly, including Hebrew text, with no server-only objects leaking
    # through either adapter's parsing step.
    jobs = (
        _load_greenhouse_fixture_jobs("wiz")
        + _load_greenhouse_fixture_jobs("playtika")
        + _load_lever_fixture_jobs("palantir")
        + _load_lever_fixture_jobs("smarsh")
    )
    for job in jobs:
        assert set(job.keys()) == {"title", "department", "location", "absolute_url"}

    round_tripped = json.loads(json.dumps(jobs, ensure_ascii=False))
    assert round_tripped == jobs


def test_lever_stage1_output_discards_full_content_fields():
    # Lever's raw response always includes description/lists/additional
    # (no lightweight mode exists — see adapters/lever.py's module
    # docstring). This test locks in that our own parsing step still
    # discards all of that before Stage 1 data goes anywhere downstream.
    jobs = _load_lever_fixture_jobs("palantir")
    leaked_keys = {"description", "descriptionPlain", "descriptionBody", "lists", "additional"}
    for job in jobs:
        assert leaked_keys.isdisjoint(job.keys())


# --- Adapter unit tests (fake compliance agent, no network) ------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeComplianceAgent:
    """Stands in for ComplianceAgent so these tests never touch the network.

    fetch() is async (ADR-0021) to match the real ComplianceAgent's
    interface, even though this fake has no actual awaiting to do.
    """

    def __init__(self, payload):
        self._payload = payload
        self.fetched_urls = []

    async def fetch(self, url, params=None):
        self.fetched_urls.append(url)
        return _FakeResponse(self._payload)


async def test_greenhouse_adapter_fetches_without_content_true():
    raw = _load_raw_fixture("wiz")
    fake_agent = _FakeComplianceAgent(raw)
    adapter = GreenhouseAdapter(fake_agent)

    jobs = await adapter.fetch_stage1_jobs("wizinc")

    assert jobs == parse_greenhouse_stage1_jobs(raw)
    assert fake_agent.fetched_urls == ["https://boards-api.greenhouse.io/v1/boards/wizinc/jobs"]
    assert "content=true" not in fake_agent.fetched_urls[0]


async def test_lever_adapter_uses_the_injected_compliance_agent():
    raw = _load_raw_fixture("palantir")
    fake_agent = _FakeComplianceAgent(raw)
    adapter = LeverAdapter(fake_agent)

    jobs = await adapter.fetch_stage1_jobs("palantir")

    assert jobs == parse_lever_stage1_jobs(raw)
    assert fake_agent.fetched_urls == ["https://api.lever.co/v0/postings/palantir"]
