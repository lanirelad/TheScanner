# PLAN.md — Roadmap

## Phase 0 — Scaffolding (current)
- [x] Living docs created (this set).
- [ ] Repo initialized, pushed to GitHub (private).
- [ ] `roles.json` seeded with devops + technical_support categories and
      starter EN/HE tags (expandable later without code changes).
- [ ] `companies.json` seeding started — target is maximum feasible coverage
      (see ARCHITECTURE.md §4a), not a small pilot list. Start with
      ATS-directory harvesting (Greenhouse/Lever/Comeet) since those come
      with adapters for free, then layer in registry-sourced companies.
- [ ] Fixture set for sandbox testing (3–5 companies, cached responses) —
      small on purpose; this is separate from the size of the real
      companies.json.

## Phase 1 — Core pipeline, Greenhouse + Lever only
- [ ] Greenhouse adapter (JSON API) — lightweight list first (ADR-0016).
- [ ] Lever adapter (JSON API) — lightweight list first (ADR-0016).
- [ ] `locations.json` — accepted locations, EN + HE (ADR-0016).
- [ ] Canonical schema + normalizer.
- [ ] Location filter + keyword filter (title-level, Stage 1) — reject
      early, before any full-description fetch.
- [ ] Stage 2: full-description fetch only for ambiguous title matches.
- [ ] Compliance Agent (robots.txt + rate limit).
- [ ] SQLite storage + dedup.
- [ ] CLI run: prints new matches to console.

## Phase 2 — Comeet + custom fallback
- [ ] Comeet adapter.
- [ ] Generic HTML scraper fallback (Playwright) for unknown ATS.
- [ ] ATS auto-detection helper (given a career page URL, guess the platform).

## Phase 3 — Deployment, scheduling, PWA client
- [ ] GitHub Actions workflow: `schedule` (twice daily) + `workflow_dispatch`
      (manual "Run now" button), per ADR-0009/0010.
- [ ] Shared scan results committed back to repo as JSON/SQLite after each run.
- [ ] PWA shell: manifest.json, service worker, install prompt, dark/light
      theme (ADR-0013).
- [ ] PWA reads shared scan results; applies local (device-only) role/tag
      filters and shows `new` vs `still_open` (ADR-0011).
- [ ] "Mark as applied" button — writes only to local device storage
      (IndexedDB/localStorage), never to the shared repo (ADR-0011, ADR-0014).
- [ ] "Apply" link on every job card, opening `source_url` directly (ADR-0015).
- [ ] Cloudflare Worker: stores Web Push subscriptions; scan workflow
      notifies it of new matches so it can push to subscribed devices
      (ADR-0012).

## Phase 4 (optional, later) — LinkedIn cross-reference
- [ ] Decide data source for "is this on LinkedIn" (own account search vs.
      third-party API) — flag privacy/ToS considerations before building.
- [ ] Tag postings not found on LinkedIn.

## Open questions
- How to harvest company slugs at scale from Greenhouse/Lever/Comeet
  (need to research whether each platform exposes any kind of public
  directory/search, or whether this has to be built from a seed list plus
  registry cross-referencing).
- Whether to add role categories beyond devops/technical_support later
  (mechanism already supports it via roles.json — just need to decide if/when).
- Exact times of day for the twice-daily scheduled scan (TBD, low priority).

## Robustness follow-ups (identified in code review, 2026-08-07 — not blockers for current sessions)
- `ComplianceAgent`'s robots.txt fetch has no timeout (`RobotFileParser.read()`
  only catches `OSError`, not a hang on a slow-but-alive server). Fix before
  real company harvesting at scale, not urgent for the current 4-company
  test set.
- `ComplianceAgent`'s internal caches (`_robots_cache`, `_last_request_at`)
  are plain dicts, not thread-safe. Needed before any concurrency work —
  sequential fetching across ~1,500 companies won't hit the 15-30 min
  estimate without parallelizing across domains eventually.
