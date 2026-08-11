# CHANGELOG.md

## 2026-08-07 — Scaffolding
- Created initial living-docs set (README, CLAUDE.md, ARCHITECTURE.md,
  DECISIONS.md, PLAN.md, PROGRESS.md, this file, DEPLOY.md,
  CLAUDE_CODE_GUIDE.md).
- Adapted the reusable work-architecture template (from the Goblet of
  Operations / calibpro lineage) for a job-scanning domain.
- Recorded ADR-0001 through ADR-0006 covering ATS-API-first strategy,
  compliance gate, no-PII policy, commit/push approval boundary, no-AI-agent
  default, and fixture-based sandbox.
- No functional code yet.

## 2026-08-07 — Deployment architecture decided
- Decided the full deployment shape: GitHub Actions (compute, schedule +
  manual trigger) + GitHub Pages (dashboard) + Cloudflare Worker (write path
  for application status) + Telegram (alerts, default/unconfirmed).
- Changed scan frequency from the earlier hourly assumption to twice daily,
  plus an on-demand manual "Run now" button.
- Added `scan_status` (new/still_open) and `application_status`
  (not_applied/applied) to the canonical job schema.
- Recorded ADR-0009, ADR-0010, ADR-0011 covering the above.
- Estimated full-scan time for ~1,500 companies at roughly 15-30 minutes,
  confirmed this fits comfortably within GitHub Actions' free-tier minutes
  even at twice-daily frequency.

## 2026-08-07 — Client architecture: PWA, local-only preferences, Web Push
- Decided the client is a Progressive Web App (ADR-0013), not a plain
  static dashboard and not a native Play Store build — installable on
  Android, works as a laptop browser tab, dark/light theme.
- Decided preferences (role/tag filters) and `application_status` are
  stored entirely on-device, never in a shared backend (ADR-0011,
  ADR-0014) — this also resolves the "what if someone else uses it"
  concern, since every install is independent with no shared state.
- Replaced the Telegram-bot alert assumption with native Web Push
  notifications via a Cloudflare Worker (ADR-0012) — no third-party
  messaging account needed.
- Replaced the Cloudflare-Worker-as-write-path design (original ADR-0011)
  with the Worker's new, simpler job: storing push subscriptions and
  sending notifications. No write-back path for job data exists anymore.
- Added ADR-0015: every job links directly to its real application page.

## 2026-08-07 — Two-stage fetch + location filtering (ADR-0016)
- Elad flagged that scanning ~1,500 companies for *all* their roles across
  *all* countries is wasteful, especially for multinational companies that
  post globally under one career page.
- Redesigned the fetch pipeline into two stages: a cheap lightweight job
  list (title, department, location) per company, and a full-description
  fetch only for roles that survive the early filters and remain ambiguous.
- Added `locations.json` — accepted locations (EN + HE), same config-driven
  pattern as `roles.json` — checked at Stage 1, before any heavy fetch.
- Updated ARCHITECTURE.md §1/§1b and PLAN.md Phase 1 accordingly.

## 2026-08-07 — First real build task: seed configs + CC task prompt
- Created `roles.json` (devops + technical_support, starter EN/HE tags) and
  `locations.json` (Israel-area locations, EN/HE) as real files.
- Verified two companies against the live Greenhouse API this session
  (Wiz -> `wizinc`, Playtika -> `playtikaltd`) rather than inventing a
  placeholder list — seeded `companies.json` with just these two, explicitly
  marked as a starter/test set, not the ~1,500-company target.
- Wrote `CC_TASK_001.md`: the first Claude Code task prompt — repo
  skeleton, Greenhouse adapter (Stage 1 only, per ADR-0016), Compliance
  Agent, location+title filter, fixture-based tests. Explicitly scoped out:
  Lever/Comeet, Stage 2, storage, the app, the Worker, and full company
  harvesting — those are later sessions.

## 2026-08-07 — Session 1 handoff reviewed; standing rules added
- Reviewed Session 1 handoff: repo skeleton, Greenhouse Stage 1 adapter,
  Compliance Agent, location+title filter, 5/5 fixture tests passing, 0
  network calls in tests, live smoke test against Wiz + Playtika confirmed
  working. Noted a real finding: Greenhouse's lightweight endpoint never
  returns `department` — added as an empirical note in ARCHITECTURE.md.
