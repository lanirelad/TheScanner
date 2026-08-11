# ARCHITECTURE.md

## 1. Data flow

```
Company list (companies.json)
   -> ATS Adapter, STAGE 1: lightweight job list (title, department,
      location — no full description; cheap, one call per company)
   -> Location filter (locations.json)  -> reject non-matching locations
   -> Title/tag filter (roles.json)     -> reject non-matching roles,
                                            resolve clear matches
   -> ATS Adapter, STAGE 2 (only for ambiguous cases): full description
      fetch, then re-run the tag filter against description text
   -> Normalizer Agent  -> canonical Job schema
   -> Compliance Agent  -> (gate: robots.txt honored? rate limit ok?)
   -> Dedup/Diff Agent  -> new postings only
   -> (optional) LinkedIn Cross-Reference Agent -> tag "not on LinkedIn"
   -> Storage (SQLite) -- shared, same for every install
   -> App/Worker deliver results + push notifications (see §9-11)
```

Stage 1 always runs for every company (it's cheap and how department/
location/title become visible at all). Stage 2 (fetching the full
description) is the one that's skipped for the vast majority of roles —
only ambiguous title matches need it. See ADR-0016.

**Empirical note (confirmed Session 1, live against Wiz/Playtika):**
Greenhouse's lightweight `/jobs` endpoint (no `content=true`) does **not**
return a `department` field at all — it's `None` for every job, on every
company tested so far. Matching at Stage 1 for Greenhouse currently relies
on `title` + `location` only; `department` may become available for other
ATS platforms (Lever/Comeet) and should be re-verified per-adapter, not
assumed.

**Empirical note (confirmed Session 3, live against Palantir/Smarsh):**
Lever's `/v0/postings/{slug}` endpoint has no lightweight mode at all — a
`content=false` query param made zero difference to the response, which
always includes full description/`descriptionBody`/`lists`/`additional`
fields for every posting. For Lever, "Stage 1" is a parsing-layer
distinction only (we discard what we didn't ask for and can't avoid
receiving); the network cost is identical to a full fetch either way.
`department` is company-configurable, not fixed: Palantir's postings have
no `department` key at all, Smarsh's do.

**Empirical note (confirmed Session 5, live against AT&T Israel R&D
Center/Enlight Renewable Energy):** Comeet has no dedicated public JSON
API for either company checked. The career page
(`https://www.comeet.com/jobs/{slug}/{uid}`) is server-rendered HTML with
the full job list embedded as a `COMPANY_POSITIONS_DATA = [...]`
JavaScript variable inside a `<script>` tag — present in the initial HTML
response itself, no client-side JS execution/headless browser needed. Same
situation as Lever: no lightweight-vs-full-content mode exists, since the
embedded data already includes full HTML descriptions. Unlike Greenhouse
and Lever, though, `department` came through cleanly and consistently for
every posting on both companies checked.

**Empirical note (confirmed Session 6, live against monday.com):**
Genuinely custom (non-ATS) career pages don't necessarily need JavaScript
execution/a headless browser — confirmed before writing any parser, per
ADR-0019's discipline, not assumed. monday.com's `/careers` page (UUID-
based job URLs, no known ATS fingerprint) is server-rendered: a plain HTTP
GET already returns a `<script id="__NEXT_DATA__">` tag (Next.js's
standard SSR data-hydration mechanism) containing the full position list
as JSON, nested under an opaque per-deploy-looking UUID key. This won't
generalize to every custom site — a page that truly builds its job list
client-side after load would fail this same check and require an explicit
Playwright/headless-browser decision (out of scope, flagged not built).
Interesting side-finding, not acted on: every monday.com position carries
`"source": "ashby"` — a real ATS platform's data is being proxied through
an otherwise-custom page rather than linked out to ashby.com. If that
turns out to be a common pattern across other "custom" companies, a
dedicated Ashby-aware strategy might be worth more than treating each one
as fully bespoke — a question for a future onboarding session.