- Greenhouse pagination on the public `/jobs` boards endpoint is unverified
  beyond one company's job count (Wiz, 129 jobs, one response). Confirm
  before trusting it doesn't silently truncate for a larger company.

## Open decisions carried forward from Session 3 (to resolve next session)
- **`absolute_url` source for Lever**: Session 3 used `hostedUrl` (the
  posting page) rather than `applyUrl` (the application form directly) —
  a judgment call, not something the data forced. Needs Elad's explicit
  sign-off before this becomes the de facto convention Comeet's adapter
  follows too.
- **Exploratory-call headroom policy**: Session 3 made 12 live calls
  against an unfamiliar ATS's undocumented schema instead of the "one
  fetch each" a task prompt specified, fully disclosed and still
  rate-limited/compliant throughout. Worth formalizing as an explicit
  standing rule (e.g. "one designated fetch per company for the *final*
  captured fixture; unlimited compliant exploratory calls permitted when
  facing an ATS whose schema isn't yet documented in this repo, provided
  it's disclosed in the handoff") rather than leaving future sessions to
  guess whether they have that latitude.
- **Fixture file size**: `palantir_stage1_raw.json` is 5.98 MB (Lever's
  full-payload-always behavior makes this unavoidable for a real fixture).
  Not urgent while git init is deferred, but worth trimming to a
  representative subset before the first real commit.
- **Test file organization**: `tests/test_filters.py` now covers 3
  adapters' worth of tests (13 total) in one file. Worth splitting into
  per-module test files once Comeet adds a third adapter's tests here —
  flagged twice now (Session 2 and 3), not yet acted on.

## Scale target correction (2026-08-07)
Realistic addressable universe: ~8,000-9,000 Israeli hi-tech companies
(startups included, per Elad's estimate) — supersedes the earlier informal
"~1,500" figure used for initial time estimates. This changes:
- Concurrency model: async/await, not threads (ADR-0021).
- Scanning splits into a fast/frequent "stable" track and a slow "full
  sweep" track covering the complete universe (ADR-0020).
- Additional role categories (e.g. "software development," mentioned as a
  likely future addition) will increase match volume/handling requirements
  — not an immediate change to roles.json, but a reason the architecture
  needs to hold up under more results, not fewer.

## Robustness follow-ups — revised for async (supersedes the threads/locks version)
- Retrofit `ComplianceAgent` to use async HTTP (httpx.AsyncClient or
  aiohttp), with a per-domain semaphore/lock implemented in an
  async-native way (not a bare dict + threading.Lock).
- Retrofit `GreenhouseAdapter` and `LeverAdapter` to async `fetch_stage1_jobs`.
- Convert `tests/` to `pytest-asyncio` (or equivalent) so fixture-based
  tests still run with zero real network calls.
- robots.txt fetch still needs an explicit timeout (unchanged finding from
  the earlier code review) — doubly important once many domains are being
  checked concurrently.
- Greenhouse pagination still unverified beyond one company's job count —
  unchanged, still needs confirming before trusting it at scale.

## New feature: scan-budget counter (ADR-0022)
- [ ] `usage_log.json`: each scan run appends {date, duration_minutes,
      company_count, track (stable/full-sweep)}.
- [ ] Compute running monthly total vs. the known free-tier cap
      (2,000 min/month, private repo).
- [ ] Projection tool: given a chosen scan frequency + company-count scale,
      estimate % of monthly budget using historical average run duration —
      not a theoretical formula.
- [ ] Dashboard widget: playful "mascot eating bandwidth" percentage
      visual (main view).
- [ ] Settings/stats panel: plain numeric percentage + minutes-used/minutes-
      remaining (professional view, same data).
- [ ] Surface a soft warning if a chosen configuration projects to >90% of
      the free budget, before Elad commits to that schedule.

## Optimization: persist robots.txt cache across runs
- Currently `ComplianceAgent`'s robots.txt cache is in-memory only, reset
  every fresh GitHub Actions job. Robots.txt rarely changes, so this is a
  recurring cost on *every* scan (not just onboarding of new companies) —
  worth persisting with a reasonable TTL (e.g. commit a small
  `robots_cache.json`, or store in the same place as the usage log) rather
  than re-fetching every domain's robots.txt on every single run.
- Distinct from onboarding cost: onboarding (ATS detection, parser
  building) is a one-time-per-company cost already solved by recording
  `ats`/`ats_slug` permanently in `companies.json` — this robots.txt item is
  a separate, smaller, but real recurring inefficiency.

## Robots.txt cache persistence — chosen approach
Decided: persist as `robots_cache.json`, committed to the repo alongside
scan results (same pattern as everything else). Entry shape:
`{domain, allowed, checked_at}`. TTL ~1 week before re-checking a domain —
robots.txt essentially never changes. Fold into the async retrofit session
(ADR-0021) since `ComplianceAgent` is being touched there anyway.

## App-side UX requirements (not yet built — design notes for whenever GUI work starts)
- **Background operation:** push notifications must keep arriving even when
  the app isn't open in the foreground — this is inherent to Web Push (a
  PWA) but must be explicitly verified once built, not assumed.
- **Exit-warning scope, precisely defined:** only warn before closing if
  closing would actually interrupt something the APP ITSELF is doing (e.g.
  a manually-triggered scan the app is actively tracking progress on).
  Never warn about the scheduled cloud-side GitHub Actions scan — that runs
  independently in GitHub's infrastructure regardless of whether the app or
  phone is open, so closing the app can't affect it and a warning there
  would be misleading.
- **Mascot:** bat, chosen for the dashboard/stats presenter (see
  CHANGELOG.md for reasoning — genuine echolocation/sonar association,
  fits dark-mode theme).

## Mascot: finalized asset
Real mascot art chosen and integrated into demo.html (embedded base64,
single-file portability). Source: user-generated image, resized from
1536x1024 (2.4MB) down to 480x320 (83KB) for practical UI use — this
smaller PNG is the one that should ship in the real app, not the original.
Bat design: warm grey body, rust-orange collar, cute rounded features —
deliberately distinct from any Batman association (color, proportions,
expression all differ). No SVG needed for this asset; static PNG is
sufficient since the mascot doesn't need to re-theme or animate per-part.

## Onboarding execution model (ADR-0023)
Full-sweep/onboarding (ADR-0020) happens via Claude Code sessions, not a
GitHub Actions workflow — see ADR-0023 for why. Practical implication:
there's no need to build an "onboarding GitHub Actions workflow" at all.
Instead, future sessions should be task-prompted like: "here are N candidate
companies — detect ATS, verify a working adapter path, commit verified
entries to companies.json." GitHub Actions only ever runs the stable-track
scan over already-verified companies.

## Mascot assets (repo root, added by Elad directly)
- `mascot.png` — primary mascot asset, in active use (sonar corner widget).
- `batPoses.png` — 4 additional reference poses of the same bat, kept for
  future use (e.g. empty states, notification icons, other UI moments
  that might want a different pose than the primary one). Not wired into
  anything yet — just available when needed.

## Ashby promoted to a real adapter (ADR-0024)
CC_TASK_007.md written: build AshbyAdapter hitting Ashby's real public API
directly, verify against Session 6's monday.com scrape, reclassify
monday.com's companies.json entry from "custom" to "ashby" once confirmed.
This effectively makes the adapter roster: Greenhouse, Lever, Comeet,
Ashby, plus the config-driven CustomAdapter as a true last-resort fallback.

## Phase 1 complete (2026-08-08)
Storage, dedup, and a real end-to-end CLI run all working — proven live
against 7 real companies, two consecutive runs, correct new/still_open
transition. See DECISIONS.md ADR-0026 for the job_id design this depends
on. Phase 2 (adapters) was already complete as of Session 7's ADR-0025.

## Minor follow-ups from Session 8 (low priority, not blocking)
- No formal schema-validation function between adapter/filter output and
  storage — currently enforced implicitly (dict shape + SQL named params),
  fails as a Python/sqlite3 error rather than a clear message if it ever
  drifts. Worth a real validator once more producers of this shape exist.
- run.py's broad Exception catch per company is a deliberate resilience
  choice — acceptable, just worth remembering if an adapter seems to be
  silently failing during future development (the real error is captured,
  just not raised loudly).
- The failed-company counting path is only unit-tested with synthetic
  data so far (this session's live run had 100% success). Will get real
  proof organically whenever a company legitimately fails.

## Settings screen spec (for whenever PWA work starts, ADR-0027/0028)
- **Role selection**: multi-select from roles.json categories (devops,
  technical_support, npi, software_development, project_manager) — local
  device preference, no shared-infra implications.
- **Approx. company count**: informational display, reads live from
  companies.json (or eventually the stable-track subset once ADR-0020's
  two-track split is actually built) — read-only, no fork needed.
- **Scan frequency + schedule**: real app setting now (single-owner
  reality, ADR-0027), backed by schedule_config.json + the config-gated
  workflow pattern (ADR-0028). Warn if >2 scans/day is selected, with a
  "never show this warning again" dismiss option (store dismissal
  locally). Show scheduled-vs-on-demand toggle; if scheduled, let the
  time(s) of day be set.
- **Future clone/template mechanism** (ADR-0027): make the repo a proper
  GitHub template (or provide clear fork-and-deploy docs) once/if the app
  is ever shared beyond Elad. Not urgent now, but keep the repo structure
  clone-friendly (no hardcoded personal values outside config files).

## Company-growth playbook (this section didn't exist before Session 32
— the task that introduced "Phase 1" referenced it as if it did; added
now per ADR-0030's protocol, backfilling what Sessions 18-21 already did
plus a real record of Session 32 so the phase numbering means something
going forward)
- **Phase 0 (Sessions 18-20):** guessed/researched company names, guessed
  or read off their real ATS slug directly, validated against the live
  API. 9 -> 63 companies. Structurally hit a ceiling: three independent
  sourcing methods all landed in the same low single-digit-percent hit
  rate, diagnosed as most real career pages being client-rendered SPAs a
  static `httpx` GET can't see into (ADR-0031).
- **Phase 0.5 (Session 21):** Playwright-based discovery approved for
  onboarding sessions only (ADR-0031). Real, honest negative result on a
  20-company batch: JS-rendering wasn't the actual blocker for that
  batch — 16 fully-inspected companies (17 counting MorphiSec, narratively
  separated because it also surfaced a robots_cache bug) showed zero
  signal for any of this project's 4 supported platforms.
- **Phase 1 (Session 32): recognize unsupported platforms.** Built
  recognition-only fingerprints (never adapters) for Workday,
  SmartRecruiters, and iCIMS in `discovery/playwright_probe.py`, each
  empirically verified against one real example before being trusted.
  Real result re-running recognition against Session 21's batch: 0 of
  those companies use any of these 3 platforms. Instead, re-deriving
  real career-page URLs via web research (Session 21's own candidate
  list/script were never committed to the repo) surfaced 8 real hits on
  the 4 platforms this project already supports — 6 Comeet, 2
  Greenhouse — merged into `companies.json` (63 -> 71) after live
  verification. `companies_unscannable.json` now holds 4 positively
  confirmed cases (1 real platform — Rippling — plus 3 confirmed access
  blocks). See PROGRESS.md's Session 32 addendum for the full per-company
  breakdown and the honest "genuinely unresolved" list (companies with no
  recognized signal at all, deliberately not force-fit into either
  outcome).
- **Real gap surfaced, not yet fixed (flagged for a future phase):**
  Comeet's own widget-loading domain is `comeet.co` (`www.comeet.co/
  careers-api/api.js`), distinct from the public job-page domain
  `comeet.com` this project's `CM_RE` regex matches — a real detection
  gap that likely caused some of the Comeet hits Session 32 found via web
  research instead of `PlaywrightProbe` directly (Overwolf, Artlist,
  Claroty, DriveNets). Extending `CM_RE`/`_detect_ats` to also parse a
  `COMEET.init({token, "company-uid", ...})` call when only the widget
  domain is observed would likely surface more Comeet-using companies
  automatically on the next re-scan, without needing web research per
  company. Not built this session — flagged as the most promising next
  step, not proven to be worth a whole adapter-scale effort yet.
- **Open decision, deliberately not made yet:** whether to build a real
  adapter for whichever unsupported platform proves most common. Session
  32 only confirmed one company (Totango) on one platform (Rippling) —
  not enough real signal to justify committing to build against it. A
  future phase re-running recognition against a much larger candidate
  pool (not just Session 21's 20-company batch) would give an honest
  answer to "is any one platform common enough to be worth a fifth
  adapter," rather than guessing from one data point.
- **Phase 2 (Session 35): custom-domain-focused harvesting + the
  comeet.co fix.** Explicit goal shift from Phase 1's "grow the count"
  to "find companies with genuinely bespoke or minimal public hiring
  infrastructure — exactly the roles that wouldn't appear on LinkedIn/
  aggregator sites either," the actual differentiation this project
  exists for. Checked 6 new candidates from real 2026 funding coverage
  (Majestic Labs, Port, Kela Technologies, Line 5, ForSight Robotics,
  AIR) — all verified as real, distinct companies first (Kela
  Technologies in particular shares its name with an unrelated,
  older cybercrime-threat-intel firm; disambiguated before touching
  anything). Fixed the comeet.co gap flagged in Phase 1: added
  `CM_WIDGET_UID_RE` to `discovery/playwright_probe.py`, recognizing a
  `company-uid=` parameter on any `comeet.co` request even when no
  public `comeet.com/jobs/{slug}/{uid}` link exists anywhere on the
  page — this is exactly what resolved 3 of Phase 1's genuinely-
  unresolved companies (Coralogix, Guesty, Upwind), each white-labeling
  or embedding Comeet in a way the old detection couldn't see at all.
  Real result: 5 new Comeet companies merged into `companies.json`
  (Port, Kela Technologies, Coralogix, Guesty, Upwind — 71 -> 76), 7
  new `companies_unscannable.json` entries split across two genuinely
  different reasons (4 real, confirmed custom career pages with real
  structured job data that CustomAdapter's current JSON-only extraction
  strategy can't parse — Coralogix and Guesty turned out to *not* need
  this bucket once their real Comeet integration was found, but
  ForSight Robotics, AIR, and Quantum Art do, plus Session 32's
  Definity re-confirmed; and 2 real companies with no structured job
  data published at all — Majestic Labs, Line 5, both genuinely
  stealth/pre-launch on hiring). 3 of Session 32's 8 unresolved
  companies remain genuinely unresolved even after this deeper pass
  (MorphiSec, HiBob, Attenti) — a real, disclosed negative result, not
  forced into either bucket.
- **Real architectural signal, not yet acted on:** this session found
  the same "real job data, rendered as static HTML with no JSON blob"
  pattern in 5 different real companies (Coralogix and Guesty turned
  out to be Comeet after all, but ForSight Robotics/AIR/Quantum Art
  genuinely aren't anything this project recognizes) — suggesting this
  pattern might be *more* common in the wild than the JSON-hydration
  pattern `CustomAdapter` currently supports (its only real confirmed
  user is still monday.com, from Session 6). Worth a real evaluation in
  a future phase: is a CSS-selector-based extraction strategy (parse a
  repeating job-item element by class/structure, config-driven same as
  the JSON strategy) worth adding to `CustomAdapter` as a second real
  strategy, now that there's more than one hypothetical company that
  would benefit from it.
- **Phase 3 (Session 36): built the CSS-selector strategy Phase 2
  flagged.** `CustomAdapter` gained a second real strategy
  (`css_selectors`, `adapters/custom.py`) alongside the original
  `json_blob` one — config-driven the same way, `custom_selectors.json`
  now requires an explicit `strategy` field (monday.com's own entry
  updated to say `"json_blob"` rather than leaving it implicit). Real
  result: ForSight Robotics, AIR, and Quantum Art — all three flagged
  unscannable in Session 35 specifically because of this gap — moved
  back into `companies.json` (76 -> 79) once real fetched data was
  confirmed against all three, not synthetic test data alone. Real
  per-company quirks the schema had to handle rather than assume away:
  a genuinely empty CMS field (Quantum Art's location), and a company
  with zero real per-job links at all (AIR's listings open a JS modal
  instead) — see ARCHITECTURE.md §4a for both. Also confirmed (Session
  36, Part 1) that Comeet's own 26 companies share one real pacing lane
  exactly like Greenhouse's, regardless of white-labeling — `adapters/
  comeet.py`'s URL template always targets `www.comeet.com` directly,
  by design, since Session 5/19. Set a deliberate httpx connection
  limit (200, up from the library's implicit 100) reasoned from GitHub
  Actions' real runner specs and today's real domain count (still just
  6), rather than leaving it as an unexamined default — see
  ARCHITECTURE.md §4a for the full reasoning and how it was verified as
  actually applied, not just documented.
- **Phase 4 (Session 37): the largest candidate pool assembled so far,
  first verification pass.** Three independently-sourced files (Hebrew
  business media, Elad's own LinkedIn browsing, Wikipedia's Israeli
  company categories) combined to roughly 450 real candidate names —
  an order of magnitude beyond any prior single round. Explicitly
  scoped as multi-session work from the start; this session prioritized
  Wikipedia's own "strong likely-active subset" (37 names, historical-
  category caveat acknowledged going in) and LinkedIn's explicitly-
  flagged actively-hiring names first, per the task's own priority
  order. Real result: 12 new companies (9 Comeet, 3 Greenhouse) —
  `companies.json` 79 -> 91 — and 8 new `companies_unscannable.json`
  entries, every one confirmed live (not from secondhand research
  alone) as genuinely acquired/absorbed with no distinct careers
  presence left, or actively bot-blocked. Both flagged identity-
  collision risks resolved with real evidence: Foresight Automotive
  and ForSight Robotics are confirmed different companies (similar
  name, different industries, different domains); Nanox Vision and
  Nano-X are confirmed the *same* company (Nano-X Imaging Ltd.'s own
  official domain is literally nanox.vision).
- **Resume-from-here, explicit per the task's own instruction not to
  fake completeness:** within the Wikipedia priority subset, 15 names
  remain genuinely unresolved (not forced into either bucket) — XM
  Cyber (a search-sourced uid turned out to be wrong; real one not yet
  found), Check Point/Papaya Global/Cyberint/Sapiens International (all
  robots.txt-blocked at check time — may just need a retry, per
  ADR-0002's own self-healing TTL design, not necessarily a permanent
  block), Cellebrite/Checkmarx/StarkWare Industries/Varonis Systems/
  Any.do/DealHub/TeraSky/Sela/ZoomInfo (no recognized-platform signal
  found in this pass — genuinely unresolved, not confirmed-unscannable).
  Entirely untouched this session: ~54 more names in
  candidates_linkedin_sourced.md, the ~165-name combined media-research
  list, and the other Wikipedia categories (cybersecurity, AI, solar
  energy, internet companies) plus the still-missing complete 153-name
  English Wikipedia "Software companies of Israel" list (referenced in
  the task's own attachments but never actually pasted in — flagged
  again here, still needed for a future session to work from).
