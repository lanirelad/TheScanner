# TheScanner

Scans Israeli hi-tech company career pages directly — not LinkedIn — to surface
DevOps and technical-support roles that never make it onto job boards. Inspired by
the "SecretJobs" concept, built as a personal tool.

## What it does

1. Maintains a list of target companies + their detected ATS platform
   (Greenhouse, Lever, Comeet, or "custom/unknown").
2. Pulls fresh postings on a schedule, mostly via clean JSON APIs where available,
   falling back to HTML scraping only when necessary.
3. Filters postings against DevOps / technical-support keywords, in both English
   and Hebrew.
4. Deduplicates against previously seen postings.
5. (Optional, later) Cross-references against LinkedIn to tag "not on LinkedIn."
6. Alerts on new matches (email / Telegram — TBD).

## Status

Day 0 — scaffolding only. No crawler code yet.

## Start here

- `CLAUDE.md` — standing instructions and session-start protocol.
- `ARCHITECTURE.md` — system design, QA layers, agent roster.
- `DECISIONS.md` — the ADR log (why things are the way they are).
- `PLAN.md` — roadmap.
- `PROGRESS.md` — current state snapshot.

Read `PROGRESS.md` and `DECISIONS.md` before proposing any changes — the repo,
not chat memory, is the source of truth.
