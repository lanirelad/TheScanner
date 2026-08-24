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

## 2026-08-19 — Session 28: role selection + mark-as-applied (local-only)
- Two real, functional PWA features, both purely local to the device
  per ADR-0011/ADR-0014 - neither ever touches roles.json, run.py's
  scan logic, or any shared/backend data.
- Added job_id to latest_scan.json's matches (the one explicitly-
  allowed backend change) - mark-as-applied needs a stable per-job key
  to store application_status against, and job_id (already
  sha256(company|absolute_url), ADR-0026) is exactly that, already
  computed, so reusing it means local storage and the backend's own
  dedup logic can never disagree about which job is which.
- Built pwa/preferences.js: a new, separate file (not a section of
  app.js) holding every pure function and localStorage wrapper for both
  features - isRoleEnabled, shouldShowJob, toggleRoleFilter,
  availableRoleCategories, isApplied, toggleApplied, plus thin
  load/save wrappers. Deliberately separate from app.js because app.js's
  bottom section calls main()/initThemeToggle() immediately on load,
  which needs a real DOM and successfully-fetchable JSON - a pure-logic
  file with zero side effects on load can be tested completely
  independently of that bootstrap.
- Role selection: no settings modal - a small toggle row ("Show roles")
  appears above the job list, one checkbox per role category actually
  present in latest_scan.json's matches (union'd with any category the
  device has an explicit preference for, so a previously-disabled
  category doesn't silently reappear just because it has zero matches
  this run). Deliberately does NOT fetch or duplicate roles.json into
  pwa/ - since every match in latest_scan.json already only ever comes
  from a category roles.json's own `enabled` flag allowed through
  (core/filters.py, Session 11), "no stored preference yet" and "show
  everything the backend already decided to include" are the same
  thing by construction. Stored in localStorage under
  thescanner:role_filters as { [role_category]: false } - only
  explicit off-toggles are stored, "on" is the implicit default, so a
  device that never opens the toggle panel keeps an empty {} forever.
- Mark as applied: a button on every job card toggling
  thescanner:applied_jobs (localStorage, keyed by job_id) between
  present (applied) and absent (not_applied, the default). Applied
  cards dim to 0.6 opacity and the button becomes "✓ Applied" -
  distinguishable without fighting the new/still_open badge for
  attention, since that badge is about the posting, this is about the
  user's own progress on it.
