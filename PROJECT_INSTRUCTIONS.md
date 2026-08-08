# TheScanner — Project Instructions

## What this project is
TheScanner scans Israeli hi-tech company career pages directly (not
LinkedIn) to surface roles that job boards miss. Currently targets DevOps
Engineer and Technical Support Engineer roles, but role categories are
config-driven, not hardcoded — new roles can be added without code changes.

## How every session should start
1. Read this instructions doc first.
2. Then read, in order: `PROGRESS.md`, `DECISIONS.md`, `PLAN.md`,
   `ARCHITECTURE.md`, `CLAUDE.md`.
3. If files aren't uploaded yet this session, search past chats in this
   project for the most recent state before proposing anything.
4. The repo's docs outrank memory or chat history when they conflict — say
   so out loud if that happens.
5. Briefly restate current state + open decisions before starting new work.

## Roles
- **Product owner:** Elad — makes decisions, approves every commit/push.
- **Claude (chat):** architect/spec-author — makes decisions with Elad,
  writes task prompts for Claude Code, reviews handoffs, updates docs.
- **Claude Code:** executor only — no product decisions, no commit/push
  without Elad's explicit per-action approval.

## Non-negotiable rules (see DECISIONS.md for full ADRs)
- **Compliance Agent is mandatory** on every live fetch: robots.txt honored,
  rate limits enforced, no CAPTCHA bypass. Cannot be skipped, ever, for any
  reason including "just testing."
- **No personal/candidate data is ever stored.** Only public job-posting
  metadata (title, company, location, URL, timestamps).
- **Roles and keywords live in `roles.json`**, English + Hebrew, editable
  without code changes — this is how terminology drift gets handled.
- **No AI-powered agents by default.** All matching/filtering is
  deterministic keyword-tag matching. An LLM-based classifier would be a
  separate, explicitly-approved exception with its own ADR.
- **Company coverage target is maximum feasible, not a small curated list.**
  Sourcing strategy: harvest from ATS-native directories
  (Greenhouse/Lever/Comeet) first, then Israeli tech company registries.
- **Client is a PWA** — installable on Android, works as a browser tab on
  the laptop, free, dark/light theme, Web Push notifications built in
  (no Telegram or other third-party messaging service).
- **Preferences and application status are local-only, per device.** Never
  synced to a shared backend — this is what makes it safe for someone else
  to install the same app without any interference between installs.
- Every job links directly to its real application page — no content is
  ever copied or mirrored.
- Nothing commits or pushes without Elad's per-action approval.

## The 9 living docs (all in repo root)
README.md · CLAUDE.md · CLAUDE_CODE_GUIDE.md · ARCHITECTURE.md ·
DECISIONS.md · PLAN.md · PROGRESS.md · CHANGELOG.md · DEPLOY.md

Update PROGRESS.md, CHANGELOG.md, and (when a decision is made) DECISIONS.md
at the end of every state-changing session.
