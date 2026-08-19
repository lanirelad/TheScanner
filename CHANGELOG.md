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

## 2026-08-11 — Session 16: sync DECISIONS.md through ADR-0030 (backfilled)
- This entry was missed at the time (Session 16 only committed
  DECISIONS.md, skipping the standing PROGRESS.md/CHANGELOG.md update
  requirement) - backfilled now during Session 17 rather than left gone.
- DECISIONS.md was still at ADR-0028. Appended ADR-0029, ADR-0029a, and
  ADR-0030 verbatim, per ADR-0030's own new protocol (no pause to ask,
  flag in the handoff instead) - the exact situation ADR-0030 itself
  describes. Pushed as 3faddaa specifically to trigger Cloudflare's
  first real Git-integration build (dashboard had shown "No builds exist
  yet" despite two manual deploys).

## 2026-08-11 — Session 17: PWA visual fixes
- Wordmark now matches the exact spec Elad's task gave (JetBrains Mono
  700 20px, -0.5px letter-spacing, "Scanner" colored via --teal, aliased
  to the existing --radar-green accent since demo.html's exact hex isn't
  available - flagged as a judgment call). Added the Google Fonts link
  for JetBrains Mono + IBM Plex Sans.
- Role tags now show roles.json's label_en ("DevOps Engineer") instead of
  the raw role_category key ("devops"). Resolved server-side in run.py
  (new _role_label() helper, fail-safe to the raw key) rather than having
  app.js fetch roles.json itself - that would have meant duplicating
  roles.json into pwa/, the same file-locality problem Session 15 solved
  for the other two JSON exports. label_en now rides alongside
  role_category in both build_summary() and build_latest_scan_export().
- Verified live: ran run.py for real (9/9 succeeded, 7 matches), confirmed
  correct label_en values in pwa/latest_scan.json, served pwa/ locally
  and confirmed via getComputedStyle that the wordmark CSS matches the
  spec exactly and via get_page_text that job cards show the human-
  readable labels. Service worker still active.
- 100/100 tests passing (was 98: 2 new for _role_label()), 0 real network
  calls.
- ARCHITECTURE.md gained a Session 17 note alongside Session 15's
  existing "no demo.html" note.

## 2026-08-11/12 — Session 18: harvest toward a real ~5-minute scan
- Goal: grow companies.json toward ~200 Israeli-relevant Greenhouse
  companies (the real pacing floor under ADR-0002's 1.5s per-domain rate
  limit, since every Greenhouse company shares one domain) plus
  opportunistic Lever/Comeet additions, as a genuine test of ADR-0021's
  concurrency payoff, not an arbitrary stress test.
- Sourcing: compiled ~330 candidate Israeli-relevant company names across
  two rounds (Wikipedia's "List of companies of Israel"/"Israeli
  cybersecurity industry", failory.com's Israel startup list, general
  knowledge of the Israeli tech/cyber/AI ecosystem), then live-verified
  each one's guessed Greenhouse/Lever slug through the real Compliance
  Agent (robots.txt + 1.5s rate limit honored throughout, per ADR-0002 -
  no test-only bypass). 283+138=421 Greenhouse calls and 289+139=428
  Lever calls made across both rounds (disclosed per ADR-0019's
  exploratory-call policy), running concurrently on their own domain
  lanes so the two ATS lookups didn't add to each other's wall time.
- Real achieved count, honestly short of the ~200 target: 34 new
  Greenhouse companies + 4 new Lever companies verified and added (36
  Greenhouse total now, up from 2). Comeet wasn't expanded this session -
  unlike Greenhouse/Lever slugs, a Comeet URL needs both a slug and a
  separate numeric-looking uid that can't be guessed blindly, only
  discovered from a company's real career page, which is a slower,
  different sourcing process than this session's approach.
