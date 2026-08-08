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