- Added ADR-0017: all future Claude Code handoffs must be a single
  triple-backtick fenced code block, plain text, no markdown formatting
  inside — for one-click copy.
- Added ADR-0018: code-style standard — OOP where it genuinely fits (not
  everywhere), mandatory why-focused docstrings/comments, and all data
  shapes written with the eventual PWA/Android client in mind.
- Updated CLAUDE.md and CLAUDE_CODE_GUIDE.md so these are standing rules
  for every future session, not just this task.
- Wrote `CC_TASK_002.md`: directory-structure review (show it, propose
  reorg if warranted, then apply) plus a code-style pass on Session 1's
  three files against ADR-0018.

## 2026-08-07 — Session 2 accepted; first commit deferred
- Reviewed and accepted Session 2's handoff: directory structure confirmed
  clean (no reorg needed — CC_TASK files were never actually written to
  disk, so nothing to move), `Adapter` base class added ahead of Lever/Comeet,
  `core/filters.py` refactored into a `RoleLocationFilter` class (real
  shared state — config loaded once, reused per job), `storage/__init__.py`
  now has an explanatory docstring, ADR citations double-checked for
  accuracy (declined to attribute the 1.5s rate-limit value to ADR-0002
  itself). 7/7 tests passing, 0 network calls, new test confirms the Stage
  1 job shape is JSON-serializable (mobile-client-awareness check).
- Elad decided to defer the first `git init`/commit — more building first,
  not yet ready to lock in history. This has now been asked and answered
  once; don't re-raise it as an open question every session, only surface
  it again if something changes (e.g. Elad asks, or risk of losing
  uncommitted work becomes concrete).

## 2026-08-07 — companies.json widened to Lever; CC_TASK_003 written
- Verified two real Lever companies with Israel offices: Palantir
  (`palantir`) and Smarsh (`smarsh`) — added to `companies.json`, same
  starter/test-set framing as the Greenhouse pair.
- Wrote `CC_TASK_003.md`: build `LeverAdapter` implementing the `Adapter`
  base class from Session 2, explicitly instructed to inspect Lever's real
  API shape empirically rather than assume it matches Greenhouse's, live
  smoke test against Palantir/Smarsh, fixture tests extended to cover it.

## 2026-08-07 — Session 3 accepted: LeverAdapter built, real Lever-specific finding
- Reviewed and accepted Session 3's handoff. `LeverAdapter(Adapter)` built
  cleanly — the base class held up for a genuinely different internal shape
  (flat list vs. jobs-key object, `text` vs `title`, nested `categories` vs
  flat `location`) without any change to `adapters/base.py`. Real second
  data point for the abstraction, not just Greenhouse-shaped duplication.
- **Real architectural finding:** Lever has no lightweight-vs-full-content
  mode at all — every posting always includes full description fields; a
  `content=false` param made no difference. For Lever, "Stage 1" is a
  parsing-layer distinction only, not a fetch-cost saving the way it is for
  Greenhouse. Documented in ARCHITECTURE.md §1 as a per-ATS caveat; Comeet's
  adapter must verify this empirically too rather than assume either
  pattern. This has real implications for the ~1,500-company time estimate
  if a meaningful share turn out to be Lever-hosted.
- Live smoke test: Palantir (305 postings) and Smarsh (42 postings), both
  compliant (robots.txt honored, rate-limited). No Stage 1 matches yet at
  either company — 3 Israel-located roles found total, none matching
  current devops/technical_support tags. Same "0 matches is not a bug"
  situation as Playtika in Session 1.
- 13/13 tests passing, 0 network calls in the test suite.
- Call-count disclosure accepted at face value and treated as a good
  practice, not a violation: 12 live calls were made against api.lever.co
  during schema discovery (vs. the "one fetch each" the task specified),
  all rate-limited and robots.txt-compliant, fully disclosed rather than
  glossed over. This is now the model for how future sessions should handle
  an unfamiliar ATS's undocumented schema — see PLAN.md open item to
  formalize this as a standing rule next session.