- Real false-positive catch, not silently trusted: 3 technical "HITs"
  (real 200 OK responses with real job data) were manually reviewed and
  excluded rather than added - "shield", "bold", and "vim" each returned
  exactly one posting with zero Israel signal in it (e.g. "Copy of
  Avenger" in Beijing for "shield") - generic-word slug collisions with
  an unrelated company on the same platform, not the intended Israeli
  company. A slug resolving to *a* real company isn't the same as
  resolving to *the intended* one; both were checked before adding
  anything.
- Fixed the real visibility gap Elad ran into: run.py's console summary
  now prints `[Company] FAILED — <real error>` per failure instead of
  just a bare count, and build_latest_scan_export() now carries a
  `failures: [{company, error}]` list in latest_scan.json alongside the
  existing companies_failed count - visible from a future PWA view, not
  just the GitHub Actions log.
- Live smoke test against the real expanded list (47 companies): 46/46
  succeeded except one genuine transient ReadTimeout (Imubit - same
  real-failure category as Session 15's Palantir timeout, not a bug),
  20 matches (13 new, 7 still_open). Real elapsed time: ~80 seconds -
  confirms the architecture's own reasoning (Greenhouse-domain company
  count is the pacing floor: ~36 real Greenhouse companies x 1.5s ≈ 54s,
  plus real response overhead ≈ the observed ~80s) rather than
  disproving it; reaching the actual ~5-minute target needs roughly
  ~200 real Greenhouse companies, which this session's harvesting fell
  well short of - reported honestly rather than rounded up.
- Test suite: 103/103 passing (was 100: 3 new for the failures-list
  fix), 0 real network calls in automated tests.

## 2026-08-12 — Session 19: domain-first harvesting round 2 + --teal fix
- Inverted Session 18's method to raise identity confidence: instead of
  guessing an ATS slug directly against boards-api.greenhouse.io/
  api.lever.co, this session fetched each candidate's own real domain/
  career page through the Compliance Agent and read the actual ATS
  (Greenhouse/Lever/Comeet) straight off of that real page — a redirect
  Location header or an embedded link, never a guessed slug.
- Sourced 505 fresh candidate names (mappedinisrael.com's real Israeli
  startup directory, flagged honestly as a dated snapshot, plus Session
  18's two guess-lists), deduplicated against the 47 already-verified
  companies.
- Real bug caught and fixed mid-session: ComplianceAgent.fetch()'s
  raise_for_status() call raises HTTPStatusError for any unfollowed 3xx
  (httpx.AsyncClient defaults to follow_redirects=False), not just
  4xx/5xx — the first discovery pass silently discarded every redirect,
  including the exact "/careers redirects straight to the real ATS"
  case this method depends on, and returned only 4 hits from 505
  candidates. Fixed by catching HTTPStatusError specifically and reading
  Location off exc.response, with one redirect-chase hop for
  non-ATS bounces (e.g. bare domain -> www) — re-run raised this to 13
  raw hits.
- 2 of those 13 were manually reviewed and rejected before adding
  anything: "BillGuard" resolved (via its own guessed domain's redirect)
  to Prosper, the US company that acquired it in 2015 — zero Israel
  signal, caught by the script's own name-token-seen=False flag, not
  the intended company; "Palantir" (from the directory) duplicated the
  existing "Palantir Technologies" Lever entry from Session 3 under a
  different display name.
- Real result: 1 new Greenhouse (K Health) + 10 new Comeet companies
  (Cognyte, Cyera, Feedvisor, Immunai, Infinidat, MetalBear, Netafim,
  Pipl, Riverside, SysAid) — companies.json: 47 -> 58 (Greenhouse: 37 ->
  38). Comeet expansion was explicitly out of scope in Session 18 since
  a slug+uid pair can't be guessed; reading it directly off each
  company's own real page resolved that blocker completely — every new
  Comeet company came with its exact slug+uid pair, no guessing
  involved.
- Honest finding on why the Greenhouse hit rate didn't rise the way the
  task hoped (2.2% raw hits / 505, ~0.2% net Greenhouse-only): most
  candidates' real /careers pages are client-side-rendered SPAs whose
  ATS integration happens via a JS fetch() call after page load, which
  never appears in the raw HTML a plain GET returns — the same
  limitation ARCHITECTURE.md already flagged in Session 6 ("a page that
  truly builds its job list client-side after load... would require an
  explicit Playwright/headless-browser decision"), now observed at
  real scale rather than as a one-company caveat. This method's actual
  win wasn't hit-rate — it was precision (0 collisions, vs. Session 18's
  3) and unlocking Comeet entirely.
- Fixed `--teal` in pwa/styles.css using the two real hex values Elad
  gave directly in this session's task (#4FD1C5 dark / #2A9D8F light),
  replacing the --radar-green alias Session 17 used as a placeholder.
  demo.html itself (which had been sitting untracked in the working
  directory as of Session 18) is deliberately not part of this repo —
  Elad's call, not referenced as a source. Verified via
  getComputedStyle in both themes: rgb(79, 209, 197) and rgb(42, 157,
  143) respectively — exact match.
- Live smoke test against the real 58-company list: 58/58 succeeded (0
  failures — the Session 18 failure-visibility fix had nothing to show
  this run, confirmed via a clean `failures: []` in latest_scan.json
  rather than assumed), 31 matches (11 new, 20 still_open). Real
  elapsed time: ~66 seconds — still well short of the ~5-minute target,
  consistent with Greenhouse count being the real pacing floor (38 real
  Greenhouse companies now, not ~200).
- Test suite: 103/103 passing, unchanged (no Python logic changed this
  session — companies.json and pwa/styles.css are data/config only).

## 2026-08-12 — Session 20: research-sourced candidates, no guessed names
- First harvesting session where the candidate list wasn't sourced by
  this session's own research pass — Elad/planning-Claude supplied ~182
  fresh, real, currently-active Israeli company names directly (deduped
  against the 58 companies already verified going in, 8 already present
  and correctly skipped), citing real sources (Calcalist/CTech's 2026
  funding-rounds coverage, StartupBlink's Israel ranking), with the
  sourcing session's own explicit warning built in: several
  generic-English-word names (Above, Bold, Neo, Frame, Willow, Swan,
  Onyx, ...) carry the exact same collision risk Session 18 hit with
  shield/bold/vim.
- Reused Session 19's fixed domain-first discovery method unchanged
  (fetch each candidate's own real career page through the Compliance
  Agent, read the actual ATS off a redirect or embedded link, confirm
  against the real API) — no new bugs this time, the redirect-chase fix
  held up against a completely different candidate list.
- Real result: 8 raw Stage A hits, 7 confirmed at Stage B (1 - "Slice" -
  resolved to a generic Greenhouse embed-script path, "embed", not a
  real company slug; correctly dropped when boards-api.greenhouse.io/v1/boards/embed/jobs
  returned nothing real). Of the 7 confirmed, 2 were rejected on manual
  review before touching companies.json: "Enigma" resolved to
  enigma.com, a NYC data company with zero Israel signal across 9
  postings — almost certainly the generic-word collision the sourcing
  session warned about, not the Israeli company Calcalist's coverage
  actually meant; "CopilotKit" resolved to a real Lever board but its
  one open role (Seattle) also carried zero Israel signal and identity
  wasn't confirmed strongly enough to include on a resolving-slug-plus-
  guess alone.
- Net addition: 5 companies (Guardio, Guidde, ScaleOps, Zeroport, ZyG) -
  2 new Greenhouse (Guidde, ScaleOps) + 3 new Comeet (Guardio, Zeroport,
  ZyG), each confirmed with a direct Israel-located posting, not just a
  resolving slug. companies.json: 58 -> 63 (Greenhouse: 38 -> 40,
  Comeet: 12 -> 15).
- 8 of the supplied candidates were already in companies.json going in
  (AppsFlyer, Cato Networks, Cyera, Oasis Security, QuantHealth,
  Tomorrow.io, Torq, Triple Whale) - correctly deduplicated before any
  live fetch was made against them.
- Live smoke test against the real 63-company list: 61/63 succeeded, 2
  genuine transient ReadTimeouts (Cato Networks, Payoneer - same
  real-failure category as every prior transient timeout this project
  has seen, both visible with their real error text in latest_scan.json's
  failures list, not just a bare count). 36 matches (5 new, 31
  still_open). Real elapsed time: ~97 seconds - still well short of
  the ~5-minute target (40 real Greenhouse companies now, not ~200).
- Test suite: 103/103 passing, unchanged (no Python logic changed).

## 2026-08-14 — Session 21: Playwright-based discovery (real negative result)
- Added ADR-0031 (DECISIONS.md was still at ADR-0030, same recurring
  doc/reality gap - added per ADR-0030's own protocol from the task's
  unambiguous framing): Playwright approved for discovery/onboarding
  sessions only, never the production scan pipeline, which stays on
  plain httpx per ADR-0001/ADR-0021.
- Installed playwright + downloaded its Chromium binary after explicit
  confirmation (a real ~115MB binary download, not just a pip package).
  Isolated as requirements-discovery.txt, separate from requirements.txt
  - the GitHub Actions workflow never installs it.
- Refactored ComplianceAgent: extracted `gate(url)`, an async context
  manager holding the robots.txt check + rate-limit wait + timestamp
  recording, with fetch() now just that gate wrapped around one httpx
  call. Lets a Playwright page load get identical compliance discipline
  without duplicating any of ComplianceAgent's own logic. Verified the
  refactor preserves fetch()'s exact original behavior (existing
  compliance test suite unchanged, still passing) before adding 4 new
  tests for gate() itself.
- Built discovery/playwright_probe.py (PlaywrightProbe): loads a real
  career page with headless Chromium, waits for real network-idle (not
  a fixed sleep), inspects the final URL/rendered DOM/every observed
  network request for Greenhouse/Lever/Comeet signals - the same
  detection targets as the static method, plus one static fetch
  structurally can't see at all (a post-load JS fetch() call to the ATS
  API). 13 tests using a hand-rolled fake browser/page (no real
  Chromium needed in the automated suite) - including one written after
  a real bug surfaced live: page.content() can raise its own "page is
  navigating" error right after a goto() timeout, not just goto()
  itself; both are now handled, and a regression test locks the fix in.
- Real test batch: 20 specific companies pulled directly from Sessions
  19/20's own "no ATS link found" logs (Coralogix, Guesty, Totango,
  MorphiSec, BlazeMeter, Overwolf, Namogoo, HiBob, Aidoc, Centrical,
  Artlist, Attenti, Claroty, Datarails, DriveNets, Definity, Quantum
  Art, Reco, Zenity, Upwind) - extended from an initial 12 to 20 after
  the first batch came back with zero hits, to rule out an unlucky
  selection before concluding anything.
- Real result: 0 new ATS signals found across all 20. 3 (BlazeMeter,
  Aidoc, Centrical) are genuinely, currently blocked by their own real
  robots.txt (confirmed via a fresh, uncached check) - Playwright
  correctly respected that, proving the compliance-reuse goal, but
  meaning those 3 were never actually browser-inspected. 1 (MorphiSec)
  surfaced a separate real finding: a persisted robots_cache.json entry
  said "disallowed" when the live robots.txt (re-checked directly - no
  Disallow rules for User-agent: * at all) says otherwise, most likely
  a transient bot-protection response at the original check time -
  corrected in the cache; Playwright still found nothing there either
  once genuinely inspected. The remaining 16 were fully, cleanly
  inspected and came back with zero signal every time.
- Honest conclusion, not spun positive: for this batch, JS-rendering
  was not the actual blocker - these companies most likely use an ATS
  outside this project's four supported platforms entirely. Scaling
  Playwright discovery up to the full ~500+ candidate pool is not
  recommended without first finding at least one genuine positive-
  control case to confirm the mechanism pays off somewhere real.
- 0 new companies added to companies.json this session (nothing to
  confirm - a real, disclosed negative result, not a gap in the work).
- Test suite: 121/121 passing (was 103: 4 new for ComplianceAgent.gate(),
  13 new for the Playwright probe, 1 new regression test for the
  content()-after-timeout bug), 0 real network calls in the automated
  suite (the Playwright browser was only ever driven manually against
  real companies for this session's proof batch, never inside pytest).
- Session 20's 5 companies (Guardio, Guidde, ScaleOps, Zeroport, ZyG)
  remain uncommitted, exactly as Elad left them - not touched, not
  re-verified, not assumed committed.

## 2026-08-15 — Session 22: fix robots_cache staleness (combined approach)
- Real incident, not a hypothetical: Session 21's MorphiSec re-check
  found a persisted robots_cache.json entry saying "disallowed" when a
  fresh live check of the real robots.txt (no Disallow rules for
  User-agent: * at all) said otherwise - most likely a transient
  bot-protection response at whatever moment it got cached. Under the
  old 7-day TTL, one bad moment could silently skip a real company's
  entire scan for a full week with zero visible symptom.
- Asymmetric TTL: allowed:true keeps the original 7-day trust window
  (being wrong there costs nothing - we just fetch normally, which is
  always safe). allowed:false now gets a 1-hour window instead
  (ROBOTS_CACHE_BLOCKED_TTL_SECONDS) - a bad "blocked" self-heals
  within the hour, not the week.
- Double-check before persisting a blocked result: a fresh "disallowed"
  live check is no longer trusted off a single call - _is_allowed()
  waits blocked_recheck_delay_seconds (5s default, overridable) and
  checks once more; only two agreeing disallowed results get cached as
  false. A one-time glitch essentially never repeats that fast; a real
  Disallow rule always does.
- Live re-verification: re-checked morphisec.com from a completely
  fresh cache under the new logic - resolved to allowed:true on the
  very first live check (the double-check path never even had to
  trigger, since it wasn't blocked to begin with), consistent with the
  original having been a one-off glitch, not a persistent block.
- 5 new tests: cached-false-past-short-TTL triggers a recheck;
  cached-true-past-short-but-within-long-TTL does not (proves the two
  TTLs are genuinely asymmetric, not the same number twice); a single
  transient block followed by allowed persists true; two consecutive
  blocked responses persist false as before; the recheck genuinely
  waits the configured delay between the two live checks (measured via
  real call timestamps, not just trusted).
- Test suite: 126/126 passing (was 121: 5 new), 0 real network calls in
  the automated suite - the live MorphiSec re-verification was a
  separate, disclosed manual check, same as every prior session's live
  smoke tests.

## 2026-08-15/17 — Session 23: fix the mascot (real root cause, partially blocked)
- Real root cause confirmed (planning-Claude compared directly against
  the actual demo.html, which Elad has decided will never be committed
  to this repo): Session 15 never had that file, so instead of a single
  static photo it invented a 4-frame flap-cycling animation
  (bat-frame-1..4.png cropped from batPoses.png via Pillow, swapped on
  a 500ms setInterval) - a different design, not a smaller mismatch.
- Removed the entire frame-cycling mechanism: initMascotAnimation() and
  its setInterval deleted from app.js; index.html's mascot <img> now
  references a single real_mascot.png with no id/JS hook; deleted
  pwa/bat-frame-1.png through -4.png and pwa/mascot-widget.png;
  service-worker.js's SHELL_FILES list updated to match (cache name
  bumped v1 -> v2 so the old cached frames actually get evicted on
  next activation, not just stop being referenced).
- batPoses.png (root-level source, outside pwa/) is not referenced
  directly anywhere in the shipped app - confirmed via a full-repo
  grep, not assumed - only its now-deleted derivatives were. Left it
  on disk rather than deleting it: it's a raw source asset outside the
  deployed directory, deleting original source material is a more
  irreversible call than removing generated derivatives, and the task
  only asked to check its usage, not to delete it.
- Real blocker, disclosed rather than worked around: real_mascot.png
  itself was never actually placed anywhere on disk this session
  (checked the repo, pwa/, the scratchpad, Downloads, Desktop) despite
  the task describing it as "provided." Asked twice; got no answer
  either time. index.html/service-worker.js now correctly reference
  real_mascot.png by the name it should have, but the file itself is
  still missing - the PWA will show a broken image in that spot until
  it's actually placed in pwa/.
- Second real blocker found while investigating, not assumed away: the
  task describes a 5-element radar structure (.radar-screen,
  .range-ring x3, .crosshair, .sweep-bg, .pct-badge) as "already
  correctly built" in the current widget - it isn't. This repo's actual
  pwa/styles.css only ever had a single .ping-ring. Session 15 built a
  simpler design than the real reference from the start; that gap was
  never caught until this session. Did not invent the missing
  structure from a text description alone - that risks the exact
  "guessed instead of using the real thing" failure mode this session
  exists to fix. Left the existing .ping-ring in place, unchanged.
- Also flagged, not silently corrected: the task's "200px badge" sizing
  claim doesn't match this repo either (currently 84px desktop / 64px
  mobile, and Session 17 never touched mascot sizing) - left unchanged
  pending real clarification, same reasoning as the radar-structure gap.
- Nothing committed or pushed this session - a genuinely incomplete,
  partially-broken PWA state (missing image file) shouldn't ship
  regardless of the standing per-action confirmation requirement.

## 2026-08-19 — Session 24: exact radar structure + real mascot file placed
- Both of Session 23's real blockers resolved with real, verbatim
  values from planning-Claude having now seen the actual reference
  file directly - the same pattern that worked for the wordmark fix
  (Session 17) and the --teal color (Session 19).
- real_mascot.png confirmed placed at pwa/real_mascot.png by Elad -
  verified directly (not assumed): 480x320, RGBA with real alpha
  transparency, exactly matching spec. Loads and renders correctly
  (img.complete === true, naturalWidth/Height 480x320).
- Replaced the entire .mascot-widget/.ping-ring implementation (Session
  15's guess, since it never had the real file) with the exact
  .sonar-corner structure given verbatim: radar-screen (radial-gradient
  circle), 3 concentric range-rings, a crosshair (via ::before/::after
  pseudo-elements), the rotating sweep-bg (conic-gradient, 3s linear
  infinite, mix-blend-mode screen), the mascot image, and a pct-badge
  ("?%" placeholder - the real percentage is separate future work, the
  usage-budget calculator isn't wired into the PWA yet). Renamed the
  container from .mascot-widget to .sonar-corner to match the real
  reference exactly, rather than keeping the old name and adapting
  internals to fit - one less layer of naming drift from here on.
- Verified element-by-element via getComputedStyle, not visual
  inspection (same standard as Session 17's wordmark fix): every
  position/inset/size/color/animation value on .sonar-corner,
  .radar-screen, all three .range-ring variants, .crosshair (including
  both pseudo-elements), .sweep-bg (including animation-name/duration/
  timing-function/iteration-count/mix-blend-mode), .sonar-corner img,
  and .pct-badge matches the given spec exactly - confirmed via direct
  computed-value comparison, not eyeballing.
- Old .ping-ring/.mascot-widget/@keyframes ping fully removed - grepped
  the whole pwa/ tree afterward and confirmed zero remaining references
  outside historical doc comments.
- Included the given onclick="showView('stats', ...)" verbatim, as
  instructed - showView() and the tabs system it references don't
  exist in this codebase yet (a future session's work, same category
  as the pct-badge placeholder), so clicking the mascot currently logs
  a harmless "showView is not defined" console error rather than doing
  anything. Flagged, not silently dropped or worked around.
- Known, pre-existing, unrelated finding while verifying live: the
  service worker fails to register in this sandboxed local-preview
  environment ("unknown error occurred when fetching the script") -
  confirmed this is not caused by anything changed this session (no
  service-worker.js logic touched), consistent with similar sandbox
  friction noted in Sessions 15/17/19.
- No automated tests affected (PWA-only change, no Python touched);
  126/126 still passing.

## 2026-08-19 — Session 26: remove the redundant mascot badge + broken onclick
- Session 25's investigation confirmed the real budget percentage
  already renders correctly in .budget-widget (working since Session
  15, untouched) - the mascot's .pct-badge was a separate, dead,
  never-wired "?%" placeholder duplicating nothing real. Elad's call:
  don't wire it up, remove it - the real number is already shown
  properly elsewhere.
- Removed `<div class="pct-badge">?%</div>` from index.html and its
  `.sonar-corner .pct-badge` CSS rule from styles.css entirely - not
  hidden, not commented out. Grepped pwa/ afterward for "pct-badge" -
  zero remaining references outside this session's own doc comment.
- Removed the onclick="showView('stats', ...)" attribute from
  .sonar-corner - confirmed (again, per Session 25) that showView()
  and any .tab elements don't exist anywhere in this codebase, so there
  was nothing for it to ever call. Also dropped .sonar-corner's
  `cursor: pointer` - with nothing to click, a pointer cursor would
  have implied an interaction that no longer exists.
- Verified live, not assumed: served pwa/ locally, confirmed via
  getComputedStyle/DOM query that .pct-badge no longer exists, the
  onclick attribute is null, cursor resolves to "auto". Clicked
  .sonar-corner programmatically and confirmed no new console error
  appears (the only console error present is the same pre-existing,
  unrelated service-worker registration failure in this sandboxed
  environment, noted in Sessions 15/17/19/24). Confirmed .budget-widget
  is completely unaffected: real data still renders correctly (e.g.
  "5.23 / 2000 min", "0.26%").
- .budget-widget and renderBudget() were not touched at all this
  session, per explicit scope.
- Test suite: 126/126 passing, unchanged (PWA-only change).

## 2026-08-19 — Session 27: service worker skipWaiting/clients.claim fix
- Real bug: every prior deploy required a hard refresh or incognito
  window to see changes, because the service worker waited to activate
  a new version until every old tab closed - confusing enough that it
  made the mascot fix look broken earlier when it was really just a
  stale cache.
- Checked before changing anything, per this project's own discipline:
  self.skipWaiting() was already present in the install handler since
  Session 15 - the task's premise that it needed to be added didn't
  match reality. Flagged rather than silently re-added as a no-op.
- The real, genuine gap: self.clients.claim() was already being called
  in the activate handler too, but as a bare statement, not wrapped in
  its own event.waitUntil() - the browser is free to consider the
  activate event finished as soon as the existing cache-cleanup
  waitUntil settles, without ever actually waiting for claim() to
  finish handing control of already-open tabs to the new worker. Fixed
  by wrapping it: event.waitUntil(self.clients.claim()) as a second,
  independent waitUntil call alongside the existing cache-cleanup one -
  each waitUntil() call independently extends the event's lifetime, so
  this doesn't replace or reorder the cleanup logic.
- Bumped CACHE_NAME from thescanner-shell-v2 to -v3, same pattern
  Session 24 already used, so this deploy itself is real evidence the
  fix works (a version bump that should now take over live tabs
  without a hard refresh).
- Verification, disclosed honestly: this sandbox's service worker
  registration fails outright ("unknown error occurred when fetching
  the script") - the same pre-existing limitation noted in Sessions
  15/17/19/24/26, confirmed again, not a regression from this change.
  Could not perform the task's requested live "old tab picks up new
  version without hard refresh" test in this environment as a result.
  Verified what was possible instead: the file's JS is syntactically
  valid (checked via new Function() against the actual served file
  content), and the fix was verified by direct code reading against
  the documented ServiceWorker lifecycle semantics (skipWaiting() on
  install + a properly-awaited clients.claim() on activate is the
  standard, well-documented fix for exactly this "requires hard
  refresh" symptom). The real end-to-end confirmation needs an actual
  deploy Elad can reload against, which this session's push enables but
  can't itself observe from inside this sandbox.
- Test suite: 126/126 passing, unchanged (PWA-only change).
