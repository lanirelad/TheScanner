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


# --- roles.json "enabled" flag (Session 11, ADR-0007) -----------------------
# Synthetic configs, not the real fixtures — isolates the enabled-flag
# mechanism itself from any particular category's real tags/matches.


def _filter_with_roles(roles_config):
    role_filter = _build_filter()
    role_filter.roles_config = roles_config
    return role_filter


def test_disabled_category_tag_is_not_matched():
    roles_config = {
        "devops": {"enabled": False, "tags_en": ["devops"], "tags_he": []},
    }
    role_filter = _filter_with_roles(roles_config)

    job = {"title": "DevOps Engineer", "department": None, "location": "Tel Aviv", "absolute_url": "x"}
    result = role_filter.match(job)

    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_enabled_category_tag_is_matched():
    roles_config = {
        "devops": {"enabled": True, "tags_en": ["devops"], "tags_he": []},
    }
    role_filter = _filter_with_roles(roles_config)

    job = {"title": "DevOps Engineer", "department": None, "location": "Tel Aviv", "absolute_url": "x"}
    result = role_filter.match(job)

    assert result == {"matched": True, "role_category": "devops", "matched_tag": "devops"}


def test_category_missing_enabled_key_entirely_defaults_to_disabled():
    # Fail safe, not fail open (documented in core/filters.py): a category
    # with no "enabled" key at all — shouldn't happen with the current
    # roles.json, but a future hand-edit could omit it — must not silently
    # start matching. A quietly-inactive category is a low-consequence
    # miss; a quietly-reactivated one surfacing unwanted matches is worse,
    # given Elad wants tight control over which categories are live.
    roles_config = {
        "devops": {"tags_en": ["devops"], "tags_he": []},  # no "enabled" key
    }
    role_filter = _filter_with_roles(roles_config)

    job = {"title": "DevOps Engineer", "department": None, "location": "Tel Aviv", "absolute_url": "x"}
    result = role_filter.match(job)

    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_only_disabled_categories_present_matches_nothing_even_with_a_universally_loose_tag():
    # A broader check than the single-category tests above: with every
    # category disabled, a title that would hit two different categories'
    # tags simultaneously still matches neither.
    roles_config = {
        "devops": {"enabled": False, "tags_en": ["devops"], "tags_he": []},
        "technical_support": {"enabled": False, "tags_en": ["support engineer"], "tags_he": []},
    }
    role_filter = _filter_with_roles(roles_config)

    job = {
        "title": "DevOps Support Engineer",
        "department": None,
        "location": "Tel Aviv",
        "absolute_url": "x",
    }
    result = role_filter.match(job)

    assert result == {"matched": False, "role_category": None, "matched_tag": None}


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


def test_wiz_backend_engineer_is_rejected_while_software_development_disabled():
    # Session 9 found this matches software_development's "backend
    # engineer" tag. Session 11 added an "enabled" flag to roles.json and
    # Elad chose devops/technical_support only for now — software_development
    # is present in config but inactive, so this must be rejected under the
    # real, current roles.json, not matched. See
    # test_disabled_categories_still_match_correctly_when_enabled below for
    # proof the underlying tag logic itself is unaffected.
    role_filter = _build_filter()
    jobs = _load_greenhouse_fixture_jobs("wiz")

    job = _job_by_title(jobs, "Backend Engineer")
    assert job["location"] == "Tel Aviv"

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_playtika_devsecops_is_not_a_devops_tag_match():
    role_filter = _build_filter()
    jobs = _load_greenhouse_fixture_jobs("playtika")

    job = _job_by_title(jobs, "DevSecOps")
    assert job["location"] == "Herzliya"

    # "devsecops" is not a substring match for the "devops" tag —
    # confirms the matcher isn't accidentally over-matching.
    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_playtika_fixture_has_no_matches_with_default_enabled_categories():
    # Session 9 found 2 matches here once roles.json grew a
    # project_manager category. Session 11's "enabled" flag makes
    # project_manager inactive by default (Elad's actual choice, only
    # devops/technical_support are on for now), so the current, correct
    # behavior is back to zero matches for this fixture.
    role_filter = _build_filter()
    jobs = _load_greenhouse_fixture_jobs("playtika")

    matches = [role_filter.match(job) for job in jobs]
    assert not any(result["matched"] for result in matches)


# --- Lever (Palantir, Smarsh) ------------------------------------------------


