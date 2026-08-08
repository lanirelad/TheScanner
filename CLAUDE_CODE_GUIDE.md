# CLAUDE_CODE_GUIDE.md — Rules for Claude Code

## Before starting any task
1. Read `CLAUDE.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `PROGRESS.md`.
2. Confirm the task prompt's scope against `PLAN.md` — flag if it seems to
   skip ahead of the current phase.

## While working
- Respect module boundaries in `ARCHITECTURE.md` §3 — `core/` never imports
  `adapters/`; every adapter fetch goes through the Compliance Agent.
- Never write a live-site test into the automated test suite — automated
  tests use fixtures only (`ARCHITECTURE.md` §5).
- Never add a code path that skips the Compliance Agent, even temporarily,
  even for local debugging.
- Never add a field to the canonical schema that could hold personal/PII
  data.
- If you hit an environment quirk (wrong Python binary, encoding issue, path
  problem), fix it once and document it in `ARCHITECTURE.md` §9 — don't leave
  it for the next session to rediscover.

## Before calling anything "done"
Run all three QA layers (`ARCHITECTURE.md` §4) plus the regression gate
checklist (§7). "Tests passing" is only true if you actually ran them this
session — restate the specific commands run and their output in the handoff.

## Handoff format
Every handoff — from `=== BEGIN HANDOFF ===` to `=== END HANDOFF ===` —
must be wrapped in a **single triple-backtick fenced code block**, plain
text only (no `**bold**`, no markdown bullets/asterisks inside the fence).
This lets Elad copy the whole thing with the code block's copy button.

````
=== BEGIN HANDOFF ===
Task:
Files changed:
Regression gate: [pass/fail per item]
QA layers: [L1/L2/L3 pass/fail]
Docs updated: [PROGRESS.md / CHANGELOG.md / DECISIONS.md — list actual edits]
Open questions / blockers:
=== END HANDOFF ===
````

## Code style (ADR-0018)
- Use classes where the domain has real objects with state/behavior (e.g. an
  `Adapter` base class with `GreenhouseAdapter`/`LeverAdapter`
  subclasses, a `ComplianceAgent` class). Don't force OOP where a plain
  function is clearer, and don't write procedural code where a class would
  clarify who owns what.
- Every non-trivial function/class gets a docstring explaining *why* it
  exists / what decision it encodes, not just a restatement of its name.
  Inline comments are for non-obvious reasoning (cite the relevant ADR when
  a comment is explaining a deliberate design choice, e.g. "content=true
  omitted deliberately, see ADR-0016").
- Data shapes should assume a phone-app (PWA) consumer eventually, even
  while only the Python backend exists: JSON-serializable, stable field
  names, no server-only assumptions baked in that the client can't work
  with later.

## Never
- Commit or push without Elad's explicit go-ahead for that specific commit.
- Bypass robots.txt, rate limits, or CAPTCHA.
- Store candidate/personal data.
- Add an AI/LLM-calling agent without a corresponding ADR approving it.
