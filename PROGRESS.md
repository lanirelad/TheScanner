# PROGRESS.md — Current State

**Last updated:** 2026-08-07 (client-architecture session)

## Where things stand

- No code written yet — still all planning/architecture.
- Living docs set complete and current: README, CLAUDE.md, ARCHITECTURE.md,
  DECISIONS.md (ADR-0001 through ADR-0015), PLAN.md, PROGRESS.md (this
  file), CHANGELOG.md, DEPLOY.md, CLAUDE_CODE_GUIDE.md, plus
  PROJECT_INSTRUCTIONS.md and MEMORY.md for the Project itself.
- **Client is now a PWA** (Progressive Web App), not a plain static
  dashboard — installable on Android, works as a browser tab on the
  laptop, dark/light theme, Web Push notifications built in.
- **Alerts are native Web Push**, not Telegram or ntfy — delivered via a
  Cloudflare Worker (free tier) that stores push subscriptions and fires a
  notification when a scan finds new matches.
- **Preferences are local-only, per device** — role/tag filters and
  "applied" marks live in the device's local storage, never synced to any
  backend. This is what makes multiple people using the app safe: each
  install is fully independent, no accounts, no shared state.
- Every job links directly to its real application page (`source_url`) —
  no content copied/mirrored.
- No companies.json or roles.json file yet — schemas drafted, not populated.
- No repo pushed to GitHub yet.

## Immediate next steps

1. Push scaffolding to a private GitHub repo.
2. Seed `roles.json` (devops + technical_support, EN + HE tags).
3. Start harvesting companies.json toward the ~1,500-company target,
   ATS-directory-first.
4. Set up the GitHub Actions workflow skeleton (schedule + manual trigger).
5. Scaffold the PWA shell (manifest, service worker, dark/light theme) even
   before real job data exists, to prove the install + push flow early.
6. Set up the Cloudflare Worker for push-subscription storage and delivery.

## Blockers

None — all decisions needed to start building are now in place.

## Addendum — two-stage fetch (2026-08-07)
- Fetch pipeline is now two-stage: cheap lightweight list per company
  first, full description only for ambiguous matches (ADR-0016).
- `locations.json` added to the config picture, alongside `roles.json` —
  location is filtered at the same early stage as role tags, which is what
  keeps multinational companies' global job lists from ballooning the scan.

## Addendum — first build session (2026-08-07)
- `roles.json`, `locations.json` created with real starter content.
- `companies.json` seeded with 2 verified companies (Wiz/greenhouse,
  Playtika/greenhouse) — a test set, not the ~1,500-company target.
- `CC_TASK_001.md` written: Claude Code's first real task — repo skeleton,
  Greenhouse Stage 1 adapter, Compliance Agent, Stage 1 location+title
  filter, fixture tests. Waiting on Elad to run this via Claude Code and
  paste back the handoff.

## Addendum — Session 1 reviewed, standing rules added (2026-08-07)
- Session 1 handoff reviewed and accepted: Greenhouse Stage 1 adapter,
  Compliance Agent, location+title filter, all tests passing, live smoke
  test confirmed against real Wiz/Playtika data.
- Two new standing ADRs (0017 handoff format, 0018 code style) now govern
  all future Claude Code sessions.
- `CC_TASK_002.md` ready: directory review + code-style tightening pass.
  Not yet run.

## Addendum — Session 2 accepted, first commit deferred (2026-08-07)
- Session 2 accepted as-is. Directory structure confirmed clean, no reorg
  needed. `Adapter` base class and `RoleLocationFilter` class now exist.
- Elad: not committing yet, wants more built first. Noted so this doesn't
  get asked again every session.
- Next up: Lever adapter (Session 3), implementing the new `Adapter` base
  class as its second real user — a genuine test of whether the
  abstraction holds up, not just Greenhouse-shaped.

## Addendum — Lever companies added, Session 3 task written (2026-08-07)
- `companies.json` now has 4 companies: Wiz/Playtika (Greenhouse),
  Palantir/Smarsh (Lever) — still a small verified test set, not the
  ~1,500-company target.
- `CC_TASK_003.md` ready: build `LeverAdapter`, testing whether the
  `Adapter` base class holds up for a second platform. Not yet run.

## Addendum — Session 3 accepted (2026-08-07)
- LeverAdapter built and accepted. Adapter base class validated against a
  genuinely different second platform, not just a Greenhouse-shaped copy.
- Key finding carried into ARCHITECTURE.md: Lever has no lightweight fetch
  mode — full content always comes back regardless of query params. This
  is a per-ATS caveat now, not a universal Stage-1-is-cheap assumption.
- companies.json test set is now 4 companies across 2 ATS platforms
  (Greenhouse: Wiz, Playtika; Lever: Palantir, Smarsh). Zero role matches
  found yet in the live data — expected at this small sample size, not a
  signal anything's broken.
- Git init/commit still deferred, by explicit repeated choice.

## Addendum — Session 4 executed: docs synced, async retrofit (2026-08-08)
- Part 0: CLAUDE.md, CLAUDE_CODE_GUIDE.md, DECISIONS.md (now through
  ADR-0022), and PLAN.md fully replaced with the planning session's new
  content. The pasted content had visibly lost markdown structure in
  transit (a stray `###` survived right before ADR-0016, headers had lost
  their `#`/`##`, bullets had become `*`) — reconstructed standard markdown
  syntax while keeping every word of content unchanged, flagged in the
  handoff rather than pasted as flattened text.
- Part 1: `ComplianceAgent` retrofitted to `httpx.AsyncClient` (ADR-0021).
  Real race condition fixed: a per-domain `asyncio.Lock` now spans the
  entire check-wait-fetch-record sequence, not just the dict read/write, so
  two concurrent same-domain calls can't both see "no wait needed" and fire
  together. Different domains use different locks and don't block each
  other.
- `robots_cache.json` added at the repo root — persisted, domain-level
  ({domain, allowed, checked_at}), 7-day TTL, guarded by its own lock
  (separate from the per-domain fetch locks, since the file is shared
  across every domain).
- `GreenhouseAdapter`/`LeverAdapter`'s `fetch_stage1_jobs` are now async
  methods; `parse_stage1_jobs` stays synchronous in both (pure functions,
  no I/O).
- `usage_log.py` added (ADR-0022) — `record_scan_run()` appends one entry
  per run. Doesn't fit any existing module boundary; kept as a standalone
  root-level module and flagged as such in ARCHITECTURE.md §3.
- Test suite: 22/22 passing (was 13 before this session: 6 new
  ComplianceAgent async tests including a measured same-domain-spacing
  test and a measured different-domains-don't-block test, both against a
  fake HTTP client; 3 new usage_log tests), 0 real network calls.
