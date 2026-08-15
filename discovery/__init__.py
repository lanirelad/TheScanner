"""Discovery/onboarding helpers (ADR-0023, ADR-0031).

Not part of the production scan pipeline — `run.py`, `adapters/`, and
the GitHub Actions workflow never import from here. This package exists
for Claude Code harvesting sessions that need to find *new* companies'
ATS before a real adapter entry can be added to `companies.json`, a
distinct concern from actually scanning already-verified companies —
same reasoning as `usage/`/`schedule/` each getting their own package
(ARCHITECTURE.md §3).
"""
