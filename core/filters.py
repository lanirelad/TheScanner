"""Stage 1 location + title filter (ADR-0016).

No network calls here — `core/` never depends on `adapters/` (dependency
direction rule, ARCHITECTURE.md §3/§4a). Stage 2 (full-description fetch
for ambiguous title matches) is explicitly out of scope this session.
"""

import json


class RoleLocationFilter:
    """Loads roles.json + locations.json once, then filters many jobs against them.

    Every job across an entire scan run (every company, every adapter) gets
    matched against the same loaded config — that's real shared state, not
    just arguments passed through a call chain, so it belongs on an object
    rather than a bare function re-loading/re-threading two config dicts
    through every call (ADR-0018).
    """

    def __init__(self, roles_path, locations_path):
        self.roles_config = self._load_json(roles_path)
        self.locations_config = self._load_json(locations_path)

    @staticmethod
    def _load_json(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def match(self, job):
        """Apply the Stage 1 filter to a single job dict.

        `job` is the Stage 1 shape: {title, department, location, absolute_url}.

        Location is checked first and rejects immediately on no match
        (ADR-0016 — location is a first-class filter, same tier as role
        tags, applied before any full-description fetch). Only a location
        match proceeds to the title/tag check.

        Returns a dict: {matched, role_category, matched_tag}.
        """
        if not self._location_matches(job.get("location")):
            return {"matched": False, "role_category": None, "matched_tag": None}

        role_category, matched_tag = self._matching_role_tag(job.get("title"))
        if role_category is None:
            return {"matched": False, "role_category": None, "matched_tag": None}

        return {"matched": True, "role_category": role_category, "matched_tag": matched_tag}

    def _location_matches(self, location):
        if not location:
            return False
        location_lower = location.lower()
        accepted = self.locations_config.get("accepted_locations", {})
        for terms in accepted.values():
            for term in terms:
                if term.lower() in location_lower:
                    return True
        return False

    def _matching_role_tag(self, title):
        if not title:
            return None, None
        title_lower = title.lower()
        for role_category, role in self.roles_config.items():
            for tag in role.get("tags_en", []) + role.get("tags_he", []):
                # Substring match is deliberately loose (e.g. catches
                # "Platform Engineer II") — see ADR-0007 on why tags are
                # config, not code: terminology drift is expected and
                # tightening this later would need real false-positive
                # evidence first, not a guess now.
                if tag.lower() in title_lower:
                    return role_category, tag
        return None, None
