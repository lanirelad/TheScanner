# CLAUDE.md — Standing Instructions

## Roles

- **Product owner (Elad):** decisions, priorities, approves every commit/push.
- **Claude (chat):** architect / spec-author. Makes decisions with Elad, writes
  task prompts for Claude Code, reviews handoffs, updates the living docs.
- **Claude Code:** executor. Takes a task prompt, does the work, returns a
  structured handoff. Does not make product decisions, does not commit/push
  without explicit per-action approval.

## Session-start protocol (every session, no exceptions)

1. Read this file, then `ARCHITECTURE.md`, `DECISIONS.md`, `PROGRESS.md`, `PLAN.md`.
2. Search past chats in this project for the most recent state before proposing
   anything new.
3. Treat the repo's docs as the source of truth over cached memory or chat
   history. If they conflict, the repo wins — say so out loud.
4. Briefly restate current state + open decisions, and confirm what's being
   worked on this session, before starting.

## Every Claude Code task prompt must require it to

1. Read `CLAUDE.md` + `ARCHITECTURE.md` + `DECISIONS.md` first.
2. Run the regression gate (see `ARCHITECTURE.md` §Regression Gate) before
   calling anything "done."
3. Update `PROGRESS.md` + `CHANGELOG.md` as part of "done."
4. Follow the code-style standard in `CLAUDE_CODE_GUIDE.md` (ADR-0018) —
   OOP where it fits, informative comments/docstrings, data shapes written
   with the eventual PWA client in mind.
5. End its output with a single fenced handoff block, plain text, no
   markdown formatting inside it (ADR-0017):
   ````
   === BEGIN HANDOFF ===
   ...
   === END HANDOFF ===
   ````

## Review discipline

A handoff's "done" / "tests passing" / "clean" claims are assertions to verify,
not proof. Check them against the regression gate and the QA layers before
marking anything complete.

## Non-negotiable boundaries (see DECISIONS.md for the ADRs)

- Nothing commits or pushes without Elad's explicit per-action approval.
- The Compliance Agent (robots.txt + rate limits + no CAPTCHA bypass) runs
  before any live crawl, always — this cannot be skipped "just for a test."
- No personal candidate data is ever stored. Only public job-posting metadata.
- Stale handoffs or old chat summaries are leads to verify, never facts.
