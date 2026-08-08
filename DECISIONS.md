# DECISIONS.md — Architecture Decision Record

Append-only. Never edit or delete a past entry. To change a decision: add a new
ADR and mark the old one *Superseded by ADR-000X*.

---

### ADR-0001 — Prefer ATS JSON APIs over HTML scraping
**Status:** Accepted
**Context:** Most Israeli hi-tech companies use Greenhouse, Lever, or Comeet,
each with a reasonably stable structure and, for Greenhouse/Lever, a public
JSON API.
**Decision:** Build one adapter per known ATS platform, hitting JSON endpoints
where available. Fall back to HTML scraping (Playwright + BeautifulSoup) only
for companies with fully custom career pages.
**Why:** Far more reliable than HTML scraping at scale; less brittle to site
redesigns.

### ADR-0002 — Compliance Agent is non-negotiable
**Status:** Accepted
**Context:** Scraping company sites at scale risks violating robots.txt, rate
limits, or ToS, and risks the appearance of hostile traffic.
**Decision:** Every fetch, from every adapter, passes through a Compliance
Agent that checks robots.txt and enforces a per-domain rate limit. This cannot
be bypassed, including "just for a quick test."
**Why:** Protects Elad legally and reputationally; keeps the tool sustainable
long-term (a company that IP-bans the scanner is a company you've lost access
to permanently).

### ADR-0003 — No personal/candidate data is ever stored
**Status:** Accepted
**Context:** The tool only needs to know what roles exist, not who applies.
**Decision:** Canonical schema stores only public job-posting metadata
(title, company, location, URL, timestamps). No login-walled content, no
application-form data, no PII of any kind.
**Why:** Removes an entire category of privacy/legal risk for a project with
no need to take it on.

### ADR-0004 — Commit/push approval boundary
**Status:** Accepted
**Decision:** Claude Code never commits or pushes on its own. Elad approves
each commit/push individually.
**Why:** Keeps a human decision point on every change that leaves the sandbox,
mirroring the MyCalib and Goblet of Operations projects.

### ADR-0005 — Default: no AI-powered agents
**Status:** Accepted
**Decision:** All agents (crawling, filtering, dedup, compliance, notify) are
deterministic by default — no LLM calls, no user/company data sent to any
third-party AI API. An AI-powered agent (e.g. LLM-based role classification)
is an explicit, separately-approved exception if ever proposed, not a default.
**Why:** Keeps the system simple, auditable, and avoids sending scraped
company data to external AI services without a deliberate decision to do so.

### ADR-0006 — Sandbox is fixture-based, not live
**Status:** Accepted
**Decision:** Automated tests run only against a fixed set of cached
fixture responses for 3–5 test companies, checked into `tests/fixtures/`.
Live-site runs are manual and opt-in.
**Why:** Prevents automated test runs from hammering real company servers or
tripping bot-detection during routine development.

