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
- `discovery/` (Session 21, ADR-0031) — Playwright-based ATS discovery
  for onboarding/harvesting sessions only. Never imported by `run.py`,
  `adapters/`, or the GitHub Actions workflow — the production scan
  pipeline stays on plain `httpx` (ADR-0001/ADR-0021). Depends on
  `compliance/` (reuses `ComplianceAgent.gate()`, never duplicates its
  robots.txt/rate-limit logic) but nothing in `compliance/`, `adapters/`,
  or `run.py` depends on `discovery/` — the dependency direction only
  ever points one way, same rule as `core/` never importing `adapters/`.
  Its one real dependency, Playwright, lives in `requirements-discovery.txt`
  (a separate file, not `requirements.txt`), on purpose: `requirements.txt`
  is what the GitHub Actions workflow installs for the production scan
  every run, and Playwright drags in a real Chromium binary (~100-300MB)
  that pipeline has no reason to ever download.

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

**Session 18 — harvesting toward a real ~5-minute scan, real result short
of the target:** Elad wanted a genuine test of ADR-0021's concurrency
payoff: since every Greenhouse company shares one domain
(`boards-api.greenhouse.io`), and ADR-0002's 1.5s per-domain rate limit
applies per-domain not per-company, a Greenhouse-heavy company list's
*count* is the actual pacing floor — roughly 200 Greenhouse companies
would cost ~5 minutes purely from that spacing, while Lever/Comeet/
custom-domain companies added on top cost almost nothing extra (different
domains run concurrently, not stacked after). Sourced ~330 candidate
Israeli-relevant company names (source #2 in this section's own list:
Wikipedia's companies-of-Israel/cybersecurity-industry pages,
failory.com's Israel startup list, general knowledge of the ecosystem),
then live-verified each candidate's *guessed* slug — not a slug taken
from a directory — against the real `boards-api.greenhouse.io`/
`api.lever.co` APIs through the real `ComplianceAgent`, honoring
robots.txt and the rate limit throughout (421 Greenhouse + 428 Lever
calls total, disclosed per ADR-0019). Real yield: 34 new Greenhouse + 4
new Lever companies (many well-known real Israeli tech companies
genuinely aren't on Greenhouse/Lever at all — Workday, Ashby, SmartRecruiters,
or fully custom career pages instead — confirmed empirically per company,
not assumed). `companies.json` grew from 9 to 47, well short of the ~200
Greenhouse target — reported honestly rather than rounded up, per this
session's own task brief. Three technically-successful slug guesses
(`shield`, `bold`, `vim`) were manually reviewed and rejected: each
returned a real 200 OK with exactly one posting and zero Israel signal
(e.g. "Copy of Avenger" in Beijing for `shield`) — a resolving slug isn't
proof it resolved to the *intended* company, and a generic one-word slug
is exactly where that risk concentrates. The real live-run timing (§9a)
confirms rather than disproves the underlying reasoning — it just shows
the pacing floor at 36 real Greenhouse companies instead of 200.

**Session 19 — inverting the method: domain-first discovery instead of
slug-guessing.** Session 18's slug-guessing approach worked but carried
a real identity risk (3 collisions caught only by manual review) and a
hard ceiling (a company simply isn't found if its real slug doesn't
match any guessed variant). This session instead fetched each
candidate's own real career page — through the Compliance Agent, same
as every fetch in this project — and read the actual ATS straight off of
it: a redirect `Location` header, or an embedded `job-boards.greenhouse.io`/
`jobs.lever.co`/`comeet.com` link in the page's own HTML. Only once a
slug (and, for Comeet, its numeric `uid`) was observed this way did a
second confirmation fetch validate it against the real ATS API — the
same final check Session 18 used, but now applied to an observed slug,
not a guessed one, which is what makes the collision risk structurally
harder to hit (the slug came from the company's own real link, not from
a name transformation that happens to also match someone else's board).
**Real bug, caught mid-session:** the first pass returned only 4 hits
from 505 candidates, which turned out to be a bug, not a true result —
`ComplianceAgent.fetch()`'s `response.raise_for_status()` call raises
`HTTPStatusError` for *any* unfollowed 3xx (httpx.AsyncClient defaults to
`follow_redirects=False`, and httpx treats an unresolved redirect as an
error condition, not just 4xx/5xx), and the discovery script's exception
handling was silently discarding that — including the exact "`/careers`
redirects straight to the real board" signal this method exists to read.
Fixed by catching `HTTPStatusError` specifically and reading `Location`
off the exception's own `.response`, plus chasing one non-ATS redirect
hop (e.g. a bare domain bouncing to its `www.` form) before giving up;
re-running raised real hits from 4 to 13. **Real yield, honestly not
higher on Greenhouse specifically:** 1 new Greenhouse (`K Health`, whose
slug `khealthcareers` is exactly the kind of non-obvious form Session
18's guessing would have missed) + 10 new Comeet companies, each with an
exact slug+`uid` pair read directly off its own page — fully resolving
Session 18's stated Comeet blocker (a `uid` genuinely can't be guessed,
but it's sitting right there in the company's own real career-page URL).
companies.json: 47 -> 58 (Greenhouse: 37 -> 38). Diagnosed, not just
reported: most candidates' real `/careers` pages are client-rendered
SPAs whose ATS integration happens via a post-load JS `fetch()` call,
which never appears in a plain HTTP GET's HTML — the exact limitation
already flagged as a caveat in Session 6 ("a page that truly builds its
job list client-side after load would fail this same check"), now
observed at real scale (505 candidates) rather than as a single
hypothetical company. This method's actual payoff wasn't a higher
Greenhouse hit rate — it was zero identity collisions (vs. Session 18's
3) and unlocking Comeet entirely.

**Session 20 — same method, a research-sourced candidate list instead
of a self-compiled one.** Elad/planning-Claude supplied ~182 real,
currently-active Israeli company names directly (Calcalist/CTech's 2026
funding-rounds coverage + StartupBlink's Israel ranking), explicitly
flagging the same collision risk Session 18 hit (several
generic-English-word names — `Above`, `Bold`, `Neo`, `Frame`, `Willow`,
`Swan`, `Onyx`...). Ran unchanged through Session 19's domain-first
discovery script against this different list: no new bugs, confirming
the redirect-chase fix generalizes rather than being a one-list fluke.
8 raw hits, 7 confirmed (`Slice` resolved to a Greenhouse *embed-script*
path, not a real company slug — correctly dropped when the confirmation
fetch found no real jobs behind it, a clean example of Stage B doing
its job). Of the 7 confirmed, 2 were rejected on manual review before
touching `companies.json`: `Enigma` resolved to a real, unrelated NYC
data company (zero Israel signal across 9 postings) — almost certainly
the exact generic-word collision this session was warned about, not the
Israeli company the funding-rounds coverage actually meant; `CopilotKit`
resolved to a real Lever board but its one open role also carried zero
Israel signal, and identity wasn't confirmed strongly enough to include
on a resolving-slug-plus-guess alone. Net: 5 new companies (Guardio,
Guidde, ScaleOps, Zeroport, ZyG), each confirmed via a real,
Israel-located posting, not just a resolving slug. `companies.json`:
58 -> 63 (Greenhouse: 38 -> 40). Real, repeatable lesson across three
sessions now: the bottleneck isn't the candidate list's quality
(guessed names, a dated directory, and real funding-round coverage all
landed in a similar single-digit-percent range) — it's that most real
companies' career pages are client-rendered and don't expose their ATS
to a plain HTTP GET at all, the limitation flagged since Session 6.

**Session 21 — testing whether a real browser actually fixes it (ADR-0031):**
Built `discovery/playwright_probe.py` (`PlaywrightProbe`, a headless
Chromium wrapper) to test the Sessions 18-20 hypothesis directly rather
than assume it and scale up blind. Every page load routes through
`ComplianceAgent.gate()` — a new context manager extracted from
`fetch()` (see §6) so Playwright gets the exact same robots.txt/rate-
limit discipline as every `httpx` call in this project, without
duplicating any of that logic. Re-tested 20 specific companies pulled
directly from Sessions 19/20's own "no ATS link found" logs (not a
fresh guess) — real result: **0 new ATS signals found.** 3 of the 20
(BlazeMeter, Aidoc, Centrical) are genuinely, currently blocked by
their own real robots.txt (confirmed via a fresh, uncached compliance
check) — Playwright correctly respected that, proving the compliance-
reuse goal worked, but meaning those 3 were never actually inspected by
a browser at all. One (MorphiSec) surfaced a real, separate finding: a
persisted `robots_cache.json` entry said "disallowed" when the live
robots.txt (re-checked directly, no Disallow rules for `User-agent: *`)
says otherwise — most likely a transient bot-protection response at
the original check time, now resolved; corrected in the cache, and
Playwright still found nothing there either once genuinely inspected.
The remaining 16 were cleanly, fully inspected (network-idle wait, full
rendered DOM, every observed network request) and came back with zero
ATS signal every time. Honest conclusion: for *this* specific batch,
JS-rendering was not the actual blocker — these companies most likely
use an ATS outside this project's four supported platforms entirely
(Workday, SmartRecruiters, iCIMS, a blocked Ashby, or a fully bespoke
backend), a different, non-Playwright-solvable problem. This is a real
negative result, not a failed session: it means scaling Playwright
discovery up to the full ~500+ candidate pool is **not** recommended
without first finding at least one genuine positive-control case (a
company independently known to expose an ATS only after JS execution)
to confirm the mechanism actually pays off somewhere real, rather than
spending a large batch of exploratory calls chasing the same negative
result at scale.

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

**`ComplianceAgent.gate(url)` (Session 21, ADR-0031):** an async context
manager extracted out of `fetch()` — robots.txt check, rate-limit wait,
and the domain-lock/timestamp-recording sequence, with no httpx call
baked in. `fetch()` itself is now just this gate wrapped around one
httpx `GET`. Exists so a *different* fetch mechanism (a Playwright page
load, for discovery sessions — see `discovery/playwright_probe.py`)
gets identical compliance discipline without reimplementing any of it.
The gate raises `ComplianceError` before the caller's block ever runs
if robots.txt disallows the URL, and only records the domain's
completion timestamp after the caller's block returns normally —
preserving `fetch()`'s original ordering exactly (a failed fetch inside
the block still doesn't count toward the next rate-limit check, same
as before this refactor).

**Robots-cache staleness, fixed after a real incident (Session 22):**
Session 21's MorphiSec re-check found a real, live bug: a persisted
`robots_cache.json` entry said `allowed: false` when a fresh live check
of morphisec.com's actual `robots.txt` (no `Disallow` rules for
`User-agent: *` at all) said otherwise — most likely a transient
bot-protection response at whatever moment that entry got cached. Under
the original 7-day TTL, a single bad moment could silently skip a real
company's entire scan for a full week with zero visible symptom. Fixed
two ways, both landing on the same asymmetry — a wrong `allowed: true`
costs nothing (we just fetch, which is always safe) but a wrong
`allowed: false` silently costs real coverage:
1. **Asymmetric TTL.** `allowed: true` keeps the original 7-day trust
   window (`ROBOTS_CACHE_TTL_SECONDS`). `allowed: false` now gets a
   1-hour window instead (`ROBOTS_CACHE_BLOCKED_TTL_SECONDS`) — a bad
   "blocked" call self-heals within the hour instead of the week,
   while a domain that's genuinely, persistently blocked still doesn't
   get re-checked on every single fetch.
2. **Double-check before trusting a fresh "blocked" result.**
   `_is_allowed()` no longer caches a disallowed result off a single
   live check — it waits `blocked_recheck_delay_seconds` (5s by
   default) and checks once more; only two agreeing "disallowed"
   results get persisted as `false`. A one-time glitch essentially
   never repeats a few seconds later; a genuine `Disallow` rule always
   does, since real robots.txt content doesn't change on that
   timescale.

Live re-verification, not just unit tests: re-checked morphisec.com
from a completely fresh cache under the new logic — resolved to
`allowed: true` on the very first live check (the double-check path
never even had to trigger, since this check wasn't blocked to begin
with), consistent with the original block having been a one-off
glitch rather than a persistent, reproducible block.

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

**`failures` list alongside `companies_failed` (Session 18):** the console
summary and `latest_scan.json` both used to reduce every failure down to a
bare count — real, but with no visibility into *why* a company failed
short of digging through the GitHub Actions log, which Elad flagged as a
genuine gap. `print_summary()` now prints `[Company] FAILED — <real
error>` per failure, and `build_latest_scan_export()` carries a
`failures: [{company, error}]` list in `latest_scan.json` alongside the
existing `companies_failed` count (kept as a stable summary number for
existing UI, not removed) — a future PWA view can show the real
diagnostic text without needing the count to also become a list.

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

**Mascot: the real root cause, and two more real gaps found while fixing
it (Session 23):** Elad reported the mascot "still not what I wanted"
after Session 17. Root cause, confirmed by planning-Claude directly
against the actual `demo.html` (which Elad has decided will never be
committed here): Session 15 never had that file, so instead of the real
design — one single static photo — it invented a different one: a
4-frame flap-cycling animation (`bat-frame-1..4.png`, cropped from
`batPoses.png` via Pillow, swapped every 500ms via `setInterval`). Not
a smaller mismatch like the wordmark/teal color — a structurally
different mechanism. Removed entirely: `app.js`'s
`initMascotAnimation()`, the four frame PNGs, `mascot-widget.png`, and
their `service-worker.js` cache entries (cache name bumped so old
cached frames actually evict, not just stop being referenced).
`index.html`'s mascot `<img>` now points at `real_mascot.png` — a
single static image, no JS hook. `batPoses.png` itself (the root-level
source, outside `pwa/`) is confirmed unreferenced anywhere else via a
full-repo grep; left on disk rather than deleted, since only its
generated derivatives were in scope.

Two real blockers surfaced doing this, neither guessed past: (1)
`real_mascot.png` was never actually placed anywhere on disk this
session despite being described as already provided — the code now
references the correct filename, but the file itself is still missing,
so the widget will show a broken image until it's placed in `pwa/`.
(2) The task described a 5-element radar structure (`.radar-screen`,
`.range-ring` ×3, `.crosshair`, `.sweep-bg`, `.pct-badge`) as already
built in this widget — it isn't; this repo's actual `styles.css` only
ever had a single `.ping-ring`, and the task's "200px badge" sizing
claim doesn't match the real 84px/64px either (Session 17 never
touched mascot sizing). Left both unchanged rather than inventing a
radar structure from a text description alone — doing that would risk
exactly the "guessed instead of using the real design" failure mode
this session exists to correct.