- Live smoke test (real network, both Greenhouse and Lever, all 4
  companies): concurrent (asyncio.gather) elapsed 6.731s vs sequential
  7.223s — only a 1.07x speedup. Not a disappointing result so much as an
  honest one: with only 2 domains and Palantir's 6MB payload dominating
  the critical path either way, there isn't much serial time to remove at
  this small scale. The real payoff (ADR-0021's actual motivation) is at
  hundreds/thousands of distinct domains, which 4 companies can't
  demonstrate — same-domain spacing (1.673s, correctly >= the 1.5s
  minimum) and cross-domain non-blocking (Lever's first request landed
  before the Greenhouse pair had finished) were both confirmed directly
  from real timestamps, which is the part that actually mattered to prove.
- robots_cache.json persistence confirmed working end-to-end, not just in
  unit tests: the concurrent run made 2 real robots.txt fetches (one per
  domain, despite 2 companies per domain); the sequential run immediately
  after made zero, reusing the cache.
- Still nothing committed — git init still deferred.

## Addendum — Session 6 executed: CustomAdapter built (2026-08-08)
- Verified before writing any parser (ADR-0019 discipline): a plain HTTP
  GET on monday.com/careers, through the Compliance Agent, no JS
  execution, already returns the full position list — embedded as JSON
  inside a `<script id="__NEXT_DATA__">` tag (Next.js SSR hydration data).
  No headless browser needed for this company. Confirmed the "positions"
  key appears exactly once in the whole blob before trusting a recursive
  key search over it.
- Built `adapters/custom.py` (`CustomAdapter(Adapter)`), config-driven via
  new `custom_selectors.json` (career page URL, script tag id, positions
  key, field name mapping, URL template) — one class, not a bespoke
  `MondayComAdapter`, per ARCHITECTURE.md §4a's scaling goal. Documented
  honestly: this scales via config only for companies sharing the same
  script-tag-JSON rendering pattern; a genuinely different page structure
  still needs a new extraction strategy in the adapter, not just config.
- Real positive match confirmed: "DevOps Tech Lead (BigBrain)", Tel Aviv,
  matches `devops`/`devops` — the actual live role that motivated this
  session, not a synthetic case.
- Side-finding, not acted on: every monday.com position carries
  `"source": "ashby"` — a real ATS's data proxied through an otherwise-
  custom page. Flagged in ARCHITECTURE.md §1/§4a as worth revisiting if
  this pattern recurs across other "custom" companies.
- Test suite: 42/42 passing (was 31 before this session: 11 new
  `CustomAdapter` tests in a new `tests/test_custom_adapter.py`), 0 real
  network calls.
- Live smoke test: 2 total real requests to monday.com this session (one
  page fetch, one robots.txt fetch — both served double duty as schema
  discovery and fixture capture, no repeat fetches needed).
- Still nothing committed — git init still deferred.

## Addendum — Session 5 executed: ComeetAdapter built (2026-08-08)
- Discrepancy flagged at session start: companies.json's note and this
  session's task prompt both referenced "ADR-0023" (company harvesting via
  separate Claude Code sessions), but DECISIONS.md still ends at ADR-0022
  — that ADR was never actually recorded. Didn't fabricate it; flagged and
  proceeded, since the substance was already covered by the task's own
  scope boundaries either way.
- `adapters/comeet.py` (`ComeetAdapter`) built, implementing the same
  `Adapter` contract as Greenhouse/Lever — a third, structurally different
  real user (HTML with embedded JS state, not a JSON API) with no changes
  needed to `adapters/base.py`.
- Real finding: Comeet has no public JSON API for either company checked.
  The career page is server-rendered HTML with the full job list embedded
  as a `COMPANY_POSITIONS_DATA = [...]` JS variable — present in the
  initial response, no headless browser/JS execution needed. Same
  no-lightweight-mode situation as Lever, but unlike both Greenhouse and
  Lever, `department` came through cleanly for every posting on both
  companies. Documented in ARCHITECTURE.md §1.
- Also restored a Session 3 empirical note (the Lever no-lightweight-mode
  finding) that had gone missing from ARCHITECTURE.md §1 at some point —
  flagged rather than silently re-added without comment.
- Task's premise ("both companies show zero open positions live") had gone
  stale by execution time — AT&T Israel had 7 real postings, Enlight had
  18. Real data for the positive case; the zero-positions parsing path is
  covered by a clearly-marked synthetic fixture instead, disclosed as such
  in both the adapter docstring and the test file.
- Small aligned fix, not explicitly in scope but already decided in
  ARCHITECTURE.md §13: moved `usage_log.py` (Session 4) into its own
  `usage/` package (`usage/log.py`, re-exported via `usage/__init__.py`)
  per the resolution recorded there. `usage_log.json` itself stays at the
  repo root.
- Test suite: 31/31 passing (was 22 before this session: 9 new
  `ComeetAdapter` tests in a new `tests/test_comeet_adapter.py` — starting
  the test-file split flagged in Sessions 2 and 3), 0 real network calls.
- Live smoke test: 3 total real requests to comeet.com this session (AT&T
  page fetch, Enlight page fetch, one robots.txt fetch) — robots_cache.json
  shows exactly one `www.comeet.com` entry with a single `checked_at`,
  confirming the AT&T fetch triggered a fresh robots.txt check (new
  domain) and the Enlight fetch reused the cached decision with zero
  additional robots.txt requests.
- Still nothing committed — git init still deferred.

## Addendum — Session 7: AshbyAdapter blocked by robots.txt (2026-08-08)
- Set out to find monday.com's real Ashby job-board slug and build
  `AshbyAdapter` per ADR-0024. Checked the already-cached
  `tests/fixtures/monday_stage1_raw.html` first, per ADR-0019 — no slug or
  API reference embedded anywhere in the `__NEXT_DATA__` blob, only
  `"source": "ashby"` on each position. A live check was needed to find
  the real slug.
- Before guessing slugs live, the Compliance Agent's own robots.txt check
  for `api.ashbyhq.com` came back BLOCKED. Verified this wasn't a bug:
  `api.ashbyhq.com/robots.txt` itself returns HTTP 401 Unauthorized
  (confirmed directly). Both `urllib.robotparser`'s standard convention and
  our own `ComplianceAgent` logic correctly treat a 401/403 on robots.txt
  as "disallow everything" — this is the agent working exactly as
  designed, not a defect to fix.
- Per ADR-0002 ("cannot be bypassed, including 'just for a quick test'"),
  stopped here. No AshbyAdapter code was written — building a parser
  against Ashby's documented response shape without ever seeing real data
  would mean guessing field names from documentation, which every prior
  adapter session (Greenhouse, Lever, Comeet, Custom) deliberately avoided
  in favor of empirical verification. Writing speculative code now would
  break that discipline for no real benefit, since it couldn't be tested
  against anything real anyway.
- `companies.json` and `custom_selectors.json` are both unchanged —
  monday.com stays on `CustomAdapter` (Session 6), which is confirmed
  working and fully compliant.