- Git init/commit remains deliberately deferred — Elad reconfirmed this
  explicitly rather than it just going unaddressed again.

## 2026-08-08 — Mascot chosen, app-UX requirements logged
- Mascot: bat — real biological sonar (echolocation), nocturnal/dark-theme
  fit, distinct from generic AI-mascot defaults. Alternatives considered:
  dolphin (also strong sonar association, friendlier/lighter feel), meerkat
  (lookout/vigilance framing rather than literal sonar). Bat chosen as
  primary; Elad can override.
- Logged app-side UX requirements to PLAN.md: background push delivery
  (inherent to PWA/Web Push, needs verification once built) and precise
  exit-warning scope (only for app-tracked in-progress actions, never for
  the independent cloud-side scheduled scan).

## 2026-08-08 — Session 4 accepted: async retrofit, robots.txt cache, usage log
- Reviewed and accepted. Race condition fix verified both by dedicated
  timing tests (fake HTTP client, real timestamp assertions) and by a live
  smoke test against real Greenhouse/Lever traffic — Wiz+Playtika (same
  domain) spaced 1.673s apart, Palantir (different domain) proceeded before
  the Greenhouse pair finished. Exactly the behavior ADR-0021 was built for.
- robots_cache.json working as designed, with a notably careful concurrency
  choice: cache-file I/O and per-domain fetch locking use separate locks,
  so cold-cache robots.txt fetches for different domains still run
  concurrently — only the near-instant file write serializes.
- Measured speedup: 1.07x — modest and honestly reported, with correct
  diagnosis (only 2 real domains at this test scale; the real payoff is at
  hundreds/thousands of domains, i.e. the actual ~8-9k target). Confirms
  the reasoning from the async-vs-threads discussion empirically rather
  than just theoretically.
- Resolved `usage_log.py`'s module placement: new `usage/` module, parallel
  to `storage/`/`compliance/`/`core/`/`adapters/` (see ARCHITECTURE.md §13).
- Doc-sync markdown corruption in transit: Claude Code caught it, disclosed
  it, and reconstructed proper formatting matching the existing ADR style
  rather than doing a broken literal paste or a silent fix. Elad should
  still eyeball the actual DECISIONS.md/PLAN.md on the laptop to confirm
  the reconstruction reads as intended.
- 22/22 tests passing, 0 real network calls in the suite.
- Git init/commit still deferred, unchanged.

## 2026-08-08 — companies.json widened to Comeet; CC_TASK_005 written
- Verified two real Comeet-hosted companies with Israel presence: AT&T
  Israel R&D Center (joinattil, 38.00A) and Enlight Renewable Energy
  (enlightenergy, 99.006). Both show zero current openings live — a valid
  test state, not a reason to pick different companies.
- Wrote CC_TASK_005.md: build ComeetAdapter, async-native from the start
  (no retrofit needed this time since async is now the established
  pattern), empirically discovering Comeet's real integration shape rather
  than assuming it matches Greenhouse or Lever.

## 2026-08-08 — companies.json widened to a custom career page; CC_TASK_006 written
- Verified monday.com's career page has no ATS fingerprint (UUID-based job
  URLs, not any known platform's ID pattern) — genuinely custom/in-house,
  not a white-labeled ATS. Found a real live match at verification time:
  "DevOps Tech Lead (BigBrain)," Tel Aviv — a genuine positive-match test
  case, not another zero-result company.
- Wrote CC_TASK_006.md: build the custom/non-ATS fallback adapter, with an
  explicit pre-check for whether the page needs JS execution to reveal job
  data (and an explicit instruction to stop and flag rather than silently
  reach for Playwright if so) — plus a config-driven design (selectors per
  company in a new config file) rather than one bespoke Python class per
  custom company, so the "custom bucket" from ARCHITECTURE.md §4a can
  actually scale via configuration.