**Mascot: both real blockers resolved with real values (Session 24):**
`real_mascot.png` was placed at `pwa/real_mascot.png` and verified
directly — 480×320, RGBA with real alpha transparency, loads correctly.
The `.mascot-widget`/`.ping-ring` guess was replaced entirely with the
exact `.sonar-corner` structure from the real reference file, given
verbatim (the same successful pattern as Session 17's wordmark fix and
Session 19's `--teal` values): `.radar-screen` (radial-gradient disc),
three `.range-ring` elements, a `.crosshair` (via `::before`/`::after`),
the rotating `.sweep-bg` (conic-gradient, 3s linear infinite,
`mix-blend-mode: screen`), the mascot `<img>`, and a `.pct-badge`
showing a literal `?%` placeholder (the real percentage needs the
usage-budget calculator wired into the PWA, which doesn't exist yet —
separate, explicitly out-of-scope future work). The container was
renamed from `.mascot-widget` to `.sonar-corner` to match the real
reference exactly, rather than keeping the old name — one less layer
of naming drift between this file and the actual source design going
forward. Verified element-by-element via `getComputedStyle` (not visual
inspection): every position/inset/size/color/animation value on all
eight elements/pseudo-elements matches the given spec exactly. The old
`.ping-ring`/`.mascot-widget`/`@keyframes ping` are fully removed —
confirmed via a full `pwa/` grep, zero remaining references outside
historical comments. The given `onclick="showView('stats', ...)"` was
kept verbatim as instructed; `showView()` and the tabs system it
targets don't exist in this codebase yet, so clicking the mascot
currently logs a harmless console error rather than doing anything —
flagged, not silently dropped, same treatment as the `pct-badge`
placeholder.

**Mascot: `.pct-badge` and the broken `onclick` removed (Sessions
25/26):** Session 25 (investigation only) confirmed Elad's on-screen
"is this one thing or two" question resolves to two unrelated things:
`.budget-widget` (Session 15, untouched, fully working — a real
`renderBudget()` call renders a real `percent_used` from
`usage_summary.json`) and `.pct-badge` (Session 24's literal `?%`
placeholder on the mascot, never wired to any data or function). Since
the real number already displays correctly elsewhere, Elad's call was
to remove the badge rather than wire it up — Session 26 deleted
`.pct-badge` from both `index.html` and `styles.css` entirely, and
removed the `onclick="showView(...)"` attribute alongside it (Session
25 re-confirmed `showView()`/`.tab` still don't exist anywhere in this
codebase, and none are planned). `.sonar-corner`'s `cursor: pointer`
came out too, since nothing is clickable there anymore. `.sonar-corner`
is now purely decorative: `.radar-screen`, three `.range-ring`s, the
`.crosshair`, the rotating `.sweep-bg`, and the mascot image — no badge,
no click handler. Verified live: the element genuinely doesn't exist in
the DOM, the `onclick` attribute is `null`, clicking produces no new
console error, and `.budget-widget`'s real data is completely
unaffected.

**Real live-run timing at 47 companies (Session 18):** ~80 seconds real
elapsed, not the ~5-minute target — see §4a for the honest shortfall in
how many companies actually got harvested/verified this session (36 real
Greenhouse companies, not ~200). The timing itself is exactly consistent
with ADR-0021's own reasoning, not a surprise: with the per-domain 1.5s
rate limit (ADR-0002) serializing every Greenhouse-domain call, ~36
Greenhouse companies costs ~54s of pure pacing, and the observed ~80s
includes real per-request response time on top of that (e.g. `NICE`
alone returned 293 open postings in one response). Lever's handful of
companies and Comeet's 2 ran concurrently on their own domain lanes and
added ~nothing to the critical path — the same cross-domain
non-blocking behavior Session 4's 4-company test first confirmed, now
visible at a slightly larger scale. Reaching the actual ~5-minute target
is a company-count problem (getting to ~200 real, verified Greenhouse
companies), not an architecture problem — the concurrency model already
does what it's supposed to.

**Real live-run timing at 58 companies (Session 19):** ~66 seconds real
elapsed, 0 failures. Slightly faster in wall-clock terms than Session
18's 47-company/~80s run despite having 11 more companies, because the
11 new companies are mostly Comeet (its own separate rate-limit lane,
running concurrently with Greenhouse's) rather than more Greenhouse —
direct empirical confirmation that it's Greenhouse-domain company count
specifically driving the pacing floor, not total company count. Still
well short of ~5 minutes, consistent with 38 real Greenhouse companies
today (target: ~200).

**Real live-run timing at 63 companies (Session 20):** ~97 seconds real
elapsed, 2 genuine transient `ReadTimeout`s (Cato Networks, Payoneer —
both real network hiccups, both visible with their actual error text in
`latest_scan.json`'s `failures` list, not just a bare count). Still
consistent with Greenhouse-domain company count being the real pacing
floor: 40 real Greenhouse companies now, still well short of ~200.

**Service worker: code-level fix (Session 27) then a real edge-caching
fix on top of it (Session 29).** Every deploy required a hard refresh
or incognito window to see changes — `service-worker.js`'s `install`
handler already called `self.skipWaiting()` (present since Session 15),
but `self.clients.claim()` in `activate` wasn't wrapped in its own
`event.waitUntil()`, so the browser could consider `activate` finished
before `clients.claim()` actually finished handing control of
already-open tabs to the new worker. Session 27 fixed that and bumped
`CACHE_NAME`, but Elad still needed a hard refresh afterward — pointing
at something upstream of the browser entirely, which a local dev server
structurally cannot reproduce (there's no CDN edge in front of
`python -m http.server`).

Session 29 confirmed that directly rather than assuming it: curled the
real deployed URL
(`https://thescanner.lanirelad.workers.dev/service-worker.js`) and
found `Cache-Control: public, max-age=0, must-revalidate` (Cloudflare
Workers' own documented default for static assets) *and*
`CF-Cache-Status: HIT` on the same response — Cloudflare's edge served
the file straight from its own cache without ever reaching the origin,
despite `max-age=0`. Confirmed this default isn't unique to
`service-worker.js` (`styles.css` shows the identical default+HIT
combination) — the platform's behavior isn't broken, it's just wrong
specifically for the one file whose entire purpose is detecting when
it's outdated. First tried `Cache-Control: no-cache` (the task's own
suggestion) but checked Cloudflare's documented semantics before
trusting it: `no-cache` still means "cache it at the edge, but
revalidate with origin before serving" — not strong enough to explain
away, or reliably prevent, the observed `HIT`. Switched to
`Cache-Control: no-store`, Cloudflare's actual documented directive for
skipping edge caching entirely, added via `pwa/_headers` (the
Workers-with-static-assets convention, confirmed via Cloudflare's own
docs to apply here since this deployment has no custom Worker script
intercepting responses) scoped to exactly `/service-worker.js` — every
other static asset keeps the normal cache-first behavior the PWA shell
actually wants.

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

**Implemented (Session 28):** both live in `pwa/preferences.js`, a file
with zero side effects on load — every function is a pure function or a
thin `localStorage` wrapper, no DOM access, no network — deliberately
separate from `app.js`, whose bottom section calls `main()` immediately
on script load and needs a real DOM/fetchable JSON to do it. Role
filters are stored as `{ [role_category]: false }` under
`thescanner:role_filters` — only explicit off-toggles are persisted,
since "on" is already the default (`isRoleEnabled` treats a missing key
as enabled). This is a pure client-side display filter on top of
`latest_scan.json`'s already-fetched matches — it never re-fetches,
never touches `roles.json`, and the available toggle set is derived
from the matches themselves (`availableRoleCategories`) rather than
`roles.json`, which is never duplicated into `pwa/` (same reasoning
Session 15 already established for the other JSON exports): every
match already only ever comes from a category `roles.json`'s own
`enabled` flag allowed through (`core/filters.py`, Session 11), so "no
stored preference yet" and "show everything the backend already
decided to include" are the same thing by construction, with no need
to know `roles.json`'s contents at all. `application_status` is stored
as `{ [job_id]: true }` under `thescanner:applied_jobs`, keyed by the
same `job_id` `core/schema.py` already computes (ADR-0026) — reusing
it rather than inventing a second ID scheme meant one small, explicitly
scoped exception to `build_latest_scan_export()`'s "no internal fields"
rule (see run.py's docstring). Both features use event delegation
(on `#role-filter-toggles` and `#job-groups`) rather than per-element
listeners, since both containers are rebuilt wholesale by every
`renderJobGroups()`/`renderRoleFilters()` call — a listener bound to
one specific checkbox or button would be silently lost on the very
next re-render otherwise.

**Testing `preferences.js` without Node.js (Session 28):** this
sandbox has no Node.js installed at all (checked directly — `node`/
`npm` are both absent), so there's no JS test runner available the way
`pytest` is for the Python side. Rather than skip real coverage for
genuinely-testable pure logic, `pwa/tests/preferences.test.html` is a
plain, dependency-free HTML+JS harness: it loads `preferences.js`
exactly the way `index.html` does and runs real assertions in an
actual browser — the environment this code actually runs in anyway —
with no build step or framework to install. Opening it directly (or
driving it headlessly) re-runs all of it; results print to the page
and the console. 23/23 real assertions pass, including full round-trips
through real `localStorage` and confirming the toggle functions don't
mutate their input arguments.

**Tri-state job status + a safe migration (Session 30):** extended
Session 28's plain applied/not-applied boolean into a real tri-state —
`not_set` / `applied` / `ignored`, mutually exclusive, enforced in
exactly one place (`setJobStatus`, which always fully replaces whatever
status was there before, so no code path can leave a job marked both
applied and ignored). Stored under a new key, `thescanner:job_status`
(values `"applied"`/`"ignored"`, absence means `not_set` — same
"don't persist the default state" reasoning as `ROLE_FILTERS_KEY`),
rather than overloading Session 28's `thescanner:applied_jobs` boolean
shape in place. This was a real decision, not a default: Elad has been
actively using the PWA since Session 28 shipped (he's the one who
reported Session 27's caching bug from real usage), so a clean break
risked silently discarding marks he'd already made — a real risk,
confirmed rather than assumed away. Chose migrate-on-read over a
one-time destructive migration: `loadJobStatuses()` merges the legacy
key's `true` entries in as `"applied"` on every call, only for a
job_id the new key has no opinion about yet — the legacy key is never
written to or deleted, so there's no window where a read could observe
a half-migrated state, and no data loss even if something goes wrong
partway. Ignored jobs are pulled out of their normal new/still_open
grouping by a new pure function, `partitionByIgnored(matches, statuses)`,
and rendered in their own "Ignored" section at the very bottom of the
list; applied jobs are deliberately **not** partitioned by this
function — they stay exactly where Session 28 already puts them, same
position and visual treatment, since only the *ignored* status changes
where a job is grouped. Verified live with a real seeded legacy entry
(not just the test harness): it renders as applied with zero
interaction on first load, correctly transitions straight to ignored
when the Ignore button is clicked (not both), correctly reverses, and
both the legacy key's original data and the new key's state survive a
real full page reload untouched. `pwa/tests/preferences.test.html`
grew from 23 to 38 real assertions, including five dedicated to the
migration behavior itself.

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