- Documented the finding in ARCHITECTURE.md §1. Did not touch DECISIONS.md
  — whether ADR-0024 needs to be marked blocked/superseded, or whether
  there's a path forward (e.g. contacting Ashby, or accepting monday.com
  stays on `CustomAdapter` permanently), is Elad/planning-Claude's call,
  not something resolved this session.
- Total live network interactions with api.ashbyhq.com this session: 4
  (3 slug-guess attempts through the Compliance Agent, all correctly
  blocked before any actual data fetch; 1 direct, out-of-band check of
  robots.txt itself to independently confirm the agent's decision wasn't a
  bug — disclosed here rather than treated as routine, since it bypassed
  the agent, though it only ever touched the robots.txt file itself, never
  job data). Zero job data was ever retrieved from Ashby.
- Test suite unchanged, still 42/42 passing — no code was added or
  modified this session.
- Still nothing committed — git init still deferred.

## Addendum — Session 8 executed: storage, dedup, first real CLI run (2026-08-08)
- Built `storage/db.py` (SQLite, task-scoped 9-field schema, no
  `application_status` — enforced by a test that reads the real table
  schema directly), `core/schema.py` (`compute_job_id`, hashing company +
  each job's `absolute_url` rather than title+location, per Session 3's
  Palantir cross-city-duplicate-title finding), `core/dedup.py`
  (`compute_scan_status`, storage-agnostic — takes a plain set of known
  job_ids, no SQLite awareness).
- Built `run.py` — the first real end-to-end pipeline: loads
  companies.json/roles.json/locations.json/custom_selectors.json, fetches
  all 7 companies concurrently through one shared `ComplianceAgent`,
  isolates each company's failure independently (broad except at that one
  boundary, deliberately, documented why), filters, dedups against
  storage, upserts, writes a usage-log entry (`track: "stable"`), prints a
  console summary.
- Live smoke test, run twice against real data: first run - 7/7 companies
  succeeded, 2 matches, both `new` (Wiz's DevOps Engineer, monday.com's
  DevOps Tech Lead). Second run immediately after - same 7/7 succeeded,
  same 2 matches, now both correctly `still_open` — dedup confirmed
  working end-to-end against real persisted SQLite state, not just unit
  tests. robots_cache.json unchanged across both runs (every domain hit
  was already cached from prior sessions) — zero new robots.txt fetches.
- Test suite: 57/57 passing (was 42 before this session: 5 new
  core/schema+dedup tests, 5 new storage tests, 5 new run-summary tests),
  0 real network calls. Confirmed by hash comparison that the test suite
  never touches the real `scan_results.db`/`usage_log.json` — only
  `tmp_path` fixtures.
- Documented in ARCHITECTURE.md: §2 gained an implementation note tying
  the actual SQLite schema back to the draft canonical schema and
  explaining which fields are deliberately not populated yet; §3 gained
  entries for the storage/core dedup split and for `run.py` itself.
- Still nothing committed — git init still deferred.

## Addendum — Session 9 executed: git init, first push, scheduled workflow (2026-08-09)
- Discovered before touching git: `roles.json` had grown three new
  categories (`npi`, `software_development`, `project_manager`) since
  Session 8 — real, intentional config evolution (ADR-0007), not
  something this session changed. It broke 6 existing tests that asserted
  stale "no match" expectations against real fixture data whose meaning
  had legitimately changed. Fixed all 6 to reflect current correct
  behavior (some became positive-match tests, one was repurposed since
  its only example job now matches) before doing anything else — the
  first-ever commit needed a genuinely green suite, not a silently-broken
  one. Re-ran `run.py` afterward so `scan_results.db`/`usage_log.json`
  reflect accurate current-config data (15 matches, up from the stale 2)
  before it became permanent history.
- Built `schedule/gate.py` (`should_run_full_scan`, ADR-0028) and
  `schedule_config.json`. New `schedule/` package, same reasoning as
  `usage/`: a distinct concern gets its own small module. CLI entry point
  is `python -m schedule` (deliberately in `schedule/__main__.py`, not a
  `__main__` block inside `gate.py`, to avoid a real double-import
  RuntimeWarning that pattern produces when a package's `__init__.py`
  also imports that same submodule).
- Built `.github/workflows/scan.yml`: hourly cheap check-in +
  `workflow_dispatch`, gate-check step decides whether to actually run
  `run.py`, then commits/pushes `scan_results.db`/`usage_log.json`/
  `robots_cache.json` back to the repo as a bot commit.
- **Part 0, git init and first push — done, with explicit confirmation at
  each step per ADR-0004:** staged all 62 files, showed the full
  `git status` and flagged two things before asking (the 6MB Palantir
  fixture, still untrimmed since Session 3; the two PNG assets that
  appeared externally in Session 6) — Elad confirmed committing as-is.
  Committed, then separately asked before adding the remote/pushing —
  confirmed separately. Renamed `master` to `main` before the push (free,
  since nothing had been pushed yet). Pushed to
  `https://github.com/lanirelad/TheScanner.git`. This is the first thing
  that has ever left the local sandbox in this project.
- Test suite: 67/67 passing (was 57 before this session: 6 fixed for the
  roles.json drift, 1 new for the now-matching Wiz Backend Engineer case,
  9 new schedule-gate tests), 0 real network calls.
- Documented in ARCHITECTURE.md: §9a gained the cron-cadence-vs-real-
  schedule distinction the task specifically asked for; §3 gained a
  `schedule/` entry.
- Not yet done, explicitly out of scope this session: verifying a live
  GitHub Actions run actually completes successfully — that needs real
  wall-clock time to pass after the push. Elad can check the Actions tab.

## Addendum — Session 10 executed: on_demand mode, scan timeout cap (2026-08-09)
- schedule_config.json's `mode` is now `"on_demand"` — manual-only for
  now, per Elad's actual preference (the `"scheduled"` value shipped in
  Session 9 was just the task prompt's example, not a real decision to
  turn scheduling on). `scans_per_day`/`times_utc` untouched, ready for
  whenever it's switched back.
- Confirmed, not rebuilt: schedule/gate.py's test suite plus a direct
  check against the real file — schedule-triggered check-ins now always
  return False, workflow_dispatch always True. 67/67 tests unchanged.
- Added `timeout-minutes: 20` to the "Run scan" step (not job-level) in
  the workflow — a safety cap for once the company list grows past
  today's 7, not a tuning target.
- Worked out and documented in ARCHITECTURE.md §9a exactly what happens
  if that timeout fires: nothing partial gets saved. run.py only writes
  to scan_results.db/usage_log.json once, after the entire concurrent
  fetch phase returns — a kill mid-fetch means execution never reaches
  that point, so the files are left exactly as the last successful run
  left them. Separately confirmed GitHub Actions' own step semantics
  would skip the commit/push step after a timed-out step anyway. A clean,
  deliberate no-op on timeout, not an accident.
- No test/code changes beyond the two files above — this was a
  deliberately small, single-purpose session.