## 2026-08-08 — Session 6 accepted; Ashby promoted to a real adapter (ADR-0024)
- Reviewed and accepted Session 6: CustomAdapter built config-driven as
  asked, with an honest scope-limiting docstring (it scales via config only
  for companies sharing the same script-tag-JSON-blob rendering pattern —
  not a universal scraper, and doesn't pretend to be). The "exactly once"
  sanity check on the recursive key search before trusting it is exactly
  the right instinct.
- Real find: monday.com's positions are tagged `source: "ashby"` —
  confirmed independently that Ashby publishes a real public posting API
  (api.ashbyhq.com/posting-api/job-board/{clientname}), same tier as
  Greenhouse/Lever. Recorded as ADR-0024: Ashby gets a proper adapter, not
  a custom-bucket config entry. monday.com will move out of the custom
  bucket once verified against the real Ashby API.
- 42/42 tests passing, exact match count (1, the DevOps Tech Lead role)
  locked in as a regression assertion.

## 2026-08-08 — Session 7 accepted: Ashby correctly abandoned, not built
- Reviewed and accepted Session 7's handoff — one of the most important
  sessions so far, precisely because nothing got built. The Compliance
  Agent blocked api.ashbyhq.com's robots.txt (401) before any product-data
  fetch, and Claude Code correctly stopped rather than attempting any
  workaround, disclosing the one out-of-band robots.txt-only diagnostic
  call it made to confirm the block was real rather than a bug.
- Confirmed via further research: api.ashbyhq.com hosts both Ashby's
  authenticated admin API and its public posting-api under one domain —
  our domain-level robots.txt check has no safe way to separate "this path
  is fine" from "this domain restricts automated access."
- ADR-0024 marked Superseded by ADR-0025: Ashby integration abandoned,
  monday.com stays permanently on CustomAdapter (Session 6). Explicitly
  corrected the record — ADR-0024's original "verified independently"
  claim rested on third-party sources, not an actual robots.txt check by
  planning-Claude. Own error, caught by the system working as designed.
- Adapter roster is now settled: Greenhouse, Lever, Comeet, and
  config-driven CustomAdapter. Phase 2 is functionally complete.

## 2026-08-08 — CC_TASK_008 written: storage, dedup, first real CLI run
- This is the session that finally ties everything built so far (4
  adapters, filter, compliance, usage log) into one real, runnable scan
  producing an actual result set.
- Explicit schema boundary called out in the task: application_status
  must NOT appear in shared/backend storage, per ADR-0011/ADR-0014 —
  device-local only.
- Elad requested a companies-scanned counter; specified in the task as
  part of the CLI's summary output (total attempted, succeeded/failed,
  matches new vs. still_open) — reuses the company_count field already in
  usage_log's schema rather than adding a separate tracking mechanism.

## 2026-08-08 — CC_TASK_009 written: finally git init + the real scheduled workflow
- This session finally addresses the git init deferral — not by choice
  anymore, but because Phase 3 (GitHub Actions) genuinely cannot exist
  without the repo being on GitHub.
- Task structured with an explicit, separate confirmation gate before any
  push happens, per ADR-0004 — the first-ever commit gets the same
  approval discipline as every future one, not treated as a special
  one-time exception.
- Implements ADR-0028's config-gated schedule: the workflow's registered
  cron is a cheap, frequent check-in; the real "scans per day" logic lives
  in schedule_config.json, editable without touching the workflow file.

## 2026-08-09 — Session 9: git init, first push, and the scheduled workflow
- Found roles.json had grown three new categories (npi,
  software_development, project_manager) since Session 8 — legitimate
  config evolution per ADR-0007. Fixed the 6 existing tests this broke to
  reflect current correct behavior before doing anything else, and
  re-ran run.py so the committed scan_results.db/usage_log.json would
  reflect real, current-config data (15 matches) rather than stale
  pre-expansion results (2 matches) at the moment they became permanent
  history.
