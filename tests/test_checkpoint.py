"""Tests for discovery/checkpoint.py (Session 39).

Real incident this module exists to prevent: Session 38's Wikipedia-
list research was delegated to a background agent that hit an org
spend limit partway through and returned nothing usable — no partial
progress survived anywhere. These tests confirm the actual durability
property that matters: the file on disk reflects every single
candidate processed so far, not just what happened to survive to a
final write.
"""

import json

import pytest

from discovery.checkpoint import (
    load_checkpoint,
    not_yet_checked,
    save_checkpoint,
    summarize,
    update_candidate,
)


def _seed(path, candidates=None):
    data = {
        "_note": "test fixture",
        "sources": {
            "test_source": {
                "description": "a fake source for testing",
                "candidates": candidates or {},
            }
        },
    }
    save_checkpoint(data, path)
    return path


def test_update_candidate_writes_immediately_to_disk(tmp_path):
    # The whole point of this module: after exactly one call, the real
    # file on disk already reflects it — not buffered in memory until
    # some later "flush" the caller might never reach.
    path = _seed(tmp_path / "checkpoint.json")

    update_candidate("test_source", "Acme Corp", "added", resolved_to="Acme Corp", path=path)

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["sources"]["test_source"]["candidates"]["Acme Corp"]["status"] == "added"


def test_update_candidate_preserves_previously_written_candidates(tmp_path):
    # An interruption between two calls must never lose the first
    # call's already-durable result — read-modify-write, not overwrite.
    path = _seed(tmp_path / "checkpoint.json")

    update_candidate("test_source", "First Co", "added", resolved_to="First Co", path=path)
    update_candidate("test_source", "Second Co", "unresolved", reason="no signal found", path=path)

    data = load_checkpoint(path)
    candidates = data["sources"]["test_source"]["candidates"]
    assert candidates["First Co"]["status"] == "added"
    assert candidates["Second Co"]["status"] == "unresolved"
    assert candidates["Second Co"]["reason"] == "no signal found"


def test_update_candidate_rejects_an_invalid_status(tmp_path):
    path = _seed(tmp_path / "checkpoint.json")

    with pytest.raises(ValueError, match="invalid checkpoint status"):
        update_candidate("test_source", "Acme Corp", "maybe", path=path)


def test_not_yet_checked_returns_only_real_unchecked_names(tmp_path):
    path = _seed(
        tmp_path / "checkpoint.json",
        candidates={
            "Added Co": {"status": "added", "resolved_to": "Added Co", "reason": None, "checked_at": "2026-01-01T00:00:00Z"},
            "Unresolved Co": {"status": "unresolved", "resolved_to": None, "reason": "blocked", "checked_at": "2026-01-01T00:00:00Z"},
            "Untouched Co": {"status": "not_yet_checked", "resolved_to": None, "reason": None, "checked_at": None},
        },
    )

    assert not_yet_checked("test_source", path=path) == ["Untouched Co"]


def test_summarize_gives_real_counts_per_status(tmp_path):
    path = _seed(
        tmp_path / "checkpoint.json",
        candidates={
            "A": {"status": "added", "resolved_to": "A", "reason": None, "checked_at": "x"},
            "B": {"status": "added", "resolved_to": "B", "reason": None, "checked_at": "x"},
            "C": {"status": "unscannable", "resolved_to": "C", "reason": None, "checked_at": "x"},
            "D": {"status": "not_yet_checked", "resolved_to": None, "reason": None, "checked_at": None},
        },
    )

    counts = summarize(path=path)
    assert counts["test_source"] == {"added": 2, "unscannable": 1, "unresolved": 0, "not_yet_checked": 1}


def test_load_checkpoint_raises_when_the_file_does_not_exist(tmp_path):
    # Deliberate: a harvesting session must never silently start from
    # an empty/missing checkpoint — that's the exact "lost track of
    # progress" failure mode this file exists to prevent.
    with pytest.raises(FileNotFoundError):
        load_checkpoint(tmp_path / "does_not_exist.json")


def test_the_real_repo_checkpoint_file_is_well_formed():
    # Confirms the real, committed harvesting_checkpoint.json (not a
    # fixture) parses and has the expected top-level shape — a cheap
    # real-world sanity check that a hand-edit hasn't corrupted it.
    data = load_checkpoint()
    assert "sources" in data
    for source_key, source in data["sources"].items():
        assert "candidates" in source
        for name, candidate in source["candidates"].items():
            assert candidate["status"] in {"added", "unscannable", "unresolved", "not_yet_checked"}, (
                f"{source_key}/{name} has an invalid status: {candidate['status']!r}"
            )