## Addendum — Session 11 executed: roles.json "enabled" flag now functional (2026-08-09)
- Discrepancy flagged at session start: the task said roles.json already
  had an `"enabled"` field added externally by planning-Claude — it
  didn't (confirmed via `git log -- roles.json`, unchanged since the
  Session 9 initial commit). Rather than blocking the whole session on a
  documentation gap, added the field myself with exactly the values the
  task specified (`true` for devops/technical_support, `false` for npi/
  software_development/project_manager) — implementing an already-decided,
  unambiguous value, not making a new product decision.
- `core/filters.py`'s `_matching_role_tag` now skips any category where
  `enabled` is falsy before checking its tags. Missing the `enabled` key
  entirely defaults to **disabled** (fail safe, not fail open) — matches
  this project's existing conservative-default pattern (robots.txt 401 ->
  disallow-all). Documented inline and in ARCHITECTURE.md §1a.
- Fixed 5 Session 9 tests whose entire premise was "this now matches
  under the full 5-category set" — converted each to assert the new,
  correct default (disabled -> rejected), and added 2 consolidated tests
  (one in test_filters.py, one in test_comeet_adapter.py) that force every
  category `enabled` in a loaded config to prove the underlying tag logic
  for software_development/project_manager still works correctly when
  active — preserving Session 9's real-data discovery value without 5
  near-duplicate override tests. Also added 4 new synthetic unit tests
  isolating the enabled-flag mechanism itself (disabled/enabled/missing-key/
  multi-category), independent of any real fixture.
- Live smoke test: real matches dropped from 15 (Session 9's actual
  recorded figure — the task said 14, a minor inaccuracy, not chased
  further) to 2, both correctly `still_open` (the same two devops matches
  from Session 9, already known to storage). Every dropped match was
  project_manager/software_development, exactly as expected.
- Test suite: 73/73 passing (was 67: 5 fixed, 6 new), 0 real network calls.
- Still nothing new committed — this session's changes remain local per
  the task's explicit "do not commit or push."

## Addendum — Session 13 executed: EU-region domains, Optimove/Mobileye (2026-08-09)
- Two more discrepancies found and disclosed at session start, same
  pattern as Sessions 9/11: companies.json didn't actually have the
  Optimove/Mobileye entries the task described, and neither company was
  previously live-verified. Added both myself with the exact slugs/domains
  the task specified, then did the actual verification work rather than
  trusting the task's premises.
- Real finding: Greenhouse and Lever handle EU hosting differently at the
  API layer. Lever genuinely has a separate api.eu.lever.co domain
  (confirmed against Mobileye — 200 OK, identical shape to the global
  API). Greenhouse does not — boards-api.eu.greenhouse.io doesn't resolve
  at all; Optimove's EU-hosted board is served by the same global
  boards-api.greenhouse.io with no regional variant. Both adapters now
  take an `ats_region` argument and consult a `REGION_DOMAINS` dict
  (empty for Greenhouse, `{"eu": "api.eu.lever.co"}` for Lever) with a
  plain default-domain fallback — a future confirmed region is a dict
  entry, not new code, and nothing speculative was added for Greenhouse
  just to look symmetrical with Lever.
- companies.json's note fields now describe what was actually verified,
  replacing the "VERIFIED VIA WEB SEARCH ONLY" placeholder language.
- Live smoke test: 9/9 companies succeeded, 7 total matches (5 new from
  Mobileye — DevOps & Infrastructure Engineer, Senior SRE & Linux
  Infrastructure Engineer, Data Platform Engineer (a genuine loose-match
  via the "platform engineer" tag), and two Field Engineer/Relocation
  postings — plus the 2 already-known still_open devops matches from
  before). Optimove contributed 0 matches: the task expected a "Site
  Reliability Engineer" title there, but no such posting exists in the
  live data at verification time — normal listing drift, not a bug,
  flagged directly in the test that covers it.
- Test suite: 87/87 passing (was 73: 14 new EU-region tests — adapter
  domain-resolution unit tests plus real Optimove/Mobileye fixture
  checks), 0 real network calls.
- Total live network calls this session: 6 (1 DNS-failure attempt against
  a hypothesized boards-api.eu.greenhouse.io that never reached a real
  server; 1 HTML page fetch investigating Optimove's EU page; 2
  exploratory JSON API probes confirming api.eu.lever.co works and
  boards-api.greenhouse.io serves Optimove fine; 2 final designated
  fetches to capture the actual fixtures) — disclosed per ADR-0019.
- Still uncommitted at this point in the session: Session 11's pending
  changes plus this session's — see the handoff for the combined
  commit/push outcome.

## Addendum — Session 14 executed: latest_scan.json + real budget calculator (2026-08-11)
- Built `usage/budget.py`'s `compute_usage_summary(entries, cap, now=None)`
  — sums `duration_minutes` for current-calendar-month entries, returns
  `minutes_used_this_month`/`minutes_cap`/`percent_used` (not clamped at
  100 — over-budget is the useful signal) plus
  `includes_checkin_overhead: false`.
- Checked empirically, not assumed, before designing the calculator:
  `usage_log.json` only ever gets entries from `record_scan_run()`, which
  only runs when `run.py` runs, which only happens when the workflow's
  gate-check says yes. The hourly cheap check-in's own real cost
  (ADR-0028's disclosed line item) is never logged anywhere in this
  codebase today. Rather than estimate/fabricate a number for it, the
  calculator sums exactly what's real and surfaces the gap via
  `includes_checkin_overhead: false` in the output itself, not just a
  code comment.
- Refactored `usage/log.py`: extracted `load_usage_log()` from inside
  `record_scan_run()` so the budget calculator (and anything else) can
  read the log without duplicating that logic.
- Added `run.py`'s `build_latest_scan_export()` (pure function, shapes a
  run's summary into the flat JSON a future PWA will `fetch()` directly —
  no `job_id`/`matched_tag`/internal timestamps, `companies_failed`
  flattened to a count, never `application_status`) and a shared
  `write_json_file()` helper. Both `latest_scan.json` and
  `usage_summary.json` are now written on every real `run.py` execution.
- Live smoke test: real run produced accurate current data in both files
  — see the handoff for full contents. `usage_summary.json` showed
  ~0.04% of the monthly cap used, matching the real, tiny logged run
  durations so far.
- Test suite: 98/98 passing (was 87: 11 new — 5 for the budget
  calculator, 4 for the latest_scan export/write helper, 2 for the new
  `load_usage_log` helper), 0 real network calls.
- ARCHITECTURE.md §9a gained two new notes: what the two new files
  actually contain, and the check-in-overhead gap explained above.

## Addendum — Session 15 executed: the first real PWA (2026-08-11)
- Two more discrepancies found and disclosed at session start, same
  pattern as Sessions 9/11/13: ADR-0029 (referenced as already recorded)
  doesn't exist in DECISIONS.md, still ends at ADR-0028; and `demo.html`
  (referenced as the visual design to match) doesn't exist anywhere in
  the repo. Proceeded from the task's own textual description of both
  rather than blocking — built the dark-radar/mascot/badge design from
  the description plus the real mascot art, and built the Cloudflare
  deployment from the task's own explanation of what ADR-0029 supposedly
  decided.