- Built schedule/gate.py (should_run_full_scan, ADR-0028) and
  schedule_config.json. New schedule/ package, mirroring usage/'s
  precedent for a distinct cross-cutting concern. CLI entry point lives
  in schedule/__main__.py specifically to avoid a double-import
  RuntimeWarning that a __main__ block inside gate.py itself would cause
  (gate.py is also imported by schedule/__init__.py's re-export).
- Built .github/workflows/scan.yml: hourly cheap cron + workflow_dispatch,
  a gate-check step, conditional run.py execution, and a bot commit/push
  of the three shared-state files back to the repo.
- Git init, first commit, first push — each step gated by an explicit,
  separate confirmation per ADR-0004, exactly as the task specified.
  Showed the full git status before committing and flagged two things
  worth Elad's attention first: the 6MB Palantir fixture (flagged since
  Session 3, still present as-is) and the two PNG assets that appeared
  externally in Session 6. Confirmed to commit as-is. Confirmed
  separately to add the remote and push. Renamed master to main before
  the push (free, nothing had been pushed yet). Now live at
  https://github.com/lanirelad/TheScanner.git.
- 67/67 tests passing (was 57: 6 fixed for the roles.json drift, 1 new,
  9 new for the schedule gate), 0 real network calls.
- ARCHITECTURE.md §9a now explicitly documents the cron-cadence-vs-real-
  schedule distinction; §3 gained a schedule/ entry.

## 2026-08-09 — Session 10: schedule_config.json to on_demand, scan timeout cap
- schedule_config.json's mode changed from "scheduled" to "on_demand" —
  Elad wants manual-only operation for now, scheduling available as a
  switchable option later, not active by default. scans_per_day/
  times_utc left in place, inactive but ready.
- Confirmed (not rebuilt) via schedule/gate.py's existing test suite plus
  a direct check against the real file: schedule-triggered check-ins now
  return False unconditionally, workflow_dispatch still always returns
  True. 67/67 tests unchanged.
- Added timeout-minutes: 20 to the "Run scan" step specifically (not
  job-level) in .github/workflows/scan.yml — a safety cap against the
  free-tier budget once the company list grows, not a tuning target.
- Confirmed and documented in ARCHITECTURE.md §9a exactly what a timeout
  kill does: nothing partial gets saved, because run.py's current
  all-companies-concurrently-then-write-once design means there's nothing
  partial to save in the first place if the process is killed mid-fetch —
  and separately, GitHub Actions' own default step semantics would skip
  the commit/push step after a timed-out step regardless. A clean no-op,
  not data corruption — confirmed deliberately, not left as an accident.

## 2026-08-09 — Session 11: roles.json "enabled" flag now functional
- Flagged a discrepancy rather than silently working around it: the task
  said roles.json already had an "enabled" field added externally — it
  didn't (unchanged since Session 9's initial commit). Added the field
  myself with exactly the values the task specified (true for devops/
  technical_support, false for npi/software_development/project_manager),
  since that value was unambiguous, not a new decision.
- core/filters.py's role-matching loop now skips any category where
  "enabled" is falsy. Missing the key entirely defaults to disabled (fail
  safe, not fail open) - matches the project's existing conservative-
  default pattern (robots.txt 401 -> disallow-all).
