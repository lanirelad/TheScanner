# MEMORY.md — Full Context (paste into Project so any new session knows this)

## Origin
Elad found secretjobs.ai — a paid product that crawls 5,000+ Israeli
hi-tech company career pages hourly and cross-references against LinkedIn to
surface roles not posted there (~34% of postings). Elad wants to build a
personal version of this, focused specifically on **DevOps Engineer** and
**Technical Support Engineer** roles, but built so other role categories can
be added easily later.

## Project name
**TheScanner.**

## Core concept
- Scan company career pages directly, not LinkedIn/job boards.
- Most Israeli tech companies use one of a few ATS platforms (Greenhouse,
  Lever, Comeet), and Greenhouse/Lever expose public JSON APIs — hit those
  directly instead of scraping HTML where possible. Fall back to HTML
  scraping (Playwright + BeautifulSoup) only for custom career pages.
- Filter results using a config-driven, tag-based keyword system —
  **English and Hebrew both** — so terminology drift (e.g. "SRE" vs "DevOps
  Engineer" vs "Platform Reliability Engineer") is handled by adding a tag
  to `roles.json`, not by changing code.
- Role categories are not hardcoded — `roles.json` currently has
  `devops` and `technical_support`, but new categories can be added the same
  way (e.g. QA Automation later, if wanted).
- **Company coverage target: as large as feasible**, not a small pilot list.
  Elad explicitly rejected the initial 30–50 company suggestion — the goal
  is the biggest scan realistically buildable. Sourcing strategy: harvest
  company slugs from ATS-native directories first (Greenhouse/Lever/Comeet —
  highest yield since the adapter already exists for these), then
  cross-reference against public Israeli tech company registries
  (Start-Up Nation Finder, IVC Online, etc.) for anything missed.
- Dedup against previously seen postings so the same job doesn't alert
  twice.
- (Optional/later phase) Cross-reference against LinkedIn to tag postings
  as "not on LinkedIn," similar to secretjobs.ai — deferred, privacy/ToS
  considerations not yet resolved.
- Alerts via email and/or Telegram (not yet decided which).

## Working model (borrowed from two other Claude Projects)
Elad has two other long-running Claude Projects with an established
operating model, which TheScanner reuses:

- **"Goblet of Operations"** (his personal DevOps-learning game, Git-graph-
  as-maze) — the *source* of the reusable, domain-neutral "Work Architecture"
  template: living markdown docs as the single source of truth, an
  append-only ADR log, a three-layer QA framework (static/regression,
  runtime/integrity, functional/end-to-end against a safe sandbox — never
  real user data), a named agent roster split into dev-time vs runtime and
  AI vs deterministic (deterministic by default), and a structured
  Claude-Code handoff loop.
- **MyCalib / CalibPro** (Elad's work project — calibration-hardware
  software, not yet cleared for public naming, so kept generic on any CV) —
  the *applied example* of that same template: same 9 living docs (plus a
  `SYNC.md` for their manual-upload sync method), the same handoff loop, and
  a concrete three-tier automated QA build (dependency-direction checks,
  binding-mode guards, a "stub-skill tripwire," integrity-seal round-trip
  tests, startup smoke tests) — proof the pattern holds up in a real,
  safety-sensitive build.

TheScanner's docs adapt this same template, with two domain-specific
choices made explicit as ADRs:
- **Sandbox** = a small fixed set of cached fixture responses for 3–5 test
  companies; automated tests never hit live company sites.
- **Non-negotiable safety gate** = the Compliance Agent — robots.txt
  honored, rate limits enforced, no CAPTCHA bypass, no PII ever stored. This
  cannot be skipped for any reason.

## Key decisions made so far (full detail in DECISIONS.md)
1. ATS JSON APIs preferred over HTML scraping (Greenhouse/Lever first, then
   Comeet, then custom fallback).
2. Compliance Agent is mandatory on every fetch, no exceptions.
3. No personal/candidate data ever stored — job-posting metadata only.
4. Elad approves every commit/push individually; Claude Code never
   commits/pushes on its own.
5. No AI-powered agents by default — all matching is deterministic
   keyword-tag matching; an LLM classifier would need its own separate ADR.
6. Sandbox testing uses fixtures only, never live sites.
7. Roles/tags live in `roles.json` (English + Hebrew), not hardcoded.
8. Company coverage target is maximum feasible via ATS-directory harvesting
   + registry cross-referencing, not a small curated list — Elad
   specifically wants ~1,500 companies scanned, not the originally-proposed
   30-50.
9. **Deployment must work on both his laptop and Android phone, and must
   stay free.** Resolved by making the system cloud-resident rather than
   device-resident: GitHub Actions runs the scan (free tier), GitHub Pages
   hosts a static dashboard viewable from any browser on either device, and
   a Cloudflare Worker (free tier) handles the one write operation the
   dashboard needs. Neither device needs to be on for scans to happen —
   both are just viewers.
10. **Scan frequency: twice daily**, not hourly (hourly was the initial
    suggestion; Elad said it's too much) — plus an always-available manual
    "Run now" button (`workflow_dispatch`) for on-demand scans.
11. **Full-scan time estimate for ~1,500 companies: roughly 15-30 minutes**,
    split between fast ATS-API companies (parallelizable across domains,
    ~5-10 min) and slower custom/HTML-scraped companies (~10-20 min). This
    fits well within GitHub Actions' free-tier minutes even at twice-daily
    frequency.
12. **New-vs-seen tracking**: every job gets a `scan_status` of `new`
    (first time seen this run) or `still_open` (seen before, still posted),
    derived from existing `first_seen_at`/`last_seen_at` fields.
13. **"Mark as applied" feature**: a new `application_status` field
    (`not_applied`/`applied`) that Elad sets by clicking a button on the
    dashboard. Since GitHub Pages is static, this required designing an
    actual write path — Elad chose a **Cloudflare Worker** (free tier) over
    a browser-side scoped GitHub token, specifically to avoid exposing any
    write-capable credential client-side, accepting the extra setup cost
    for the better security posture.

## Still open / not yet confirmed
- Exact times of day for the twice-daily schedule.
- How exactly to harvest ~1,500 company slugs at scale from
  Greenhouse/Lever/Comeet (research needed on what each platform exposes
  publicly vs. what has to be built from registries).

## Scan efficiency pivot (2026-08-07, same session)
Elad pointed out that scanning ~1,500 companies for *all* their roles
across *all* countries is wasteful — many are multinational and post
globally under one career page, not just in Israel. Resolved with a
**two-stage fetch** (ADR-0016):
- **Stage 1 (always runs, cheap):** pull the lightweight job list per
  company — title, department, location, no full description. Every ATS
  platform returns this in one call regardless of how many roles exist.
- **Filter immediately, before anything heavy:** check location
  (`locations.json`, new — same config-driven pattern as `roles.json`, EN +
  Hebrew) and title/tags right there. Most roles get rejected for free at
  this stage — a multinational's global job list mostly disappears here.
- **Stage 2 (only for ambiguous matches):** fetch the full description,
  re-check tags against the description text.
This means the actual scan cost is much lower than "1,500 companies × all
their roles" sounds like — most of that is rejected cheaply before any
heavy fetch happens.

## Client architecture pivot (2026-08-07, same session as the above)
Elad asked three things that reshaped the client design:

1. **"What if I let someone else use the app?"** — he correctly flagged
   that storing everything as one shared dataset (roles, applied-status)
   would be bad practice once a second person is involved. Resolved by
   making the app **always single-user-per-install**: role/tag preferences
   and `application_status` live entirely in local device storage, never
   in a shared backend. Anyone who installs the app gets fully independent
   state — no accounts, no login, no possibility of cross-contamination.
   This is ADR-0011 (revised) and ADR-0014.

2. **"Let's make it a phone app with a nice dark/light GUI"** — since no
   sensitive data is involved (only public job metadata), a full native
   app wasn't worth the Google Play developer fee and build tooling.
   Decided on a **PWA** instead: installable on Android, works as a normal
   tab on the laptop, dark/light theme, free. This is ADR-0013.

3. **Alerts: reconsidered Telegram** — once it became clear the app itself
   is a phone app, Elad reasoned the app can deliver its own native alerts
   instead of routing through Telegram or a similar third-party service.
   Decided on **Web Push notifications** (the same free, built-in mechanism
   real Android apps use), delivered via a Cloudflare Worker that stores
   push subscriptions and fires notifications when new matches are found.
   This is ADR-0012, and it changed the Cloudflare Worker's purpose — it
   was originally proposed as a write-path for "mark as applied," but that
   feature moved to local-only storage, so the Worker's job now is push
   delivery instead.

4. **Application links** — every job card links directly to the original
   posting (`source_url`) via a tappable "Apply" link; nothing is copied or
   mirrored. This is ADR-0015.

**Current full architecture, end to end:**
```
GitHub Actions (2x/day + manual button)
  -> scans companies, commits shared results to repo
  -> notifies Cloudflare Worker of new matches
       -> Worker pushes native notifications to subscribed devices

PWA (installed on laptop and/or phone, independently per install)
  -> reads shared scan results
  -> filters using THIS DEVICE's local role/tag preferences
  -> shows new vs. still_open, dark/light theme
  -> "mark as applied" writes only to local device storage
  -> "Apply" link opens the real posting directly
  -> registers once for Web Push via the Cloudflare Worker
```

## Repo state
Scaffolding only as of 2026-08-07: the 9 living docs
(README/CLAUDE/CLAUDE_CODE_GUIDE/ARCHITECTURE/DECISIONS/PLAN/PROGRESS/
CHANGELOG/DEPLOY) plus this MEMORY.md and PROJECT_INSTRUCTIONS.md. No code,
no `companies.json`, no `roles.json` file yet (schema for both is drafted in
ARCHITECTURE.md). No repo pushed to GitHub yet.

## Immediate next steps (see PLAN.md)
1. Push scaffolding to a private GitHub repo.
2. Seed `roles.json` with starter EN/HE tags for devops + technical_support.
3. Start harvesting companies.json toward ~1,500 companies — ATS-directory
   approach first.
4. Build the GitHub Actions workflow skeleton (schedule + manual trigger)
   early, to prove the deployment shape before adapters are complete.
5. Scaffold the PWA shell (manifest, service worker, install prompt,
   dark/light theme) and the Cloudflare Worker (push subscription storage +
   delivery) early, to prove the client architecture before real job data
   exists.