def test_palantir_non_israel_location_is_rejected():
    role_filter = _build_filter()
    jobs = _load_lever_fixture_jobs("palantir")

    job = _job_by_title(jobs, "Administrative Business Partner")
    assert job["location"] == "London, United Kingdom"

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_palantir_israel_role_is_rejected_while_software_development_disabled():
    # Real live data (Session 3): Palantir has exactly one Israel-located
    # posting. "Forward Deployed Software Engineer" is also posted under
    # many other cities, so this must be looked up by title+location
    # together, not title alone (a genuine difference from every
    # Greenhouse fixture in this repo, where title alone was unique).
    # Session 9 found this matches software_development's "software
    # engineer" tag; Session 11's "enabled" flag makes that category
    # inactive by default, so the current, correct behavior under the real
    # roles.json is rejection.
    role_filter = _build_filter()
    jobs = _load_lever_fixture_jobs("palantir")

    job = _job_by_title_and_location(jobs, "Forward Deployed Software Engineer", "Tel Aviv, Israel")
    assert job["department"] is None  # Palantir's categories have no "department" key at all

    result = role_filter.match(job)
    assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_smarsh_israel_roles_without_matching_tag_are_rejected():
    role_filter = _build_filter()
    jobs = _load_lever_fixture_jobs("smarsh")

    for title in ("Java Developer", "Mobile Developer"):
        job = _job_by_title(jobs, title)
        assert job["location"] == "Israel"
        assert job["department"] == "Divisions"  # Smarsh's categories do set "department"

        result = role_filter.match(job)
        assert result == {"matched": False, "role_category": None, "matched_tag": None}


def test_lever_fixtures_have_no_matches_with_default_enabled_categories():
    # Session 9 found 1 match here (Palantir's Forward Deployed Software
    # Engineer, via software_development). Session 11's default
    # (devops/technical_support only) makes that category inactive, so
    # the current, correct behavior is back to zero.
    role_filter = _build_filter()
    jobs = _load_lever_fixture_jobs("palantir") + _load_lever_fixture_jobs("smarsh")

    matches = [role_filter.match(job) for job in jobs]
    assert not any(result["matched"] for result in matches)


def test_disabled_categories_still_match_correctly_when_enabled():
    # Session 9's real-data discovery (software_development/project_manager
    # tags correctly matching real fixture titles) shouldn't just vanish
    # because Session 11 disabled those categories by default — otherwise
    # the underlying tag-matching logic for every disabled category could
    # silently rot, unexercised, until someone re-enables one in production
    # and finds out then whether it still works. Force every category
    # "enabled" in a loaded config (not the real roles.json file) to prove
    # the tag logic itself is untouched by the enabled-flag feature —
    # only which categories participate has changed.
    role_filter = _build_filter()
    for role in role_filter.roles_config.values():
        role["enabled"] = True

    wiz_backend = _job_by_title(_load_greenhouse_fixture_jobs("wiz"), "Backend Engineer")
    assert role_filter.match(wiz_backend) == {
        "matched": True,
        "role_category": "software_development",
        "matched_tag": "backend engineer",
    }

    palantir_fdse = _job_by_title_and_location(
        _load_lever_fixture_jobs("palantir"), "Forward Deployed Software Engineer", "Tel Aviv, Israel"
    )
    assert role_filter.match(palantir_fdse) == {
        "matched": True,
        "role_category": "software_development",
        "matched_tag": "software engineer",
    }

    playtika_pm = _job_by_title(_load_greenhouse_fixture_jobs("playtika"), "Tech Program Manager")
    assert role_filter.match(playtika_pm) == {
        "matched": True,
        "role_category": "project_manager",
        "matched_tag": "program manager",
    }


# --- Location matching beyond the literal string "Israel" (Session 39) ------
# Real bug this locks in the fix for: Session 38 caught itself missing a
# real match (Parallel Wireless, Kfar Saba) because its own ad-hoc
# verification script only searched for the substring "israel" in a
# job's location. That script was never part of this codebase, but the
# *real* production filter (this file) turned out to have the identical
# gap for real — Kfar Saba, Ness Ziona, and other genuine Israeli tech
# hubs simply weren't in locations.json's accepted_locations list at
# all, so a job located at exactly one of those cities (with no country
# name anywhere in the string) was silently rejected in production, not
# just in a throwaway script.


def test_kfar_saba_alone_is_accepted_without_the_word_israel():
    # The real, exact case this session found: a genuine Parallel
    # Wireless posting whose location field is the bare city name.
    role_filter = _build_filter()
    job = {"title": "Sr. Principal, DevOps", "department": None, "location": "Kfar Saba", "absolute_url": "x"}

    result = role_filter.match(job)

    assert result == {"matched": True, "role_category": "devops", "matched_tag": "devops"}


def test_ness_ziona_alone_is_accepted_without_the_word_israel():
    # The real, exact case for Foresight Automotive — confirmed via a
    # real live scan that its Ness Ziona postings were being silently
    # dropped before this fix (0 matches from a company with 5 real
    # open Israel-based postings).
    role_filter = _build_filter()
    job = {"title": "DevOps Engineer", "department": None, "location": "Ness Ziona", "absolute_url": "x"}

    result = role_filter.match(job)

    assert result == {"matched": True, "role_category": "devops", "matched_tag": "devops"}


def test_a_real_non_israeli_city_sharing_no_substring_with_any_accepted_term_is_still_rejected():
    # Guards against the fix being so broad it stops rejecting anything —
    # a real, unambiguous non-Israel location must still fail.
    role_filter = _build_filter()
    job = {"title": "DevOps Engineer", "department": None, "location": "Austin, TX", "absolute_url": "x"}

    result = role_filter.match(job)

    assert result == {"matched": False, "role_category": None, "matched_tag": None}


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