- Fixed 5 Session 9 tests whose premise no longer held ("this now matches
  under the full 5-category set") to assert the new correct default
  instead, and added 2 consolidated all-enabled override tests preserving
  the real-data discovery value without 5 near-duplicates, plus 4 new
  synthetic unit tests isolating the enabled-flag mechanism itself.
- Live smoke test: real matches dropped from 15 (Session 9's actual
  figure) to 2, both still_open, every dropped match being project_manager/
  software_development as expected.
- 73/73 tests passing (was 67: 5 fixed, 6 new), 0 real network calls.
- Nothing committed - per this session's explicit instructions.

## 2026-08-09 — Session 13: EU-region domain support, Optimove + Mobileye
- companies.json didn't actually have the Optimove/Mobileye entries the
  task described (same discrepancy pattern as Sessions 9/11) - added them
  with the exact slugs/domains specified, then did the real verification.
- Real finding: Lever has a genuine separate EU API domain
  (api.eu.lever.co, confirmed against Mobileye - 200 OK, identical shape
  to the global API, 138 real postings). Greenhouse does not -
  boards-api.eu.greenhouse.io fails DNS resolution entirely; Optimove's
  EU-hosted board is served fine by the ordinary global
  boards-api.greenhouse.io. EU residency there only affects the public
  page domain, not the API.
- GreenhouseAdapter/LeverAdapter both take an ats_region argument now,
  resolved via a REGION_DOMAINS dict (empty for Greenhouse, {"eu":
  "api.eu.lever.co"} for Lever) with a default-domain fallback - a future
  confirmed region is a dict entry, not new code. Nothing speculative was
  added to Greenhouse's mapping just for symmetry with Lever.
- Live smoke test: 9/9 companies succeeded, 7 total matches (5 new from
  Mobileye, 2 already-known still_open). Optimove: 0 matches - the task
  expected a "Site Reliability Engineer" posting there; it doesn't exist
  in the live data at verification time, flagged as listing drift, not a
  bug.
- 87/87 tests passing (was 73: 14 new), 0 real network calls. 6 total
  live network calls this session, disclosed per ADR-0019 (1 DNS-failure
  attempt that never reached a server, 1 HTML investigation fetch, 2
  exploratory API probes, 2 final fixture-capture fetches).
- ARCHITECTURE.md §1 gained the EU-region empirical finding.

## 2026-08-11 — Session 14: latest_scan.json export + real budget calculator
- Built usage/budget.py's compute_usage_summary(entries, cap, now=None) -
  sums duration_minutes for current-calendar-month entries only,
  percent_used deliberately not clamped at 100.
- Checked before designing it, not assumed: usage_log.json only ever gets
  entries from real run.py executions - the workflow's hourly cheap
  check-in cost (ADR-0028's own disclosed line item) is never logged
  anywhere. The calculator sums exactly what's real and surfaces that gap
  via includes_checkin_overhead: false in the output itself, not a
  fabricated estimate or a buried code comment.
- Refactored usage/log.py to extract load_usage_log(), shared between
  record_scan_run and the new calculator.
- Added run.py's build_latest_scan_export() (pure, flat PWA-facing shape,
  no internal bookkeeping fields, never application_status) and a shared
  write_json_file() helper. Both latest_scan.json and usage_summary.json
  now get written on every real run.py execution.
- Live smoke test: both files written with real current data - see the
  handoff for full contents.
- 98/98 tests passing (was 87: 11 new), 0 real network calls.
- ARCHITECTURE.md §9a gained two new notes documenting both files' real
  shape and the check-in-overhead gap.

## 2026-08-11 — Session 15: the first real PWA
- Two more discrepancies flagged, not silently resolved: ADR-0029 doesn't
  exist in DECISIONS.md (still ends at ADR-0028), and demo.html (the
  visual reference the task asked to match) doesn't exist anywhere in
  the repo. Built from each one's textual description instead of
  blocking - same pattern as Sessions 9/11/13's discrepancies.
- Moved latest_scan.json/usage_summary.json's default location from the
  repo root into pwa/ (amending Session 14's still-uncommitted work, not
  shipped behavior) - only files inside wrangler.jsonc's assets.directory
  are ever reachable on the deployed Cloudflare site.
- Built the full read-only PWA shell in pwa/: index.html, styles.css
  (dark radar theme), app.js (fetches and renders both JSON files, no
  interactivity yet per explicit scope), service-worker.js
  (network-first for data files, cache-first for the shell - two
  different strategies on purpose), manifest.json, and Pillow-generated
  properly-sized icons/animation frames (cut ~4.9 MB of source mascot art
  down to ~88 KB actually shipped).
- Wrote wrangler.jsonc (assets.directory: "./pwa") and updated
  .github/workflows/scan.yml's commit step to also push
  pwa/latest_scan.json/pwa/usage_summary.json - that push is what
  triggers Cloudflare's redeploy and keeps the live site's data current.
- Live-verified in a real browser, not just by inspection: ran run.py for
  real (9 attempted, 8 succeeded, 1 genuine ReadTimeout on Palantir),
  served pwa/ locally, confirmed both JSON files fetched successfully,
  all UI sections rendered with real values, zero console errors, and
  the service worker registered and active.
- 98/98 tests passing, unchanged - this session touched frontend/config
  only, plus two path constants in run.py.
- ARCHITECTURE.md §9a rewritten for the real Cloudflare deployment
  mechanics; §3 gained a pwa/ entry.