### ADR-0007 — Roles and tags are config, not code
**Status:** Accepted
**Context:** Elad wants DevOps + technical support today, but role
terminology drifts constantly and other role categories may be added later.
**Decision:** All role categories and their matching keywords ("tags") live
in `roles.json`, in both English and Hebrew, editable without touching
adapter/filter code. See `ARCHITECTURE.md` §1a.
**Why:** Keyword drift (e.g. "SRE" vs "DevOps Engineer" vs "Platform
Engineer") is constant and language-dependent; hardcoding it would mean a
code change every time terminology shifts.

### ADR-0008 — Maximum feasible company coverage, not a curated shortlist
**Status:** Accepted
**Context:** Elad wants the largest scan possible, not the initially-proposed
30–50 company pilot list.
**Decision:** Target company coverage is "as many as can be sourced and
verified," built primarily by harvesting company slugs from ATS-native
directories (Greenhouse/Lever/Comeet) plus public Israeli tech company
registries, rather than hand-curating a small list. See `ARCHITECTURE.md`
§4a for the sourcing strategy.
**Why:** A hand-curated list of 30–50 defeats the point of catching roles
other tools miss — the value is in breadth. The Compliance Agent (ADR-0002)
is what keeps a large list safe, not a small list size.

### ADR-0009 — Deployment architecture: cloud-based, not laptop/phone-resident
**Status:** Accepted
**Context:** Elad wants TheScanner usable from both his laptop and Android
phone, for free, without either device needing to be on for scans to happen.
**Decision:**
- **Compute:** GitHub Actions scheduled workflow runs the scan — free tier
  (2,000 min/month private repo, unlimited if public), well within budget
  for twice-daily runs of ~1,500 companies (~15-30 min/run estimated).
- **Trigger:** both a `workflow_dispatch` manual button (usable from GitHub's
  UI/app on laptop or phone) and a `schedule` cron, twice daily — not hourly.
- **Storage:** scan results committed to the repo (JSON/SQLite), so history
  is versioned and free. This is shared data, same for any install of the app.
- **Client:** see ADR-0013 (PWA) for how this data actually gets viewed.
- **Alerts:** see ADR-0012 (Web Push) — superseded the original Telegram
  assumption below.
**Why:** Makes the tool device-independent rather than device-dependent —
solves "works on laptop and phone" more reliably than running locally on
either one, and every piece involved has a genuinely free tier.

### ADR-0010 — Scan frequency: twice daily, not hourly
**Status:** Accepted
**Decision:** Scheduled scans run twice per day (exact times TBD), not
hourly. Manual on-demand runs via the `workflow_dispatch` button are always
available on top of the schedule.
**Why:** Hourly was overkill for Elad's use case and would burn through
Actions minutes faster for no real benefit — job postings don't change fast
enough to need hourly checks, and a manual button covers "I want to check
right now."

### ADR-0011 — New-vs-seen tracking; application status is local-only
**Status:** Accepted
**Context:** Elad wants to see which roles are new since the last scan vs.
already shown, and wants to mark a job as "already applied" (CV sent). He
later clarified this is always single-user-per-install: if someone else
installs the app, their preferences live entirely on their own device, with
no shared account or sync between installs.
**Decision:**
- Every job record gets a per-scan status of `new` (first time seen this
  run) or `still_open` (seen in a prior scan, still posted) — derived from
  existing `first_seen_at`/`last_seen_at` fields on the **shared** scan data,
  same for every install.
- `application_status` (`not_applied`/`applied`) is stored **entirely on
  the device**, in local app storage (IndexedDB/localStorage) — never
  written back to the shared repo or any backend. It behaves exactly like
  role/tag preferences: personal, local, install-specific.
**Why:** Since it's always single-user-per-install (not shared accounts),
there's no reason for this to touch a backend at all — local storage is
simpler, free, and structurally prevents one install's data from ever
leaking into another's.

### ADR-0012 — Native push notifications via Web Push, not Telegram/ntfy
**Status:** Accepted (supersedes the Telegram assumption in ADR-0009)
**Context:** Elad initially considered Telegram, then reconsidered once the
app itself became a phone app — reasoning that the app can deliver its own
native-feeling alerts instead of routing through a third-party messaging
service.
**Decision:** The PWA registers for Web Push (the same free, built-in
mechanism real Android apps use — no third-party account). A Cloudflare
Worker (free tier) stores each device's push subscription and sends a push
notification directly to it after each scan finds new matches.
**Why:** Removes a third-party dependency (Telegram account, bot chat) in
favor of alerts that feel native to the phone, using an already-free,
already-planned piece of infrastructure (the Cloudflare Worker) instead of
adding a new one.

### ADR-0013 — Client: PWA, not a native app store build
**Status:** Accepted
**Context:** Elad wants it on both laptop and Android, free, with a nice
dark/light UI, and pointed out that since no company data beyond public
job-posting metadata is ever collected, there's no real security reason to
avoid a lightweight web-based app.
**Decision:** Build a Progressive Web App — installable to the Android home
screen, works as a normal browser tab on the laptop, supports Web Push
(ADR-0012), and follows/toggles dark/light mode. Not a React
Native/Flutter/native build.
**Why:** A native build would require a Google Play developer account
($25 one-time) and considerably more tooling for no real benefit here —
PWAs get installability, push notifications, and offline-capable caching
for free, which covers everything this app needs.

### ADR-0014 — Single-user-per-install, no multi-user backend
**Status:** Accepted
**Context:** Elad raised the concern that if someone else ever used the
app, shared preferences between users would be bad practice.
**Decision:** The app is always single-user *per install* — never a
shared multi-tenant backend with accounts. Anyone who installs the app gets
their own local preferences (roles/tags, application_status), stored only
on their device. There is no login, no per-user cloud storage, no
possibility of one install's local data affecting another's.
**Why:** Avoids building authentication and multi-tenant storage for a
problem that doesn't actually need a backend — local-only state on each
device is simpler, free, and structurally correct rather than merely
policy-correct.

### ADR-0015 — Direct application link on every job
**Status:** Accepted
**Decision:** Every job card in the app links directly to the original
posting (`source_url`) via a tappable "Apply" link. No content is copied,
mirrored, or reproduced from the source page.
**Why:** Gives Elad a one-tap path to the real application page, and keeps
the app firmly on the safe side of "link out" vs. "republish content."### ADR-0016 — Two-stage fetch; filter on location + title before fetching content
**Status:** Accepted
**Context:** Elad pointed out that fetching full job data for ~1,500
companies across all their open roles and countries is wasteful — many
target companies are multinational and post roles worldwide, not just in
Israel.
**Decision:**
- Every adapter fetch is **two-stage**: first pull the lightweight job list
  (title, department, location — no full description), which every ATS
  platform returns cheaply for all open roles at once. Only fetch the full
  description for a specific job if title + department + location don't
  already clearly resolve a match/reject.
- **Location is a first-class filter, same tier as role tags** — not
  something checked after storage. A new `locations.json` (or a `locations`
  block alongside `roles.json`) lists accepted locations in English and
  Hebrew, config-driven like roles. Non-matching-location roles are
  discarded at the lightweight-list stage, before any heavy fetch.
**Why:** Most of the "1,500 companies, all their roles, all countries"
cost was going to be wasted work — multinational companies post globally
under one career page, and the filtering fields (location, department,
title) are free in the initial response. Filtering early means less data
fetched, less stored, and a cleaner result set.

### ADR-0017 — Handoffs are a single plain-text fenced code block
**Status:** Accepted
**Context:** Elad wants to copy a full handoff with one click (the code
block's copy button), but the Session 1 handoff mixed markdown formatting
(bold, bullet asterisks) into the block, which breaks a clean one-click copy.
**Decision:** Every Claude Code handoff, from `=== BEGIN HANDOFF ===` to
`=== END HANDOFF ===`, must be wrapped in a single triple-backtick fenced
code block, in plain text — no `**bold**`, no markdown bullets, no nested
formatting inside the fence. Plain dashes/colons for structure only.
**Why:** A fenced block renders with a copy button in the chat UI; mixing
markdown into it defeats that and forces manual copy-paste.

### ADR-0018 — Code style: OOP where it fits, always commented, mobile-client-aware
**Status:** Accepted
**Context:** Elad wants the codebase to read as deliberate, professional
work — not something that "looks like junior work" — and wants Claude and
Claude Code held to the same standard. He also flagged that the client is
an Android app (PWA) *for now*, meaning code and data shapes should be
written with that consumer in mind even while only the Python backend
exists.
**Decision:**
- Use classes where the domain genuinely has objects with state and
  behavior (e.g. `ComplianceAgent`, an `Adapter` base class with
  per-platform subclasses like `GreenhouseAdapter`) — not OOP for its own
  sake, and not procedural code where a class would clarify responsibility
  boundaries.
- Every non-trivial function/class gets a docstring explaining *why*, not
  just *what* — inline comments are for non-obvious decisions (e.g. "why
  `content=true` is deliberately omitted here, see ADR-0016"), not restating
  the code.
- Data shapes (Stage 1/2 job dicts, the canonical schema) are written
  assuming a phone-app consumer: JSON-serializable, no server-side-only
  assumptions, field names/shapes stable enough that the PWA can consume
  them directly later.
**Why:** Keeps the codebase reviewable and consistent as scope grows past a
single adapter, and avoids having to retrofit structure later once the PWA
client starts consuming this data.

### ADR-0019 — Exploratory-call policy: permissive, bounded by compliance and cost
**Status:** Accepted
**Context:** Building adapters for a large, ATS-diverse company universe means
encountering unfamiliar/undocumented schemas repeatedly (Lever's schema
discovery in Session 3 being the first, not the last, example).
**Decision:** When facing a platform whose data shape isn't yet documented
in this repo, unlimited exploratory live calls are permitted — bounded only
by (1) every call still routes through the Compliance Agent (robots.txt +
rate limit, never bypassed), (2) staying within free-tier compute (no paid
API/service), and (3) the total call count being disclosed in the handoff.
There is no fixed numeric cap.
**Why:** At real scale, unfamiliar schemas will keep recurring. A few extra
safe, free, rate-limited requests to get a parser right the first time is a
better trade than guessing and needing a follow-up fix session.

### ADR-0020 — Two-track scanning: stable (frequent) vs. full-sweep (slow, complete universe), immediate notification
**Status:** Accepted
**Context:** The realistic addressable company universe is ~8,000-9,000
Israeli hi-tech companies (Elad's estimate) — far larger than the ~1,500
figure used for early time estimates. Scanning the full universe on the
same fast, frequent cadence as a small already-vetted subset isn't
practical, and job postings can appear/disappear within a single day, so
notification timing matters more than batching for calm.
**Decision:**
- **Stable track:** a vetted subset of companies, scanned frequently
  (twice daily default per ADR-0010, adjustable). Drives normal app
  updates.
- **Full-sweep/onboarding track:** covers the complete ~8-9k universe,
  run on a much slower cadence (e.g. monthly — exact frequency TBD),
  tolerant of taking hours since freshness pressure is lower for a
  first-pass discovery sweep. Newly-vetted companies graduate into the
  stable track afterward.
- **Notification: immediate, not batched.** Whenever either track
  completes and finds a genuine match, push fires right away — because a
  role published in the morning can be gone by evening, and waiting for
  the next scheduled cycle risks missing it entirely.
**Why:** Decouples "keep the small vetted set fresh" from "eventually cover
everything," without sacrificing responsiveness for either.

### ADR-0021 — Concurrency model: async/await, not threads+locks
**Status:** Accepted (supersedes the threads-per-domain-lock direction
discussed but never implemented in code)
**Context:** Early concurrency discussion assumed a small number of shared
ATS domains, where OS threads with a per-domain lock would comfortably
handle the load. Elad's clarification of the real scale (~8,000-9,000
companies, a monthly full-universe sweep) changes that: a meaningful share
of that universe likely runs custom, unique-domain career pages rather than
a shared ATS — potentially thousands of independent per-domain rate-limit
"lanes" needing to run concurrently for a full sweep to finish in a
reasonable window.
**Decision:** Build the Compliance Agent and all adapters on an async/await
foundation (e.g. `httpx.AsyncClient` or `aiohttp`) instead of
threads-with-locks. Async tasks carry far less memory/overhead per
concurrent "lane" than OS threads — decisive once concurrent per-domain
waits could number in the hundreds or thousands, not just dozens.
**Consequence:** Requires retrofitting `ComplianceAgent`, `GreenhouseAdapter`,
and `LeverAdapter` (Sessions 1-3) to async-compatible HTTP calls, and
converting the test suite to `pytest-asyncio` or equivalent. Real rework of
already-tested code, accepted now — before Comeet's adapter or
custom-domain scraping adds more code on top of the current synchronous
foundation, since retrofitting later means rewriting more surface area.
**Why:** Threads were the right call for proving correctness at 4 test
companies. The real target scale crosses the point where async's lower
per-task overhead is a genuine architectural advantage, not a theoretical
one.

### ADR-0022 — Scan-budget counter: self-tracked, not GitHub billing API
**Status:** Accepted
**Context:** Elad wants visibility into how much of the free Actions-minute
budget scans are consuming, and a projection of what a given
frequency/scale choice would cost monthly — before committing to a
schedule that risks the free tier.
**Decision:** Each scan run records its own wall-clock duration into a
small running log (`usage_log.json`, committed like the scan results
themselves) rather than querying GitHub's billing API. The app computes
monthly-used-minutes and percent-of-free-budget from this self-tracked
log, and projects future usage from the historical average duration ×
chosen frequency × company count, rather than a theoretical formula.
**Why:** GitHub's billing endpoint requires a more sensitive,
account-scoped token than anything else in this project needs — a bigger
exposure surface for a feature that's really just "how long did our own
runs take." Self-tracking needs no new credentials at all and is exactly
as accurate for this purpose (projecting from real, observed run times).
**Presentation:** two views over the same data — a playful "mascot eating
bandwidth" widget for the main dashboard (percentage-driven animation),
and a plain numeric/percentage panel in a settings/stats view for anyone
who wants the professional version. Same underlying number, two skins —
consistent with the existing dark/light theme approach (ADR-0013).

### ADR-0023 — Onboarding runs as Claude Code sessions, not a GitHub Actions workflow
**Status:** Accepted
**Context:** Claude Code billing is entirely separate from GitHub Actions'
free-tier minutes — Claude Code draws from Elad's own Claude subscription
or API usage, not GitHub's infrastructure. Elad recognized that if the
expensive onboarding work (ADR-0020's full-sweep track: detecting a new
company's ATS, building/verifying its adapter, confirming compliance)
happens during Claude Code sessions rather than inside a scheduled GitHub
Actions workflow, the GitHub Actions free-tier budget never has to pay for
that discovery work at all.
**Decision:** The onboarding/full-sweep track from ADR-0020 is executed as
periodic Claude Code sessions — batch-processing a list of new companies,
verifying each one's ATS/adapter, and committing verified entries to
`companies.json` — rather than as an automated GitHub Actions workflow.
Only after a company is verified this way does it enter the stable track
that the actual scheduled GitHub Actions scan covers.
**Caveat:** this doesn't make onboarding free in an absolute sense — it's
billed through Elad's own Claude plan (subscription quota or API usage),
a separate budget from GitHub's, bounded by that plan's own usage limits
(e.g. rolling session windows) rather than eliminated entirely.
**Why:** Ensures GitHub Actions' free-tier minutes are spent exclusively on
fast, already-known Stage 1 fetches — never on first-encounter exploratory
costs — maximizing how far the free tier stretches as the company list
grows toward ~8,000-9,000.

### ADR-0024 — Ashby gets a real adapter, not a custom-bucket entry
**Status:** Superseded by ADR-0025
**Context:** Session 6 discovered that monday.com's "custom" career page is
actually a proxy for Ashby (every position tagged `source: "ashby"` in the
embedded data). Verified independently: Ashby publishes a real, public,
unauthenticated posting API — `GET
https://api.ashbyhq.com/posting-api/job-board/{clientname}` — returning
clean JSON (title, location, department, team, employmentType, jobUrl,
applyUrl), the same tier as Greenhouse's and Lever's public APIs. Ashby is
a real, widely-used ATS (reportedly thousands of companies), not a rare
edge case.
**Decision:** Build a proper `AshbyAdapter`, hitting Ashby's own API
directly — not by scraping monday.com's (or any other company's) proxy
page. monday.com moves out of the custom bucket and into the Ashby bucket
once verified. The config-driven `CustomAdapter` (Session 6) remains for
companies with genuinely no backing ATS at all — this doesn't replace it,
it just means fewer companies should ever need to land in that bucket than
originally assumed.
**Why:** A platform-level adapter gives leverage across every Ashby-hosted
company at once, the same payoff Greenhouse/Lever/Comeet already provide —
strictly better than a one-off selector config per company for something
that has a real, clean, official API underneath it.

### ADR-0025 — Ashby integration abandoned; monday.com stays on CustomAdapter
**Status:** Accepted (supersedes ADR-0024)
**Context:** Session 7 attempted to build the `AshbyAdapter` ADR-0024
called for. Before any product-data fetch, the Compliance Agent checked
robots.txt for `api.ashbyhq.com` (the domain hosting Ashby's public
posting-api) and got HTTP 401 — verified as a genuine server response, not
an agent bug, via one disclosed out-of-band diagnostic fetch of the
robots.txt file itself (no job/company data touched). Per RFC convention
and this project's own `ComplianceAgent` logic (Session 4), a 401/403 on
robots.txt itself is correctly treated as "disallow all automated access"
to that domain. Further research (this session, planning side) found
`api.ashbyhq.com` hosts both Ashby's authenticated admin/RPC API and the
public posting-api under the same domain, different paths — meaning our
domain-level robots.txt check has no safe way to distinguish "this
specific public sub-path is fine" from "this domain restricts automated
access." Whether the 401 reflects a deliberate policy or bot-detection
flagging the request is genuinely unclear from outside, and doesn't change
the answer either way.
**Decision:** Do not build `AshbyAdapter`. Do not attempt to work around
the robots.txt block (different User-Agent, different headers, or any
other technique to get past what looks like a bot-detection or access
restriction) — that is exactly the kind of bypass ADR-0002 forbids,
regardless of whether the block turns out to be intentional. monday.com
remains permanently on `CustomAdapter` (Session 6's working, tested
implementation) rather than migrating to a Ashby-specific adapter.
**Correction to the record:** ADR-0024's "verified independently" claim was
based on third-party sources confirming the API *works*, not on an actual
robots.txt check by planning-Claude before recommending the integration.
That gap in diligence is what this session's Compliance Agent check
correctly caught. Future ATS-adapter recommendations from planning
sessions should be treated as *candidates requiring empirical compliance
verification*, not settled decisions, until a live session actually checks
robots.txt — the same discipline already applied to every other adapter's
field-shape assumptions.
**Why:** The Compliance Agent's non-negotiable status (ADR-0002) means a
compliance block is a stop, not an obstacle to route around — a
higher-leverage adapter is not worth compromising that principle for.

### ADR-0026 — job_id: sha256(company + absolute_url), not title+location
**Status:** Accepted
**Context:** Session 3 found Palantir posts the identical title ("Forward
Deployed Software Engineer") across dozens of cities — title+location is
not a safe uniqueness key for a job. Session 8 needed a stable identifier
for dedup to work at all.
**Decision:** `job_id = sha256(f"{company}|{source_identifier}")`, where
`source_identifier` is the job's `absolute_url` (already unique per
posting across all four adapters — Greenhouse embeds a numeric ID,
Lever/Comeet/CustomAdapter each embed a UUID — with no adapter changes
needed). Company is included in the hash, not just the identifier alone,
so two companies could never collide even on a coincidentally-identical
identifier string.
**Why:** This is what every future adapter must produce a stable,
unique-per-posting `absolute_url` for — a load-bearing contract, not an
implementation detail, so it's recorded here rather than left to be
rediscovered from `core/schema.py`'s source.

### ADR-0027 — Future multi-user support: independent clones, not shared multi-tenancy
**Status:** Accepted
**Context:** If TheScanner is ever shared beyond Elad, each new person would
want genuinely independent control (their own scan frequency, company
list, schedule) — not settings that could conflict with anyone else's,
since scan configuration affects shared infrastructure (ADR-0009), unlike
local device preferences (ADR-0011/0014).
**Decision:** Sharing the app with other independent users means giving
them their own clone/fork of the repo — their own GitHub account, their
own Actions budget, their own config files, their own schedule. Not a
shared backend with per-user accounts. Right now, with exactly one real
owner (Elad), the app is free to control the real schedule directly —
there's no multi-tenancy to protect against yet, since even a guest using
Elad's own device is operating Elad's one instance, not a competing one.
**Why:** Avoids ever building real multi-tenant write-access (accounts,
permissions, conflict resolution) for a problem that a clone genuinely
solves better — each deployment is fully independent by construction,
not by policy enforced in code.

### ADR-0028 — Scan frequency becomes app-editable via a config-gated schedule
**Status:** Accepted
**Context:** Following ADR-0027, Elad wants to change scan frequency from
the app itself, without needing to edit/commit the GitHub Actions workflow
file each time.
**Decision:** The workflow's registered cron trigger stays fixed and
cheap — a frequent check-in (e.g. hourly), not the real scan schedule.
Each run reads `schedule_config.json` (a plain config file, same pattern
as `roles.json`) to decide whether this check-in should actually run a
full scan or exit immediately at near-zero cost. Changing "scans per day"
becomes editing this config value, not the workflow file — write access
goes through the Cloudflare Worker (already planned for push
notifications; this becomes its second responsibility), which holds any
necessary GitHub write credentials server-side rather than exposing them
in the app.
**Cost tradeoff, disclosed explicitly:** the cheap check-in itself isn't
literally free — an hourly check-in that exits fast is still ~24
runs/day of a few seconds each, a real (small) fraction of the monthly
Actions-minute budget, separate from actual scan minutes. This should be
factored into the scan-budget projector (ADR-0022) as its own line item,
not hidden inside "scan minutes."
**Why:** Makes scan frequency a real, safely-editable app setting — for
the current single-owner reality — without requiring git commits for
every frequency change, and without exposing write credentials
client-side.