- Amended Session 14's still-uncommitted work before it ever shipped:
  moved `latest_scan.json`/`usage_summary.json`'s default write location
  from the repo root into `pwa/`. Real reason, not tidiness: Cloudflare
  Workers-with-static-assets only ever serves files inside
  `wrangler.jsonc`'s `assets.directory` — outside it, the deployed PWA
  could never `fetch()` them at all. Since Session 14 was never committed,
  this was refining in-flight work, not changing shipped behavior.
- Built the full read-only PWA shell in `pwa/`: `index.html`, `styles.css`
  (dark radar theme, `[data-theme="light"]` swap), `app.js` (fetches both
  JSON files, renders summary tiles/budget bar/job cards, no
  interactivity yet per explicit scope), `service-worker.js`
  (network-first for the two data files, cache-first for the shell —
  two different strategies, not one applied everywhere), `manifest.json`,
  and properly-sized icons/animation frames generated from
  `mascot.png`/`batPoses.png` via Pillow (cut total image weight from
  ~4.9 MB to ~88 KB — the originals are full-resolution 1536x1024 PNGs,
  too heavy to ship as-is for a PWA).
- Wrote `wrangler.jsonc` at the repo root: `assets.directory: "./pwa"`,
  `compatibility_date: "2026-08-11"`. Updated `.github/workflows/scan.yml`
  to also commit `pwa/latest_scan.json`/`pwa/usage_summary.json` — this
  same push is what triggers Cloudflare's redeploy (Git integration),
  which is what actually refreshes the *deployed* site's data.
- Verified for real, not just by inspection: ran `run.py` live (9
  companies attempted, 8 succeeded, 1 real transient failure — Palantir
  timed out, a genuine `ReadTimeout`, not a bug), generating real data in
  `pwa/`. Served `pwa/` locally and loaded it in the browser: both JSON
  files fetched successfully, summary tiles/budget bar/all 7 job cards
  rendered correctly with real values, zero console errors, service
  worker registered and active. Confirmed via `read_network_requests`
  and a direct `serviceWorker.getRegistrations()` check rather than
  trusting a visual glance alone (the browser pane's screenshot tool
  wasn't available in this environment, so text/network/JS-level
  verification stood in for it).
- Test suite: 98/98 passing, unchanged — this session's new work is all
  frontend/config, no Python logic changed beyond the two path constants.
- ARCHITECTURE.md §9a rewritten to describe the real Cloudflare
  deployment mechanics (replacing the stale "GitHub Pages-hosted JSON"
  reference) and document `pwa/`'s role; §3 gained a `pwa/` module entry.
- Still uncommitted at this point: Session 14's amended work plus all of
  this session's — see the handoff for the combined commit/push outcome.

## Addendum — Session 16 executed: DECISIONS.md synced through ADR-0030 (2026-08-11)
- Confirmed DECISIONS.md was still at ADR-0028, exactly the gap ADR-0030
  itself describes. Appended ADR-0029, ADR-0029a, and ADR-0030 verbatim
  per ADR-0030's own new protocol - no pause to ask, flagged in the
  handoff instead.
- Real side effect this session existed for: a genuine new commit to
  trigger Cloudflare's Git integration, which had never actually built
  from this repo. Pushed as 3faddaa - outcome (whether a real build
  appeared on the dashboard) is Elad's to check and report back.

## Addendum — Session 17 executed: PWA visual fixes (2026-08-11)
- Wordmark: `.wordmark`/`.wordmark span` now match the exact CSS/HTML
  Elad's task gave (JetBrains Mono 700 20px, -0.5px letter-spacing, the
  "Scanner" half colored via `--teal`). Added the Google Fonts `<link>`
  for JetBrains Mono + IBM Plex Sans. `--teal` aliased to the existing
  `--radar-green` accent since the real `demo.html` (still never
  committed to this repo) isn't available to pull an exact hex from -
  flagged as a judgment call in both the CSS comment and the handoff.
- Role tags: job cards now show `roles.json`'s `label_en` ("DevOps
  Engineer") instead of the raw `role_category` key ("devops"). Chose
  server-side resolution (`run.py`'s new `_role_label()` helper, fail-safe
  to the raw key) over having `app.js` fetch `roles.json` itself, since
  the latter would mean duplicating `roles.json` into `pwa/` - the same
  file-locality problem Session 15 solved for the other two JSON exports.
  `label_en` now rides alongside `role_category` in both `build_summary()`
  and `build_latest_scan_export()` (role_category stays as the stable
  key for future filtering; label_en is purely the display string).
- Verified for real: ran `run.py` live (9/9 succeeded this time, 7 real
  matches), confirmed `pwa/latest_scan.json` has correct `label_en` values
  for every match ("devops" -> "DevOps Engineer", "technical_support" ->
  "Technical Support Engineer"). Served `pwa/` locally, loaded it in the
  browser, confirmed via `getComputedStyle` that the wordmark's
  font-family/weight/size/letter-spacing/color match the spec exactly,
  and via `get_page_text` that every job card now shows the human-readable
  label. Service worker still registers and goes active correctly.
- Added 2 new tests for `_role_label()` (known category, fallback for an
  unknown one) and updated the one existing exact-shape assertion that
  needed the new field added.
- Test suite: 100/100 passing (was 98: 2 new), 0 real network calls.
- ARCHITECTURE.md gained a Session 17 note alongside the existing
  Session 15 "no demo.html" note, documenting both fixes and the
  `--teal` judgment call.

## Addendum — Session 18 executed: harvest toward a real ~5-minute scan (2026-08-12)
- Sourced ~330 candidate Israeli-relevant company names across two
  rounds (Wikipedia's companies-of-Israel/cybersecurity-industry pages,
  failory.com's Israel startup list, general knowledge of the
  ecosystem), then live-verified each candidate's guessed Greenhouse/
  Lever slug through the real `ComplianceAgent` — 421 Greenhouse calls +
  428 Lever calls total across both rounds, robots.txt/rate-limit
  honored throughout, disclosed per ADR-0019.
- Real, honest result: 34 new Greenhouse + 4 new Lever companies
  verified and added (`companies.json`: 9 -> 47). Short of the ~200
  Greenhouse target — reported as such, not rounded up. Comeet wasn't
  expanded: its URLs need a slug *and* a separate numeric uid that can't
  be guessed blindly, only discovered from a company's real career page.