- Both features use event delegation (on #role-filter-toggles and
  #job-groups respectively), not per-element listeners - both
  containers get rebuilt wholesale on every render, so a listener bound
  to one specific checkbox/button would be silently lost on the very
  next re-render otherwise.
- Real test coverage, not just visual behavior: this project has no
  Node.js-based JS test runner (none existed before this session, and
  this sandbox has no Node.js installed at all - checked directly, not
  assumed). Built pwa/tests/preferences.test.html instead - a real,
  dependency-free HTML+JS test harness that loads preferences.js
  exactly as index.html does and runs real assertions in an actual
  browser (the environment this code actually runs in anyway), no
  build step or framework needed to re-run it. 23/23 real assertions
  passing, covering both features' pure logic including round-trips
  through real localStorage and confirming toggle functions don't
  mutate their input. Caught and fixed a real bug in the test harness
  itself while building it: JSON.stringify-based equality is key-order
  sensitive, which produced two false failures against otherwise-
  correct code - replaced with a proper order-independent deepEqual.
- Verified live end-to-end, not just via the pure-function harness: ran
  a real run.py live smoke test (63 attempted, 62 succeeded, 1 genuine
  transient ReadTimeout - ScaleOps, 36 matches) to get real data with
  job_id populated, then in a real browser: toggled a role category off
  and confirmed matching cards actually disappeared (36 -> 8 cards,
  confirmed via checking no DevOps Engineer role-tags remained visible),
  toggled it back on (36 cards returned), marked a job applied and
  confirmed the card visibly updated (button text, applied class,
  computed opacity 0.6) and localStorage was written correctly, then
  did a real full page reload and confirmed both the applied mark and
  the role-filter state survived - not assumed from the code, actually
  observed surviving a real reload.
- service-worker.js: added preferences.js to SHELL_FILES, bumped
  CACHE_NAME v3 -> v4 (same pattern as Sessions 24/27) so this deploy
  itself picks up the new file for offline/cache-first use.
- Test suite: 126/126 passing (Python side unchanged in count - the
  job_id addition updated existing assertions, not new test functions).

## 2026-08-19 — Session 29: fix Cloudflare-edge caching of service-worker.js
- Session 27's skipWaiting()/clients.claim() fix was correct at the
  code level, but Elad still needed a hard refresh after the next
  deploy - flagged then as possibly a Cloudflare-edge caching issue
  upstream of the browser entirely, which a local dev server can never
  reproduce. This session investigated and confirmed that hypothesis
  empirically rather than assuming it.
- Real headers, checked directly on the live URL
  (https://thescanner.lanirelad.workers.dev/service-worker.js), not
  guessed: Cache-Control: public, max-age=0, must-revalidate (Cloudflare
  Workers' own documented default for static assets) *and*
  CF-Cache-Status: HIT on the same response - Cloudflare's edge served
  the file straight from cache without reaching the origin at all,
  despite max-age=0. Confirmed this isn't unique to service-worker.js -
  styles.css showed the identical default/HIT combination - so the
  platform's default behavior isn't broken, it's just wrong specifically
  for the one file whose entire job is detecting when it's outdated.
- First attempt used Cache-Control: no-cache, per the task's own
  suggestion - checked Cloudflare's documented semantics before trusting
  it and found no-cache means "cache it, but revalidate with origin
  before serving," which doesn't explain away the observed HIT and
  isn't strong enough to guarantee the edge always reaches origin.
  Switched to Cache-Control: no-store - Cloudflare's own documented
  directive for skipping edge caching entirely - before shipping it,
  rather than assuming the first guess would work.
- Added pwa/_headers (Cloudflare Workers static-assets convention,
  confirmed via Cloudflare's own docs to apply to a pure static-assets
  deployment with no custom Worker script, which is what this project
  is) scoped to exactly /service-worker.js - every other static asset
  keeps Cloudflare's normal caching behavior, which is desirable for a
  cache-first PWA shell (ARCHITECTURE.md §9a).
- No Python/backend changes, no app code changes - purely a Cloudflare
  static-assets configuration file.
- Test suite: 126/126 passing, unchanged.

## 2026-08-19 — Session 30: "Ignore" state + Ignored section
- Extended Session 28's boolean applied/not-applied into a real tri-state
  per-job status: not_set / applied / ignored, mutually exclusive.
- State model: kept preferences.js's key/value approach but moved to a
  new key (thescanner:job_status, values "applied"/"ignored") rather
  than overloading the old thescanner:applied_jobs key's boolean shape.
  Confirmed the real data-loss risk before choosing this, not assumed
  it away: Elad has been actively using the PWA since Session 28
  shipped (he's the one who reported Session 27's caching bug from real
  usage), so a clean break risked silently discarding marks he'd
  already made. Chose migrate-on-read instead of a one-time destructive
  migration: loadJobStatuses() merges the legacy key's `true` entries in
  as "applied" every time it's called, only when the new key has no
  opinion yet for that job_id - the legacy key is never written to or
  deleted, so there's no window where a read could observe a
  half-migrated state and no risk of losing the original data even if
  something goes wrong. Verified live with a real seeded legacy entry:
  it renders correctly as applied on first load with zero interaction,
  and survives being read repeatedly without ever being touched.
- Added an "Ignore" button next to "Mark as applied" on every job card.
  Both buttons funnel through one delegated click handler (same
  "container rebuilt wholesale, needs delegation" reasoning as Session
  28) that loads the current statuses once, toggles the right job_id
  via toggleApplied/toggleIgnored, and re-renders.
- Rendering: preferences.js's new partitionByIgnored(matches, statuses)
  pure function splits ignored jobs out before the new/still_open
  grouping happens; a new "🙈 Ignored" section renders them at the very
  bottom, separated by a dashed top border. Applied jobs are
  deliberately NOT partitioned - they stay in their normal new/
  still_open group, same position and visual treatment Session 28 built
  (a dimmed card, "✓ Applied" button) - only ignored jobs move.
- Mutual exclusivity enforced in one place (setJobStatus) rather than
  scattered checks: setting any status always fully replaces whatever
  was there before, so there's no code path that could leave a job
  marked both applied and ignored. Verified both directions live and in
  the test harness: clicking Ignore on an already-Applied job moves it
  straight to Ignored (not both), and clicking Mark as applied on an
  Ignored job moves it straight to Applied.
- Real test coverage: extended pwa/tests/preferences.test.html (same
  no-Node.js dependency-free HTML+JS harness as Session 28) to 38/38
  passing - covers getJobStatus/isApplied/isIgnored, setJobStatus's
  mutual-exclusivity enforcement, both toggle functions' cross-status
  transitions, partitionByIgnored, and five dedicated migration tests
  (fresh migration, read-only/non-destructive, new-key-supersedes-
  legacy for a shared job_id, non-overlapping merge, missing-keys
  fail-safe).
- Verified live end-to-end beyond the harness: seeded a real legacy
  thescanner:applied_jobs entry, confirmed it renders as applied with
  zero interaction, confirmed toggling Ignore on it produces the
  correct migrated-applied -> ignored transition (moves to the Ignored
  section, legacy key untouched, new key correctly says "ignored" not
  both), confirmed toggling Mark as applied afterward correctly reverses
  it, and confirmed both the applied state and the Ignored section
  survive a real full page reload.
- Bumped service-worker.js's CACHE_NAME v4 -> v5 - app.js/styles.css/
  preferences.js all changed substantively this session, and those are
  cache-first shell files; without a version bump already-installed
  devices would keep serving the pre-Ignore-feature JS/CSS indefinitely
  regardless of Session 29's edge-caching fix, which only ever applied
  to service-worker.js itself.
- Test suite: 126/126 Python tests passing, unchanged (no backend
  changes this session).

## 2026-08-19 — Session 31: real failure detail + days-until-budget-reset
- Part 1: rendered latest_scan.json's `failures` list (real company +
  error text, built Session 18) for the first time - previously only a
  bare Failed count was shown. New app.js renderFailures() populates a
  native <details>/<summary> disclosure just under the summary strip;
  hidden entirely on a clean scan, expandable to a per-company error
  list otherwise. No new data shape needed - the data was already
  correct, just unrendered.
- Part 2: added a real, configurable GitHub Actions billing-cycle reset
  day - GITHUB_BILLING_RESET_DAY_OF_MONTH in usage/budget.py, default 1,
  same explicit-constant pattern as FREE_TIER_MONTHLY_MINUTES. Confirmed
  via research that GitHub's real reset date depends on each account's
  personal billing cycle and is not safely assumable as the 1st, so this
  is deliberately a named, documented, editable value rather than a
  hardcoded assumption. Elad needs to check Settings -> Billing & plans
  on his real account and correct the constant if it isn't day 1.
- Computed days_until_reset server-side in compute_usage_summary (new
  _next_reset_date() helper, calendar.monthrange-based clamping for
  reset days that don't exist in every month, e.g. 31 in a 30-day
  month or February) rather than in the PWA's JS - `now` and
  `reset_day_of_month` are both injectable parameters, same
  deterministic-testing pattern as schedule/gate.py's `now_utc`.
  usage_summary.json gained two new fields: reset_day_of_month,
  days_until_reset. Rendered in .budget-widget via a new #budget-reset
  line.
- Regenerated pwa/usage_summary.json by hand from the real current
  usage_log.json and today's date, since no live scan ran this session
  to regenerate it via run.py.
- Bumped service-worker.js's CACHE_NAME v5 -> v6 (index.html/app.js/
  styles.css all changed and are cache-first shell files).
- No pure-JS changes to preferences.js this session (all new logic is
  server-side Python) - pwa/tests/preferences.test.html stays at
  38/38, unchanged.
- Verified live in the sandbox browser against the real current
  latest_scan.json (which already had one real failure, ScaleOps/
  ReadTimeout) and usage_summary.json - failure text renders correctly,
  the detail hides correctly when failures is empty, and the reset
  countdown matches the real computed value.
- Test suite: 131/131 Python tests passing (5 new tests covering the
  default reset day, today-is-reset-day, mid-month countdown,
  month-boundary rollover, and short-month/February clamping).

## 2026-08-20 — Session 32: Growth playbook Phase 1 — ATS pattern recognition
- Built recognition-only fingerprints for Workday, SmartRecruiters, and
  iCIMS in discovery/playwright_probe.py - deliberately separate from
  the existing Greenhouse/Lever/Comeet detection, since this project has
  no adapter for any of these three. Each verified against one real live
  example before being trusted: NVIDIA (Workday), Nielsen
  (SmartRecruiters), Wake County Public Schools (iCIMS) - all 3 correctly
  recognized via a real compliance-gated Playwright probe.
- Re-ran recognition against Session 21's real 16-zero-signal-company
  batch (plus MorphiSec, plus a fresh re-check of the 3 previously
  robots.txt-blocked companies) - real career-page URLs had to be
  re-derived via web research this session, since Session 21's own
  harvesting script and candidate list were never committed to the repo.
- Honest result on the actual task scope: 0 of ~20 companies checked use
  Workday, SmartRecruiters, or iCIMS - a real, disclosed negative result.
- Real result found instead: re-deriving current career-page URLs
  surfaced 8 real hits on the 4 platforms this project already
  supports - 6 Comeet (Reco, Zenity found directly via PlaywrightProbe;
  Overwolf, Artlist, Claroty, DriveNets found via web research after a
  real gap was found - Comeet's widget domain is comeet.co, not
  comeet.com, which the existing CM_RE regex doesn't match at all) and 2
  Greenhouse (Datarails, newly listed since Session 21; Aidoc, recovered
  from Session 21's robots.txt-blocked list). All 8 merged into
  companies.json (63 -> 71) after live API verification.
- Isolated a real, non-transient block distinct from Session 22's
  transient-glitch case: BlazeMeter and Centrical's own WAF returns HTTP
  403 to this project's httpx client specifically (confirmed via direct
  comparison - curl and a real browser both get through cleanly at the
  same moment httpx doesn't) even on robots.txt itself, which
  ComplianceAgent's existing 401/403 handling correctly treats as
  disallow-everything. Documented as intentional, not a bug.
- Created companies_unscannable.json (new file, ARCHITECTURE.md 14, new
  section - neither existed before this session, backfilled per
  ADR-0030's protocol) with 4 positively-confirmed entries: Totango
  (uses Rippling's ATS, a real platform observed live but out of this
  session's scope), Namogoo (blocked by an active bot-protection
  challenge, not robots.txt), BlazeMeter and Centrical (the WAF finding
  above). Deliberately excludes companies with no recognized signal at
  all (Coralogix, Guesty, MorphiSec, HiBob, Attenti, Definity, Quantum
  Art, Upwind) - those are honest unknowns, not positive findings, and
  stay recorded in PROGRESS.md's prose instead.
- Backfilled PLAN.md's "Company-growth playbook" section (also
  referenced by the task as if it already existed, also didn't) -
  documents Phases 0/0.5 from Sessions 18-21 and this session's Phase 1
  result, plus two flagged-not-built opportunities: extending Comeet
  detection to catch the comeet.co widget domain, and the still-open
  decision on whether any unsupported platform is common enough to
  justify a fifth adapter (one data point - Totango/Rippling - isn't
  enough to decide that yet).
- Test suite: 140/140 passing (was 131: 9 new for the fingerprint
  logic). Live python run.py smoke test against the updated 71-company
  companies.json: 71/71 attempted and succeeded, 0 failures, 5 immediate
  new real DevOps-category matches from the newly added companies.
- No adapter built for any of the three recognized-but-unsupported
  platforms, per the task's explicit scope.

## 2026-08-20 — Session 33: Cloudflare Worker backend - push subscriptions + manual trigger
- Checked directly (not assumed) whether Elad's two setup prerequisites
  were done: neither the fine-grained GitHub PAT nor the
  thescanner-subscriptions KV namespace exists yet. Built everything
  that doesn't depend on either, stopped cleanly at the points that do.
- wrangler.jsonc gained a real main field (worker/index.js) alongside
  the existing static assets.directory - confirmed via Cloudflare's
  current docs that assets.run_worker_first defaults to false, so the
  existing PWA keeps being served exactly as before and the Worker only
  runs for the three new API paths, none of which collide with a real
  static file. kv_namespaces deliberately left out until the real
  namespace ID exists; the exact entry to add is documented in a
  wrangler.jsonc comment.
- Generated a real VAPID key pair locally (deterministic P-256 ECDSA,
  no live API needed). Implemented all three routes
  (/api/push-subscribe, /api/trigger-scan, /api/notify) plus a
  hand-rolled Web Push crypto module (worker/webpush.js - RFC 8291/8188
  aes128gcm encryption, RFC 8292 VAPID signing) on native crypto.subtle
  rather than the web-push npm package, since this repo has no verified
  build step for Cloudflare's Git-integration deploy to run against.
- Resolved a real discrepancy between two sources on GitHub's
  workflow_dispatch endpoint's success response by checking a dated,
  authoritative GitHub changelog entry directly: the true default is
  still 204 No Content, not the 200-with-run-details a generic doc
  summary claimed - opted into the newer return_run_details:true
  behavior explicitly rather than assuming either behavior blindly.
- /api/trigger-scan protected by a shared-secret header checked against
  a real, randomly-generated TRIGGER_SECRET value (Python's CSPRNG) -
  deliberately simple, matching the task's own "don't over-engineer
  auth for a personal single-owner app" instruction.
- Added defensive guards so a route missing its KV binding or a secret
  returns a clean, diagnosable JSON 500 instead of crashing - concretely
  relevant this session since both real prerequisites are still
  missing.
- Real verification, real limits disclosed: no live Worker/KV
  namespace/PAT/subscribed device exist yet, so the GitHub dispatch call
  and KV storage were never tested end-to-end - not possible this
  session. What was verified, in a real browser's crypto.subtle (the
  same WebCrypto standard the Workers runtime implements): a new
  dependency-free test harness (worker/tests/webpush.test.html, 5/5
  passing, same pattern as pwa/tests/preferences.test.html)
  independently re-implements RFC 8291's receiving side and confirms a
  round-trip decrypt recovers the exact original bytes, no nonce reuse
  across calls, and a signed VAPID JWT verifies against its own public
  key (and correctly fails against tampered claims) - including with
  the real generated key pair, not just a random test one. Routing
  logic (404/405/500-guards/400-validation/real SHA-256 KV keying/401
  on a wrong secret/the full notify sent-removed-failed accounting with
  three simulated push-service outcomes) verified live with fake
  KV/fetch standing in for Cloudflare's real bindings.
- Docs updated: ARCHITECTURE.md SS11 (real implementation replacing the
  "not built yet" sketch), DEPLOY.md (fully rewritten - was still
  describing the superseded GitHub Pages plan).
- No PWA frontend changes this session, per the task's explicit scope.
- Test suite: 140/140 Python tests passing, unchanged. 5/5 new
  worker/tests/webpush.test.html assertions passing.

## 2026-08-20 — Session 34: wire the real KV namespace + verify the Worker end to end
- Added the real kv_namespaces binding to wrangler.jsonc (binding name
  SUBSCRIPTIONS, confirmed against worker/index.js). Asked Elad to
  confirm all four secrets directly rather than trust the task text.
- Real incident, resolved live: TRIGGER_SECRET and the VAPID keys
  briefly behaved as unset despite being confirmed set (resolved after
  a re-check/short delay); GITHUB_PAT then kept failing even after
  being confirmed correctly listed - diagnosis surfaced that the real
  KV namespace had been deleted from the Cloudflare account mid-session
  (while troubleshooting the secret, not something asked for), which
  was blocking every subsequent Worker config save. Elad created a
  replacement namespace; wrangler.jsonc was updated to the new real ID
  and pushed, which cleared the error and let GITHUB_PAT save
  successfully.
- Real end-to-end confirmation - the actual point of this session: a
  live curl to /api/trigger-scan returned a real workflow_run_id and
  html_url, and Elad independently confirmed via the GitHub Actions tab
  that the run genuinely exists. First real, live proof the Worker ->
  GitHub API -> workflow_dispatch path actually works.
- Real KV read/write confirmed against the replacement namespace: a
  synthetic push-subscribe call's stored key was independently verified
  to be exactly sha256(the test endpoint used), retrieved correctly by
  a follow-up /api/notify call. Two harmless synthetic test entries
  remain in the live namespace - safe to ignore or delete manually.
- Files changed: wrangler.jsonc only (two commits).
- Test suite: 140/140 Python tests passing, unchanged.

## 2026-08-23 — Session 35: concurrency reality check + custom-domain-focused harvesting
- Part 1: read run.py/compliance/agent.py directly rather than
  theorizing. Real answer: no application-level concurrency cap exists
  anywhere - one asyncio.gather() call schedules every company at once,
  matching ADR-0021's own explicit design intent ("potentially
  thousands" of concurrent per-domain lanes). One real, currently-dormant
  limit exists a layer below the app code: httpx.AsyncClient()'s
  unconfigured default connection pool caps at 100 - not reached at
  today's 76 companies, but worth revisiting as the company count grows
  toward the ~200/~8,000-9,000 targets already discussed. No code
  change - a report, not a fix.
- Part 2: verified 6 new candidates (Majestic Labs, Port, Kela
  Technologies, Line 5, ForSight Robotics, AIR) as real, distinct
  companies before doing anything else - Kela Technologies required
  disambiguating from an unrelated, older cybercrime-threat-intel
  company sharing the same name.
- Fixed the comeet.co gap flagged in Session 32: added CM_WIDGET_UID_RE
  to discovery/playwright_probe.py, recognizing a company-uid= query
  parameter on any comeet.co request even with no public comeet.com
  link on the page at all - this directly resolved 3 of Session 32's 8
  genuinely-unresolved companies.
- Real result: Coralogix and Guesty turned out to be real Comeet
  customers all along, invisible to two prior sessions because both
  white-label Comeet through a WordPress plugin under their own
  domain/URL scheme; Upwind embeds Comeet's widget directly. All three
  confirmed against the real API (50/13/51 real jobs respectively,
  matching each page's own displayed counts exactly). Port and Kela
  Technologies (both new candidates) also confirmed real Comeet hits.
  companies.json: 71 -> 76.
- ForSight Robotics, AIR, and Quantum Art positively identified as
  custom career pages with real, structured job data that
  CustomAdapter's current JSON-only extraction strategy can't parse
  (a real architectural gap now hit by 3 companies, not theoretical) -
  added to companies_unscannable.json with that specific reason.
  Majestic Labs and Line 5 (new candidates) and Definity (Session 32,
  re-confirmed) have no structured job data published at all.
  companies_unscannable.json: 4 -> 10 entries.
- MorphiSec, HiBob, and Attenti remain genuinely unresolved even after
  a deeper pass specifically checking for the Comeet white-label
  pattern that resolved the other three - a real, disclosed negative
  result, not forced into either bucket.
- Live python run.py smoke test against the updated 76-company
  companies.json: 76/76 attempted and succeeded, 0 failures, 4
  immediate new real matches (2 Coralogix, 2 Upwind).
- Test suite: 143/143 passing (was 140: 3 new for CM_WIDGET_UID_RE).

## 2026-08-23 — Session 36: Comeet domain check + connection limit + CustomAdapter CSS strategy
- Confirmed via code (adapters/comeet.py's fixed CAREER_PAGE_URL_TEMPLATE)
  and live timing that all 26 Comeet companies - including the 5
  white-labeled/embedded ones Session 35 found - share one real pacing
  lane at scan time (www.comeet.com directly), regardless of what any
  company's own site proxies. ~39s of pure pacing floor at today's
  count, same order of magnitude as Greenhouse's own domain
  concentration.
- Set a deliberate httpx connection limit (200 max connections, 20 max
  keepalive - both configurable) replacing the library's unexamined
  100/20 default, reasoned from GitHub Actions' real runner specs and
  today's real 6-domain count. New tests inspect a real (non-fake)
  ComplianceAgent's actual httpx connection-pool internals to confirm
  the value is genuinely applied, not just documented.
- Built CustomAdapter's second real extraction strategy (css_selectors,
  adapters/custom.py) alongside the original json_blob one from Session
  6 - custom_selectors.json now requires an explicit "strategy" field.
  Confirmed against a plain httpx GET (not a browser snapshot) for all
  3 real companies flagged in Session 35 (ForSight Robotics, AIR,
  Quantum Art) before writing selectors - all genuinely server-rendered
  Webflow CMS collections. Handled two real per-company quirks
  honestly: a genuinely empty CMS field (Quantum Art's location) comes
  through as null, not empty string; a company with zero real per-job
  links at all (AIR's listings open a JS modal) falls back to the
  career page URL rather than a fabricated one.
- Moved ForSight Robotics, AIR, and Quantum Art from
  companies_unscannable.json back into companies.json (76 -> 79) - a
  real capability gained, not a new discovery. companies_unscannable.json:
  10 -> 7.
- Live python run.py smoke test: 79/79 attempted and succeeded, 0
  failures, including a real ForSight Robotics match flowing through
  the full production pipeline end to end.
- Test suite: 152/152 passing (was 143: 2 new for the connection-limit
  verification, 7 new for the css_selectors strategy).

## 2026-08-23 — Session 37: big verification pass - 3 combined candidate lists
- Three independently-sourced candidate files (Hebrew business media,
  Elad's own LinkedIn browsing, Wikipedia's Israeli company categories)
  combined to roughly 450 real names - an order of magnitude beyond any
  prior round. Deduped against the real current companies.json/
  companies_unscannable.json first (18 names across all three files
  already known). Prioritized Wikipedia's "strong likely-active
  subset" and LinkedIn's explicitly-flagged actively-hiring names per
  the task's own scope, deliberately deferring the larger media/
  historical-Wikipedia lists rather than rushing them.
- Resolved both flagged identity-collision risks with real evidence:
  Foresight Automotive vs. ForSight Robotics confirmed different
  companies; Nanox Vision vs. Nano-X confirmed the same company (Nano-X
  Imaging's own domain is literally nanox.vision).
- Delegated initial domain/status research to background agents, then
  did every real verification fetch personally through the live
  ComplianceAgent - the research was a lead to verify, not a
  substitute, and several findings needed real correction once
  actually fetched (a false-positive "embed" slug for Transmit
  Security, an invalid searched-up uid for XM Cyber).
- 12 new companies added (9 Comeet, 3 Greenhouse) - companies.json
  79 -> 91. 8 new companies_unscannable.json entries (7 -> 15), every
  one confirmed live (not from research alone) as genuinely acquired/
  absorbed with no distinct careers presence, or actively bot-blocked.
- Real, honest negative results: 15 names from the priority subset
  remain genuinely unresolved (some robots.txt-blocked at check time,
  some no recognized-platform signal found) - not forced into either
  bucket.
- Session explicitly NOT finished - resume-from-here state recorded:
  ~54 more LinkedIn names, the ~165-name media list, other Wikipedia
  categories, and the complete 153-name English Wikipedia category
  (referenced in the task's attachments but never actually included)
  all remain for a future session.
- Doc gap resolved per ADR-0030: added ADR-0032 (no automated LinkedIn
  scraping, ever) to DECISIONS.md, referenced by the task as already
  decided but missing from the repo.
- Live python run.py smoke test: 90/91 attempted succeeded (1 real
  transient failure, Smarsh ReadTimeout, unrelated to this session), 9
  immediate new real matches from the newly added companies.
- Test suite: 152/152 passing, unchanged (no code changes this session
  - pure data/config work).

## 2026-08-24 — Session 38: commit Session 37 + robots.txt recheck + continue verification
- Committed Session 37's pending work (4fb8ff6) before starting this
  session's own changes, confirmed with Elad first.
- Robots.txt recheck: Check Point/Papaya Global/Cyberint still
  genuinely blocked (confirmed via curl too, not an httpx-specific WAF
  artifact); Sapiens International self-healed but still no ATS
  signal found. Found and fixed a real Session 37 mistake: XM Cyber's
  slug/uid was wrongly marked invalid because the check matched an
  empty template-default declaration instead of the real one further
  down the same script - the record is genuinely real, added.
- Delegated research to two background agents (LinkedIn's remaining 53
  names, Wikipedia's remaining 126) - the Wikipedia agent hit an org
  spend limit and returned nothing usable, so that list got a smaller,
  hand-picked live-verification pass instead of a full one.
- 10 new companies added from the LinkedIn list (Fetcherr, Commit,
  Eitan Medical, KMS Lighthouse, Chargeflow, Airobotics, CodeValue,
  D-Fend Solutions, GitLab, Parallel Wireless) plus XM Cyber's
  correction - companies.json 91 -> 102.
- Real self-caught mistake, corrected before finalizing: an
  Israel-location check that only searched for the literal substring
  "israel" missed Parallel Wireless's real Kfar Saba-tagged roles
  (including a real DevOps match) - caught during the live smoke test,
  fixed before committing.
- LinkedIn list fully triaged (every remaining name has a real
  disposition: added, negative, excluded-as-agency, or
  flagged-collision-unresolved). Media list (~163 names) entirely
  untouched. Wikipedia 153-list: only 14 hand-picked names checked
  (all negative/blocked) of ~112 remaining - explicitly not finished.
  4 additional Wikipedia categories not attempted at all.
- Live python run.py smoke test: 102/102 on retry (an initial run hit
  a real but clearly transient DNS blip affecting ~46 unrelated
  pre-existing companies, confirmed transient by immediate clean
  retry), 9 immediate new real matches.
- Test suite: 152/152 passing, unchanged (no code changes this
  session).
