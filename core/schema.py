"""Canonical Job schema pieces (ARCHITECTURE.md §2/§3: "core/ — canonical
schema, dedup logic, keyword filter.").

Currently just job_id construction — there's no separate Normalizer Agent
built yet (ARCHITECTURE.md §1's pipeline diagram still lists one as a
future piece), so the rest of the canonical shape is assembled directly by
run.py's build_summary() for now.
"""

import hashlib


def compute_job_id(company, source_identifier):
    """Stable hash of company + the adapter's own identifier for one posting.

    Deliberately NOT title + location: Session 3 found Palantir posts the
    exact same title ("Forward Deployed Software Engineer") across dozens
    of cities, so title+location isn't guaranteed unique, and a company
    could plausibly post the same title in the same city twice regardless.
    `source_identifier` is meant to be each job's `absolute_url` — already
    unique per posting for every adapter in this repo (Greenhouse embeds a
    numeric job id, Lever/Comeet/CustomAdapter each embed a UUID) — without
    requiring any adapter to expose a new field just for this.

    Company is included in the hash (not just the identifier alone) so two
    different companies' postings can never collide even in the
    unexpected case their URL schemes ever produced the same identifier
    string.
    """
    raw = f"{company}|{source_identifier}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