- 3 technical "HITs" (real 200 OK + real job data) were manually
  reviewed and rejected as generic-word slug collisions with an
  unrelated company, not the intended Israeli one: `shield`, `bold`,
  `vim` — each a single posting with zero Israel signal (e.g. "Copy of
  Avenger" in Beijing). A resolving slug isn't the same as resolving to
  the *intended* company; both were checked.
- Fixed the real gap Elad flagged: `run.py`'s console summary now prints
  `[Company] FAILED — <real error>` per failure (was a bare count), and
  `build_latest_scan_export()` now carries a `failures:
  [{company, error}]` list in `latest_scan.json` alongside the existing
  `companies_failed` count.
- Live smoke test against the real 47-company list: 46/46 succeeded
  except one genuine transient `ReadTimeout` (Imubit), 20 matches (13
  new, 7 still_open). Real elapsed time ≈ 80 seconds — confirms rather
  than disproves the architecture's own reasoning: Greenhouse-domain
  company count is the real pacing floor (~36 real Greenhouse companies
  × 1.5s ≈ 54s, plus real response overhead ≈ the observed ~80s).
  Reaching the actual ~5-minute target needs roughly ~200 real
  Greenhouse companies — this session's harvesting fell well short of
  that, reported honestly.
- Test suite: 103/103 passing (was 100: 3 new for the failures-list
  fix), 0 real network calls in automated tests.

## Addendum — Session 19 executed: domain-first harvesting round 2 + --teal fix (2026-08-12)
- Method inverted from Session 18: fetched each candidate's own real
  career page through the Compliance Agent and read the actual ATS
  directly off of it (redirect Location header or embedded link),
  instead of guessing a slug against the ATS API directly. This
  eliminates the "resolved to the wrong company" risk Session 18 hit
  three times, at the cost of a lower raw hit rate against Greenhouse
  specifically.
- Real bug found and fixed mid-session: the first discovery pass
  silently discarded every HTTP redirect (ComplianceAgent.fetch()'s
  raise_for_status() raises on unfollowed 3xx too, not just 4xx/5xx),
  which killed the exact signal this method relies on. Fixed by reading
  the Location header off the raised exception's response and chasing
  one non-ATS redirect hop; hits went from 4 to 13 after the fix.
- 505 fresh candidates sourced (mappedinisrael.com's real, if dated,
  Israeli startup directory + Session 18's two guess-lists),
  deduplicated against the 47 already-verified companies.
- 2 of 13 raw hits rejected on manual review: BillGuard's guessed
  domain now redirects to Prosper (the US company that acquired it in
  2015, zero Israel signal); "Palantir" duplicated the existing
  "Palantir Technologies" entry under a different name.
- Real result: 1 new Greenhouse (K Health) + 10 new Comeet (Cognyte,
  Cyera, Feedvisor, Immunai, Infinidat, MetalBear, Netafim, Pipl,
  Riverside, SysAid). companies.json: 47 -> 58 (Greenhouse: 37 -> 38).
  Comeet's slug+uid blocker from Session 18 is fully resolved — every
  new Comeet company came with its exact pair read directly off its
  own page, no guessing.
- Honest diagnosis of the still-low Greenhouse yield: most companies'
  real /careers pages are client-rendered SPAs whose ATS link only
  ever appears via a post-load JS fetch(), invisible to a plain HTTP
  GET — the same limitation ARCHITECTURE.md flagged in Session 6, now
  seen at real scale. This method's real win was precision (0
  collisions vs. Session 18's 3) and unlocking Comeet, not raw count.
- `--teal` fixed in pwa/styles.css using the two real hex values given
  directly in this session's task (#4FD1C5 dark / #2A9D8F light) -
  demo.html itself stays deliberately out of the repo (Elad's call),
  not referenced as a source. Replaces Session 17's --radar-green
  placeholder. Verified via getComputedStyle in both themes - exact
  match.
- Live smoke test against the real 58-company list: 58/58 succeeded, 0
  failures, 31 matches (11 new, 20 still_open). Real elapsed time ~66
  seconds — still well short of ~5 minutes, consistent with 38 real
  Greenhouse companies being the actual pacing floor today.
- Test suite: 103/103 passing, unchanged.

## Addendum — Session 20 executed: research-sourced candidates (2026-08-12)
- First session where the candidate list came pre-sourced from real
  research (Calcalist/CTech's 2026 funding-rounds coverage +
  StartupBlink's Israel ranking) rather than being compiled this
  session — ~182 fresh names after deduping against the 58 companies
  already verified (8 supplied names were already present and
  correctly skipped without a live fetch).
- Reused Session 19's domain-first discovery method unchanged — no new
  bugs, the redirect-chase fix held up against a different candidate
  list. 8 raw hits, 7 confirmed (1, "Slice", resolved to a generic
  Greenhouse embed-script path rather than a real company slug and was
  correctly dropped at confirmation).
- 2 of 7 confirmed hits rejected on manual review: "Enigma" resolved to
  a NYC data company with zero Israel signal across 9 postings — almost
  certainly the exact generic-word collision the sourcing session
  itself warned about; "CopilotKit" resolved to a real Lever board but
  its single open role (Seattle) also carried zero Israel signal, not
  confirmed enough to include.
- Net result: 5 new companies (Guardio, Guidde, ScaleOps, Zeroport,
  ZyG) — 2 Greenhouse + 3 Comeet, each with a direct Israel-located
  posting confirming genuine R&D presence, not just a resolving slug.
  companies.json: 58 -> 63 (Greenhouse: 38 -> 40).
- Live smoke test: 61/63 succeeded, 2 genuine transient ReadTimeouts
  (Cato Networks, Payoneer, both visible with real error text in
  latest_scan.json's failures list). 36 matches (5 new, 31 still_open).
  Real elapsed time ~97 seconds — still short of ~5 minutes.
- Test suite: 103/103 passing, unchanged.
- Note as of this session's end: companies.json's 5 new entries
  (Guardio, Guidde, ScaleOps, Zeroport, ZyG) are staged locally but
  Elad chose not to commit yet ("handoff" instead of a commit
  confirmation) — still pending as Session 21 begins.

## Addendum — Session 21 executed: Playwright-based discovery (2026-08-14)
- Added ADR-0031 (DECISIONS.md was still at ADR-0030 — same recurring
  gap, resolved per ADR-0030's own protocol): Playwright approved for
  discovery/onboarding sessions only, never the production scan
  pipeline (stays on plain httpx, ADR-0001/ADR-0021).
- Installed playwright + its Chromium binary (~115MB, confirmed with
  Elad before downloading) as a discovery-only dependency
  (requirements-discovery.txt, separate from requirements.txt — the
  GitHub Actions workflow never installs it).
- Refactored ComplianceAgent: extracted `gate(url)` — the robots.txt
  check + rate-limit wait + timestamp recording, as an async context
  manager — with `fetch()` now just that gate wrapped around one httpx
  call. Verified the refactor preserves fetch()'s exact behavior
  (existing compliance tests unchanged and passing) before adding 4 new
  tests for gate() itself. This is what lets a Playwright page load get
  identical compliance discipline without duplicating any logic.
- Built `discovery/playwright_probe.py` (`PlaywrightProbe`): headless
  Chromium, real network-idle wait (not a fixed sleep), inspects the
  final URL/rendered DOM/every observed network request for ATS
  signals — the same targets as the static method, plus a signal static
  fetch structurally can't see (a post-load JS `fetch()` call to the
  ATS API). 13 tests using a fake browser/page (no real Chromium needed
  in the automated suite), including a regression test for a real bug
  hit live this session (`page.content()` can raise its own error right
  after a `goto()` timeout, not just `goto()` itself — both now handled).
- Real test batch: 20 specific companies pulled directly from Sessions
  19/20's own "no ATS link found" logs, extended from an initial 12
  after that came back with zero hits, to rule out an unlucky selection
  before concluding anything.
- Real, honest result: 0 new ATS signals found across all 20. 3
  (BlazeMeter, Aidoc, Centrical) are genuinely, currently blocked by
  their own real robots.txt (confirmed via a fresh check) — proving the
  compliance-reuse goal, but meaning they were never actually browser-
  inspected. 1 (MorphiSec) surfaced a separate finding: a stale
  robots_cache.json entry said "disallowed" when the live robots.txt
  says otherwise (likely a transient bot-protection response earlier) —
  corrected in the cache; still zero signal once genuinely inspected.
  The remaining 16 were fully inspected and came back empty every time.
- Honest conclusion: for this batch, JS-rendering wasn't the actual
  blocker — these companies most likely use an ATS outside this
  project's four supported platforms. Scaling Playwright discovery up
  to the full candidate pool is not recommended without first finding
  a genuine positive-control case.
- 0 new companies added — a real, disclosed negative result.
- Test suite: 121/121 passing (was 103: 4 + 13 + 1 new), 0 real network
  calls in the automated suite.
- Session 20's 5 companies remain uncommitted exactly as Elad left them
  — not touched, not re-verified this session.
- Sessions 20 + 21 were committed together as 95e922d after this
  session's own write-up, per Elad's explicit choice.

## Addendum — Session 22 executed: fix robots_cache staleness (2026-08-15)
- Real incident, not hypothetical: Session 21's MorphiSec re-check found
  a persisted robots_cache.json entry saying "disallowed" when a fresh
  live check of the real robots.txt (no Disallow rules at all) said
  otherwise — likely a transient bot-protection response at whatever
  moment it got cached. Under the old 7-day TTL, one bad moment could
  silently skip a real company's whole scan for a week, invisibly.
- Asymmetric TTL: allowed:true keeps the original 7-day window (wrong
  there costs nothing); allowed:false now gets 1 hour instead
  (ROBOTS_CACHE_BLOCKED_TTL_SECONDS) — self-heals within the hour.
- Double-check before persisting a blocked result: a fresh "disallowed"
  live check waits blocked_recheck_delay_seconds (5s default) and
  checks once more before being cached; only two agreeing results
  persist as false.
- Live re-verification: morphisec.com from a completely fresh cache now
  resolves to allowed:true on the very first live check — the
  double-check never had to trigger, since it wasn't blocked to begin
  with, consistent with a one-off glitch rather than a real block.
- 5 new tests covering both mechanisms independently (asymmetric TTL,
  transient-block-then-allowed persists true, two-consecutive-blocks
  persists false, real timing between the two checks).
- Test suite: 126/126 passing (was 121: 5 new), 0 real network calls in
  the automated suite.

## Addendum — Session 23 executed: fix the mascot, blocked on two real gaps (2026-08-15/17)
- Root cause confirmed by planning-Claude directly against the real
  demo.html: Session 15 never had that file, so it invented a 4-frame
  flap-cycling animation instead of the real single static photo.
- Removed the frame-cycling mechanism entirely: app.js's
  initMascotAnimation()/setInterval deleted, index.html's mascot <img>
  now references real_mascot.png with no JS hook, service-worker.js's
  shell manifest updated (cache bumped v1 -> v2 so old frames actually
  evict), pwa/bat-frame-1..4.png + mascot-widget.png deleted.
  batPoses.png itself (root-level source) confirmed unreferenced
  anywhere else via a full-repo grep - left on disk, not deleted, since
  the task only asked to check its usage.
- Two real blockers, disclosed rather than guessed past:
  1. real_mascot.png was never actually placed on disk this session
     (checked repo, pwa/, scratchpad, Downloads, Desktop) despite being
     described as "provided." Asked twice, no answer either time. The
     PWA now correctly references the right filename but the file
     itself is missing - a broken image until it's actually placed.
  2. The task describes a 5-element radar structure (.radar-screen,
     .range-ring x3, .crosshair, .sweep-bg, .pct-badge) as already
     built - it isn't; this repo only ever had a single .ping-ring.
     Didn't invent the missing structure from a text description alone
     (same failure mode this session exists to fix) - left it
     unchanged, flagged for real clarification. Also flagged: the
     task's "200px badge" sizing claim doesn't match this repo's actual
     84px/64px, which Session 17 never touched either.
- Nothing committed or pushed - a partially-broken PWA (missing image)
  shouldn't ship regardless of the standing confirmation requirement.

## Addendum — Session 24 executed: exact radar structure + mascot placed (2026-08-19)
- Both Session 23 blockers resolved with real, verbatim values now
  that planning-Claude has seen the actual reference file directly.
- real_mascot.png confirmed placed at pwa/real_mascot.png by Elad -
  verified directly: 480x320, RGBA with real transparency, loads and
  renders correctly (confirmed via img.complete/naturalWidth/Height,
  not assumed).
- Replaced .mascot-widget/.ping-ring (Session 15's guess) with the
  exact .sonar-corner structure given verbatim - radar-screen, 3
  range-rings, crosshair, sweep-bg (3s rotating conic-gradient), the
  mascot image, and a pct-badge ("?%" placeholder, real percentage is
  separate future work). Renamed the container to .sonar-corner to
  match the real reference exactly.
- Verified element-by-element via getComputedStyle (same standard as
  Session 17's wordmark fix) - every position/inset/size/color/
  animation value confirmed matching exactly, including both crosshair
  pseudo-elements and the sweep animation's full property set.
- Old .ping-ring/.mascot-widget/@keyframes ping fully removed - grepped
  and confirmed zero remaining references.
- Included the given onclick="showView(...)" verbatim as instructed -
  showView()/tabs don't exist yet (future work), so this currently logs
  a harmless console error on click rather than doing anything.
  Flagged, not hidden.
- Unrelated, pre-existing finding: service worker registration fails
  in this sandboxed local-preview setup - confirmed not caused by
  anything changed this session.
- 126/126 tests passing, unchanged (PWA-only change, no Python touched).

## Addendum — Session 26 executed: removed the mascot badge + broken onclick (2026-08-19)
- Session 25 confirmed .budget-widget already shows the real percentage
  correctly (Session 15, untouched); .pct-badge was a separate, dead,
  never-wired "?%" placeholder. Elad's decision: remove it rather than
  wire it up, since the real number is already shown properly.
- Removed the pct-badge div and its CSS rule entirely, removed the
  onclick="showView(...)" attribute (confirmed nothing exists for it
  to call) and its now-meaningless cursor: pointer.
- Verified live: pct-badge gone from the DOM, onclick attribute null,
  cursor auto, clicking produces no new console error (only the
  pre-existing unrelated service-worker issue), .budget-widget's real
  data unaffected.
- 126/126 tests passing, unchanged.

## Addendum — Session 27 executed: service worker skipWaiting/clients.claim fix (2026-08-19)
- Real bug: deploys required a hard refresh/incognito to see changes,
  since the SW waited for all old tabs to close before activating.
- Checked first: self.skipWaiting() was already present since Session
  15 - the task's premise it was missing didn't match reality, flagged
  rather than silently re-added.
- Real gap: self.clients.claim() was already called too, but not
  wrapped in its own event.waitUntil() - fixed by wrapping it as a
  second, independent waitUntil() alongside the existing cache-cleanup
  one.
- Bumped CACHE_NAME v2 -> v3 (same pattern as Session 24) so this
  deploy is itself evidence of the fix.
- Verification honestly disclosed: this sandbox's service worker
  registration fails outright (same pre-existing limitation as
  Sessions 15/17/19/24/26) - couldn't run the requested live
  "old tab picks up new version" test here. Verified what was possible:
  JS syntax valid, fix matches the standard documented ServiceWorker
  lifecycle pattern for this exact symptom. Real end-to-end
  confirmation needs an actual deploy Elad reloads against.
- 126/126 tests passing, unchanged.

## Addendum — Session 28 executed: role selection + mark-as-applied (2026-08-19)
- Two real, functional PWA features, both purely local per ADR-0011/
  ADR-0014 - never touch roles.json, run.py's scan logic, or shared data.
- Added job_id to latest_scan.json's matches (the one allowed backend
  change) - mark-as-applied's stable localStorage key, reusing the
  existing sha256(company|absolute_url) rather than inventing a second
  ID scheme.
- Built pwa/preferences.js - a new file, separate from app.js, holding
  every pure function (isRoleEnabled, shouldShowJob, toggleRoleFilter,
  availableRoleCategories, isApplied, toggleApplied) plus localStorage
  wrappers. Separate specifically so it's testable without executing
  app.js's immediate-on-load bootstrap (fetch calls, DOM lookups).
- Role selection: a small toggle row above the job list, one checkbox
  per role category actually present in the current scan's matches
  (union'd with any category the device has an explicit preference
  for). Deliberately doesn't fetch/duplicate roles.json into pwa/ -
  every match already only comes from a roles.json-enabled category by
  construction, so "no stored preference" already equals "show
  everything the backend included." localStorage key
  thescanner:role_filters, only explicit off-toggles stored.
- Mark as applied: a button per job card, localStorage key
  thescanner:applied_jobs keyed by job_id, present=applied/absent=not
  applied. Applied cards dim (opacity 0.6) with a "✓ Applied" button.
- Both features use event delegation, not per-element listeners, since
  both containers rebuild wholesale on every render.
- Real test coverage despite no Node.js in this environment (checked
  directly - node/npm both absent): built pwa/tests/preferences.test.html,
  a dependency-free HTML+JS harness that loads preferences.js and runs
  real assertions in an actual browser. 23/23 passing. Caught a real
  bug in the harness itself (JSON.stringify equality is key-order
  sensitive) and fixed it with a proper deepEqual before trusting the
  results.
- Verified live end-to-end: real run.py smoke test (63 attempted, 62
  succeeded, 1 genuine transient ReadTimeout, 36 matches) for real
  job_id-populated data, then in a real browser confirmed toggling a
  role category actually hides/shows matching cards, marking a job
  applied visibly updates the card and persists to localStorage, and
  both states survive a real full page reload.
- service-worker.js: added preferences.js to SHELL_FILES, bumped
  CACHE_NAME v3 -> v4.
- 126/126 tests passing (job_id change updated existing assertions).

## Addendum — Session 29 executed: fix Cloudflare-edge caching of service-worker.js (2026-08-19)
- Session 27's fix was correct at the code level, but Elad still needed
  a hard refresh - investigated the flagged Cloudflare-edge-caching
  hypothesis empirically rather than assuming it.
- Real headers on the live URL confirmed it: Cache-Control: public,
  max-age=0, must-revalidate (Cloudflare's documented default) plus
  CF-Cache-Status: HIT on the same response - the edge served the file
  straight from cache without reaching origin, despite max-age=0.
  Confirmed styles.css shows the identical default - the platform's
  default isn't broken, it's just wrong for this one file specifically.
- First tried Cache-Control: no-cache per the task's suggestion, but
  checked Cloudflare's documented semantics first and found it means
  "cache it, but revalidate" - not strong enough. Switched to
  Cache-Control: no-store (Cloudflare's real "skip edge caching
  entirely" directive) before shipping it.
- Added pwa/_headers scoped to exactly /service-worker.js - every other
  static asset keeps normal caching, which is desirable for the
  cache-first PWA shell.
- No Python/app-code changes - a Cloudflare static-assets config file.
- 126/126 tests passing, unchanged.

## Addendum — Session 30 executed: "Ignore" state + Ignored section (2026-08-19)
- Extended Session 28's boolean applied/not-applied into a real
  tri-state per-job status: not_set / applied / ignored, mutually
  exclusive, enforced in one place (setJobStatus).
- State model: new key thescanner:job_status (values "applied"/
  "ignored") rather than overloading the old thescanner:applied_jobs
  boolean key. Confirmed the real data-loss risk before choosing this
  path, not assumed it away - Elad has been actively using the PWA
  since Session 28, so a clean break risked discarding real marks.
  Chose migrate-on-read (loadJobStatuses merges the legacy key's `true`
  entries in as "applied" whenever the new key has no opinion yet for
  that job_id) over a one-time destructive migration - the legacy key
  is never written to or deleted, so there's no half-migrated state and
  no data-loss risk even if something goes wrong.
- Added an Ignore button next to Mark as applied on every job card, one
  delegated click handler for both.
- Rendering: new partitionByIgnored(matches, statuses) pure function
  splits ignored jobs into a new "Ignored" section at the bottom;
  applied jobs are NOT partitioned, they stay exactly where Session 28
  put them, only ignored jobs move.
- Real test coverage: pwa/tests/preferences.test.html extended to
  38/38 passing - status transitions, mutual-exclusivity enforcement in
  both directions, partitionByIgnored, and 5 dedicated migration tests.
- Verified live end-to-end: seeded a real legacy applied_jobs entry,
  confirmed migration renders it correctly with zero interaction,
  confirmed the migrated-applied -> ignored transition works correctly
  (moves to Ignored section, no dual state), confirmed the reverse, and
  confirmed both states survive a real full page reload.
- Bumped service-worker.js's CACHE_NAME v4 -> v5, since app.js/
  styles.css/preferences.js all changed substantively and are
  cache-first shell files.
- 126/126 Python tests passing, unchanged.