**Empirical finding (Session 7, blocking — no AshbyAdapter built):**
ADR-0024 assumed Ashby's public posting API
(`https://api.ashbyhq.com/posting-api/job-board/{clientname}`) was
directly fetchable, same tier as Greenhouse/Lever's public APIs. Checked
before building anything, per ADR-0019's discipline: `api.ashbyhq.com`'s
own `/robots.txt` returns HTTP 401 Unauthorized (confirmed directly, not
just via the Compliance Agent's own check). Both `urllib.robotparser`'s
standard convention and `ComplianceAgent`'s logic (compliance/agent.py,
`_check_robots_live`) treat a 401/403 on robots.txt itself as "this domain
restricts automated access, disallow everything" — a conservative, correct
default, not a bug. `robots_cache.json` now persists
`api.ashbyhq.com: {"allowed": false}`. Per ADR-0002 ("cannot be bypassed,
including 'just for a quick test'"), no AshbyAdapter fetch was built or
attempted beyond this compliance check. monday.com stays on `CustomAdapter`
(Session 6) — that path is confirmed working and compliant. Whether ADR-0024
itself needs revisiting (its "verified independently" note apparently
didn't check robots.txt) is a decision for Elad/planning-Claude, not
something resolved here.

**Empirical note (confirmed Session 13, live against Optimove/Mobileye —
EU-region hosting):** Greenhouse and Lever handle EU data residency
differently at the API layer, confirmed rather than assumed for both:
Lever genuinely has a separate regional API domain
(`api.eu.lever.co`, verified against Mobileye — 200 OK, byte-for-byte the
same response shape as the global `api.lever.co`). Greenhouse does not:
`boards-api.eu.greenhouse.io` doesn't resolve at all (DNS failure), and
Optimove's EU-hosted board (`job-boards.eu.greenhouse.io/optimove`, the
public page) is served via the ordinary global `boards-api.greenhouse.io`
API with no regional variant — EU residency there only affects the public
page domain, not the read-only JSON API. `GreenhouseAdapter`/`LeverAdapter`
both take an `ats_region` constructor argument and consult a
`REGION_DOMAINS` dict (empty for Greenhouse, `{"eu": "api.eu.lever.co"}`
for Lever) with a plain default-domain fallback — adding a confirmed
future region is a dict entry, no code change, but nothing is added
speculatively for a region that hasn't actually been checked.

## 1a. Role configuration (roles.json)

Roles are **not hardcoded**. `roles.json` defines every role category the
scanner should look for, so new roles can be added without touching code.

```json
{
  "devops": {
    "enabled": true,
    "label_en": "DevOps Engineer",
    "label_he": "מהנדס DevOps",
    "tags_en": ["devops", "sre", "site reliability", "platform engineer",
                "infrastructure engineer", "ci/cd", "kubernetes engineer"],
    "tags_he": ["דיבאופס", "מהנדס תשתיות", "אבטחת אתרים ותפעול"]
  },
  "technical_support": {
    "enabled": true,
    "label_en": "Technical Support Engineer",
    "label_he": "מהנדס תמיכה טכנית",
    "tags_en": ["technical support", "support engineer", "customer support engineer",
                "field engineer", "application support", "helpdesk engineer"],
    "tags_he": ["תמיכה טכנית", "מהנדס תמיכה", "תמיכה ללקוחות", "מהנדס שטח"]
  }
}
```

- Each role category has a set of **tags** (keywords/phrases) in English and
  Hebrew — this is how new/changing terminology gets caught without a code
  change (e.g. a company calls the role "Platform Reliability Engineer" —
  just add the tag).
- Matching is tag-based, case-insensitive, checked against title first, then
  description if no title match.
- Adding a new role category (e.g. "QA Automation Engineer") means adding a
  new block to `roles.json` — no code changes required.
- `roles.json` is user-editable and lives in the repo, not hardcoded in
  `core/`.
- **`enabled` (Session 11):** a category whose tags are never matched
  against when `false`, even if a title would otherwise clearly hit one —
  the config-level half of the "role selection" setting from the
  PLAN.md settings-screen spec, built now because `roles.json` already has
  5 categories (`npi`, `software_development`, and `project_manager` were
  added after the initial devops/technical_support pair) but Elad only
  wants devops/technical_support active for now. The other three stay in
  the file, not deleted, ready for whenever they're actually turned on.
  Missing the `enabled` key entirely is treated as **disabled** (fail
  safe, not fail open) — see `core/filters.py`'s `_matching_role_tag` for
  the reasoning.

## 1b. Location configuration (locations.json) — ADR-0016

Same config-driven pattern as `roles.json`, checked at Stage 1 (the cheap
lightweight list), before any full-description fetch:

```json
{
  "accepted_locations": {
    "en": ["Israel", "Tel Aviv", "Herzliya", "Ra'anana", "Remote - Israel"],
    "he": ["ישראל", "תל אביב", "הרצליה", "רעננה", "מרחוק - ישראל"]
  }
}
```

- Matching is substring/keyword-based against the location field returned
  in Stage 1, same mechanism as role-tag matching.
- A role whose location doesn't match anything in this list is discarded
  immediately — it never reaches Stage 2 (full description fetch), storage,
  or the app.
- This is what keeps a multinational company's global job list from
  ballooning the scan — most of its roles get rejected for free at Stage 1.

## 2. Canonical Job schema (draft — refine in DECISIONS.md as ADR when settled)

```
job_id (stable hash of company + source_id)
company
title
location
role_category      # matched key from roles.json, e.g. "devops" | "technical_support" | ...
matched_tag        # which specific tag triggered the match, for auditability
scan_status        # new | still_open  (derived: new = first_seen_at == this run)
application_status # not_applied | applied  (LOCAL to each device only — never
                    # stored in the shared repo, see §10)
source_url          # direct link to the original posting — always shown as
                    # a tappable "Apply" link, never mirrored/copied (ADR-0015)
source_ats         # greenhouse | lever | comeet | custom
posted_at
first_seen_at
last_seen_at
on_linkedin         # bool | unknown
raw_description_hash   # never store full copyrighted text long-term
```

**Implementation note (Session 8):** `storage/db.py`'s actual SQLite table
is a deliberate subset of the draft above: `job_id, company, title,
location, role_category, matched_tag, source_url, first_seen_at,
last_seen_at`. `scan_status` isn't a stored column — it's computed at read
time by `core/dedup.py` from `first_seen_at`/`last_seen_at`, matching this
section's own field definition exactly. `source_ats`, `posted_at`,
`on_linkedin`, and `raw_description_hash` aren't populated by anything
upstream yet (no per-job ATS tag, no posted-date field from any adapter,
no LinkedIn Cross-Reference Agent, no description content retained past
Stage 1), so they're left out rather than added as dead columns.
`application_status` is never a column, per ADR-0011/ADR-0014 — enforced
by a dedicated test (`tests/test_storage.py`) that asserts the real table
schema directly, not just that no code path writes it.

## 3. Module boundaries

- `adapters/` — one file per ATS type. Only place that knows API/HTML shapes.
  Adapters must not know about filtering, storage, or notification.
- `core/` — canonical schema, dedup logic, keyword filter. No network calls.
  No adapter-specific knowledge. Adapters depend on core; core never depends
  on adapters (dependency direction rule — checked by regression gate).
- `compliance/` — robots.txt checking, rate limiting. Every adapter call goes
  through this layer; nothing bypasses it.
- `storage/` — SQLite persistence (`storage/db.py`, Session 8). Dedup
  *state* lives here (the set of known job_ids); dedup *logic* (deciding
  new vs. still_open from that state) lives in `core/dedup.py` instead —
  storage only persists and reads back plain values, so the same dedup
  logic would work unchanged against a different backend later.
- `notify/` — email/Telegram senders. No business logic.
- `usage/` — scan-run telemetry (ADR-0022). Kept separate from `storage/`
  so its reader/projection logic can never end up reasoning about
  job-posting data, and vice versa. See §13.
- `schedule/` — scan-schedule gate-check logic (ADR-0028, Session 9). Same
  reasoning as `usage/`: a distinct cross-cutting concern gets its own
  small package rather than being wedged into `core/` or anywhere else.
  `python -m schedule` is the CLI entry point the GitHub Actions workflow
  calls; see §9a for the cron-cadence-vs-real-schedule distinction.
- `run.py` (repo root, Session 8) — the actual end-to-end CLI entry point:
  loads config, fetches every company concurrently (ADR-0021), filters,
  dedups, persists, logs usage, prints a summary. Lives at the repo root
  like `usage_log.json`/`robots_cache.json`'s data files, not inside any
  of the packages above, since it's the orchestration layer that ties all
  of them together rather than belonging to one.
- `pwa/` (Session 15) — the entire deployed PWA (HTML/CSS/JS, service
  worker, manifest, icons) plus `latest_scan.json`/`usage_summary.json`
  themselves. This is a hard boundary, not a style choice: `wrangler.jsonc`
  makes this directory the deployed site's whole file tree, so anything
  the PWA needs to fetch has to live inside it. See §9a.

## 4. Three-layer QA framework

**L1 — Static Regression Guard**
- L1.1: `core/` never imports from `adapters/` (dependency direction).
- L1.2: every adapter output is validated against the canonical schema before
  it can reach storage.
- L1.3: no adapter call path exists that skips the Compliance Agent.

**L2 — Integrity Agent (runtime)**
- L2.1: Compliance Agent actually ran and logged its decision for every fetch
  (not just available — invoked).
- L2.2: dedup state prevents the same job_id from alerting twice.
- L2.3: no raw personal data fields appear anywhere in storage (schema-checked).

**L3 — Functional Validation Agent**
- L3.1: end-to-end run against the sandbox fixture set (below) produces
  expected new/duplicate/filtered counts.
- L3.2: never run against real companies' live sites during automated tests.

A change isn't "done" until all three layers pass, plus the regression gate.

## 4a. Scale strategy — maximum feasible company coverage

Target is the largest realistic company list, not a small curated set.
Sourcing strategy, largest-yield first:

1. **ATS-native company directories** — Greenhouse, Lever, and Comeet each
   have ways to enumerate boards using their platform (public job boards,
   "powered by X" footprints). Harvesting company slugs from these is the
   highest-yield, lowest-effort source since it comes with a working adapter
   for free.
2. **Public Israeli tech company registries** — Start-Up Nation Finder, IVC
   Online, geektime/calcalist company lists, and similar directories, to
   build the company -> career-page-URL mapping at scale.
3. **ATS auto-detection on unknowns** — for any company whose career page URL
   is known but ATS is not, fetch the page once and pattern-match against
   known ATS fingerprints (script tags, API calls visible in page source,
   URL structure) to assign it automatically instead of manually.
4. Companies with no detectable ATS and a fully custom career page go in a
   lower-priority "custom scraper" bucket, handled by `CustomAdapter`
   (Session 6) — config-driven via `custom_selectors.json`, not a bespoke
   Python subclass per company. Onboarding a new company here means adding
   a config entry (career page URL, which `<script id="...">` tag to parse
   as JSON, which key holds the positions list, field name mapping) *only
   if it shares a rendering pattern `CustomAdapter` already knows how to
   read* (confirmed for monday.com: server-rendered HTML with a JSON data-
   hydration blob, no JS execution needed — see §1's Session 6 note). A
   company using a genuinely different pattern, or one that truly requires
   executing JavaScript, needs either a new extraction strategy added to
   `CustomAdapter` or a real headless-browser decision — still real
   per-company effort in those cases, just less of it than a full bespoke
   adapter class every time.

The Compliance Agent (§6) still gates every fetch regardless of list size —
scale changes the size of `companies.json`, not the safety rules.

## 5. Sandbox (domain-specific hook #1)

A fixed set of 3–5 test companies with cached fixture responses (saved JSON/HTML
snapshots) checked into `tests/fixtures/`. All automated tests run against
fixtures only. Live-site testing is manual, rate-limited, and opt-in per run.

## 6. Non-negotiable safety gate (domain-specific hook #2)

**Compliance Agent.** Before any live fetch:
- robots.txt for the target domain is fetched and honored (no disallowed paths).
- A per-domain rate limit / delay is enforced.
- No CAPTCHA or bot-detection bypass, ever.
- Only public job-posting metadata is stored — no candidate PII, no scraping of
  application forms, no login-walled content.

This gate cannot be disabled by a task prompt, a "just for testing" request, or
an emotional/urgency framing. Any change to it requires its own ADR.

## 7. Regression gate (checklist, expand as needed)

1. Compliance Agent runs before every live crawl. No exceptions.
2. Dedup never re-alerts on the same job_id.
3. Adapter output always conforms to the canonical schema before storage.
4. Keyword filter matches both English and Hebrew terms.
5. No personal/candidate data fields ever populated in storage.

## 8. Agent roster

| Agent | Dev-time / Runtime | AI or deterministic |
|---|---|---|
| Regression Guard | Dev-time | Deterministic |
| Security/Secrets scan (no leaked API keys/tokens in repo) | Dev-time | Deterministic |
| Crawler / ATS Adapter | Runtime | Deterministic |
| Normalizer | Runtime | Deterministic |
| Compliance Agent | Runtime | Deterministic |
| Dedup/Diff Agent | Runtime | Deterministic |
| Keyword Filter Agent | Runtime | Deterministic |
| LinkedIn Cross-Reference Agent (later) | Runtime | Deterministic (API-based, not AI) |
| Notifier Agent | Runtime | Deterministic |

**Default stance:** all agents are deterministic, no AI calls, no data sent
off-device beyond fetching public job pages. If an AI-powered agent is ever
proposed (e.g. an LLM-based role classifier instead of keyword matching), it is
a separate, explicitly approved exception — logged as its own ADR — not a
default.

## 9a. Deployment architecture (ADR-0009, ADR-0010, ADR-0012, ADR-0013, ADR-0028, ADR-0029)

```
GitHub Actions (frequent cheap check-in + manual "Run now" button)
   -> gate-check (schedule/gate.py, ADR-0028) decides: run a full scan, or
        exit near-instantly?
   -> if yes: runs the full pipeline (§1-4, Session 8's run.py)
   -> commits shared scan results (JSON/SQLite, plus pwa/latest_scan.json +
        pwa/usage_summary.json — Session 15/14) back to the repo
   -> that push also triggers a Cloudflare redeploy (Git-integration,
        ADR-0029), re-snapshotting pwa/ — this is what refreshes the
        *deployed* PWA's data, not a separate mechanism
   -> triggers Cloudflare Worker: "new matches found" -> Worker sends
        Web Push to every subscribed device (ADR-0012)

PWA (installed on laptop and/or Android phone, ADR-0013; served by
Cloudflare Workers with Static Assets, ADR-0029 — see below)
   -> fetches latest_scan.json + usage_summary.json (same origin, both
        inside pwa/, Session 15)
   -> applies THIS DEVICE's local role/tag filters (stored locally, never
        synced — ADR-0014) [not built yet — deferred to a later session]
   -> renders new vs still_open, dark/light theme
   -> registers for Web Push once; subscription sent to the Cloudflare
        Worker so this device receives alerts [not built yet]
```

Nothing here needs the laptop or phone to be on for the *scan* to run —
compute lives entirely in GitHub Actions. Each device is a client with its
own local state; there is no shared account or backend user record.

**Cron cadence vs. real schedule — easy to get backwards (ADR-0028,
Session 9):** `.github/workflows/scan.yml`'s registered `schedule:` cron
(`0 * * * *`, hourly) is a cheap, fixed CHECK-IN cadence, not the actual
scan frequency. Every check-in calls `schedule/gate.py`'s
`should_run_full_scan()`, which reads `schedule_config.json` (`mode`,
`scans_per_day`, `times_utc`) to decide whether *this specific check-in*
should run a real scan or exit at near-zero cost. Changing how often real
scans happen means editing `schedule_config.json`'s values, never the
workflow file's cron expression — the whole point of ADR-0028 is that
scan frequency becomes a safely-editable config value instead of
something requiring a commit to the workflow itself. A `workflow_dispatch`
manual trigger always runs a full scan regardless of `schedule_config.json`,
since that's explicit human intent, not a check-in.

**`schedule_config.json`'s default mode is `"on_demand"` (Session 10):**
scheduling exists as a switchable option, not something active by
default — `scans_per_day`/`times_utc` stay in the file, inactive but
ready, for whenever it's switched back to `"scheduled"`. Until then, the
scan only ever runs via the manual `workflow_dispatch` button.

**Scan-step timeout and what a kill actually does to stored data (Session
10):** the "Run scan" step in `.github/workflows/scan.yml` has
`timeout-minutes: 20` — a safety cap, not a tuning target (today's 7-company
scan finishes in seconds; this matters once the company list grows and a
hang or a slow/unresponsive company shouldn't be able to burn the free-tier
Actions-minute budget indefinitely). Confirmed, deliberate answer to what
happens if it fires: **nothing partial gets saved, and nothing partial
*can* get saved with `run.py`'s current design.** `run.py`'s `run()`
fetches every company concurrently via a single `asyncio.gather(...)` call,
and only calls `upsert_jobs()`/`record_scan_run()` once, after that whole
call returns. If the step is killed mid-fetch, execution never reaches
that point at all — `scan_results.db` and `usage_log.json` are left
byte-for-byte as they were before the step ran, not partially written.
Separately, GitHub Actions' own step semantics mean the following "Commit
and push" step would be skipped anyway on a timeout: an `if:` condition
without an explicit status-check function (`always()`, `failure()`, etc.)
implicitly requires `success()` too, and a timed-out step counts as failed.
So today, a timeout kill means a clean no-op — the repo is left exactly as
the last successful run left it, and the only lost work is that run's own
progress, not any prior state. This was an explicit design confirmation,
not a change made this session: making partial progress survive a timeout
would need `run.py` to persist incrementally (e.g. per-company, as each
`fetch_company()` call resolves, rather than once at the end) — a real
change to `run.py`'s structure, flagged here as a possible future session,
not built now.

**`latest_scan.json` and `usage_summary.json` (Session 14):** the two
concrete, plain-JSON files this section's PWA diagram describes fetching —
built now, before the PWA itself, since both are pure "compute a summary
from data that already exists" work with no GUI dependency.
`latest_scan.json` is `run.py`'s existing match data reshaped flat
(`generated_at`, `companies_attempted/succeeded/failed`, `matches` —
each with company/title/location/role_category/source_url/scan_status,
no `job_id`/`matched_tag`/internal timestamps, and never
`application_status`, per ADR-0011/ADR-0014). `usage_summary.json` is
`usage/budget.py`'s `compute_usage_summary()` output
(`minutes_used_this_month`, `minutes_cap`, `percent_used` — deliberately
not clamped at 100, since going over the cap is the useful signal, not an
error to hide). Both are rewritten on every real `run.py` execution, not
cached — during a stretch of the workflow's gate-check-only skips
(ADR-0028), neither file changes at all, since `run.py` never runs; the
next real run recomputes both fresh.

**Real gap in the budget calculator, checked not assumed (Session 14):**
`usage_log.json` today only ever gets an entry from `record_scan_run()`,
which only runs when `run.py` runs, which only happens when the workflow's
gate-check says yes. The hourly cheap check-in's own cost (ADR-0028's own
disclosed line item — real Actions minutes, just not logged anywhere) is
NOT included in `minutes_used_this_month` — not because it's filtered out,
but because nothing in this codebase writes it. `usage_summary.json`
surfaces this honestly via `"includes_checkin_overhead": false` rather
than folding in an estimated number. If a future session makes the
gate-check log a small entry on every skip too, `compute_usage_summary()`
needs no code change at all — it would just start summing genuinely
complete data.

**The first real PWA (Session 15) — read-only, `pwa/` as the deployment
root:** `pwa/` holds the entire deployed site (`index.html`, `styles.css`,
`app.js`, `service-worker.js`, `manifest.json`, icons/mascot art) —
`wrangler.jsonc`'s `assets.directory` points at it. `latest_scan.json` and
`usage_summary.json` were moved here from the repo root (where Session 14
originally put them, still uncommitted at the time) specifically because
only files inside `assets.directory` are ever reachable on the deployed
site — nothing else in the repo is servable over HTTP once deployed. This
session is deliberately read-only: real data rendered correctly (company
counts, matches grouped new/still_open with working Apply links, the real
`percent_used` budget bar), no interactivity yet — role selection, "mark
as applied," theme persistence, Web Push registration, and the manual-
trigger button are all explicitly deferred to a later session, so this one
only had to get "fetch real JSON, render it correctly" right.

**Doc/reality gap, flagged not silently resolved (Session 15):** the task
for this session referenced ADR-0029 ("Cloudflare Pages + Access, not
GitHub Pages") — it does not exist in `DECISIONS.md`, which still ends at
ADR-0028. Same recurring pattern already flagged in Sessions 9, 11, and
13's handoffs (a planning-side decision described in a task prompt that
never actually landed in the repo before the task referencing it was
sent). Proceeded using the task's own description of what ADR-0029
supposedly decided (Cloudflare Workers with Static Assets via Git
integration, Cloudflare Access restricting the live site to Elad's email)
since that was unambiguous enough to build against — but the ADR itself
should get written for real, not just referenced.

**No `demo.html` found to match (Session 15):** the task asked this
session's visual design to match `demo.html`'s "dark radar theme,
sonar-corner mascot widget, job cards with new/still_open badges" — no
such file exists anywhere in this repo (checked directly, not assumed).
Built from that same text description plus the real `mascot.png`/
`batPoses.png` art already in the repo instead of blocking on a missing
reference. If `demo.html` exists somewhere outside this repo (e.g. a
chat-session artifact never committed), it's worth committing it here so
future sessions have the actual reference rather than a secondhand
description of one.

**Visual fixes against the real `demo.html` spec (Session 17):** Elad saw
the deployed PWA and flagged two mismatches against the actual original
design (which still never made it into this repo — this session worked
from exact CSS/HTML given directly in the task, not the file itself).
Wordmark: `.wordmark`/`.wordmark span` now match the given spec exactly
(JetBrains Mono 700 20px, -0.5px letter-spacing, the "Scanner" half
colored via a `--teal` variable) — `--teal` itself is aliased to the
existing `--radar-green` accent already used everywhere else in the UI,
since the original's exact hex isn't available without `demo.html`
itself; flagged as a judgment call, not a confirmed match. Role tags: job
cards now show `roles.json`'s `label_en` ("DevOps Engineer") instead of
the raw `role_category` key ("devops") — `run.py`'s `build_summary()`
resolves this server-side (a new `_role_label()` helper, fail-safe to the
raw key if a category's `label_en` is ever missing) and carries it
through to `latest_scan.json` as a `label_en` field alongside
`role_category`, rather than having `app.js` fetch `roles.json` itself —
that would have meant duplicating `roles.json` into `pwa/` the same way
Session 15 deliberately avoided duplicating the scan/usage exports.

## 10. Local-only preferences and application status (ADR-0011, ADR-0014)

Two things are **never** written back to the shared repo or any backend —
they live only in the device's local storage (IndexedDB/localStorage):

- Which role categories/tags this device is filtering on.
- `application_status` (`not_applied`/`applied`) per job, set by tapping
  "mark as applied" in the app.

This is what makes the app safely multi-install: anyone who installs it
gets their own independent local state, with no possibility of one
install's filters or applied-marks affecting another's, and no login or
per-user backend required.

## 11. Push notifications (ADR-0012)

```
PWA (first launch) --requests notification permission-->
   --registers Web Push subscription--> Cloudflare Worker (stores it, free tier KV)

GitHub Actions scan finds new matches
   --calls Worker--> Worker sends Web Push to every stored subscription
   --arrives as a native-feeling notification on each subscribed device
```

No third-party messaging account (Telegram, etc.) is required — Web Push is
built into Android/Chrome and is free.

## 12. Environment hygiene

(To be filled in as friction is discovered — e.g. Python version, OS quirks,
encoding issues. Bake in as standing rules the first time something bites.)

## 13. usage_log.py module placement (resolved, Session 4 follow-up)
Flagged in Session 4's handoff as not fitting any existing module boundary
(`adapters/`, `core/`, `compliance/`, `storage/`). Resolved: it gets its own
module, `usage/`, parallel to the others — scan-run telemetry (ADR-0022) is
a distinct concern from `storage/` (job-posting data, scoped by ADR-0003).
Keeping them separate also means `usage/`'s eventual reader/projection
logic can't accidentally end up reasoning about job data, and vice versa.

Implemented Session 5: code moved from the root-level `usage_log.py` into
`usage/log.py` (re-exported via `usage/__init__.py`, same pattern as
`compliance/__init__.py`). `usage_log.json` — the data file itself — still
lives at the repo root, unchanged; only the module code moved.
