# DEPLOY.md — Deployment / Installation Notes

## Current status (as of Session 33)
Live and deployed: `https://thescanner.lanirelad.workers.dev/`, via
Cloudflare Workers with Static Assets + Git integration (ADR-0029/
ADR-0029a — corrects the GitHub-Pages plan below, kept only for
historical context). Every push to `main` redeploys automatically —
there is no separate manual deploy step.

Session 33 added a real Worker script (`worker/index.js`) alongside the
static assets, for three push/trigger-scan API routes (see
ARCHITECTURE.md §11 for the real, current design) — but two real
Cloudflare-side setup steps are still outstanding as of this session:
- A fine-grained GitHub PAT (repo-scoped, `Actions: write` only) has not
  been created yet.
- The `thescanner-subscriptions` KV namespace has not been created yet.
Until both exist, the three new routes deploy safely (they don't affect
the existing static PWA at all) but return a clean, diagnosable error
instead of doing real work — see the Session 33 handoff for exactly
what Elad needs to do next.

## Runtime architecture (decided — see DECISIONS.md ADR-0009, 0012, 0013,
0029, 0029a)
- **Compute:** GitHub Actions, manual `workflow_dispatch` trigger today
  (`schedule_config.json`'s `mode` defaults to `on_demand`, ADR-0028) —
  scheduled runs are a switchable option, not currently active.
- **Shared data:** committed to the repo as JSON/SQLite after each scan
  run; `pwa/latest_scan.json` + `pwa/usage_summary.json` are the two
  plain-JSON exports the PWA actually fetches.
- **Client:** a PWA (manifest.json + service worker), installable on
  Android, works as a normal tab on the laptop. Hosted on Cloudflare
  Workers with Static Assets (**not** GitHub Pages — see ADR-0029 for
  why GitHub Pages structurally can't do "private repo, private
  results" on the free tier). Dark/light theme built in.
- **Push notifications:** the same `thescanner` Cloudflare Worker now
  also runs real backend logic (`worker/index.js`, Session 33) —
  storing Web Push subscriptions in KV, dispatching manual scans via
  GitHub's API, and sending Web Push notifications — alongside serving
  the static PWA. No third-party messaging account (Telegram, etc.)
  involved.
- **Local-only state:** role/tag filters and per-job status live in each
  device's local storage (`pwa/preferences.js`) — never touch the
  backend. This is what makes multiple independent installs safe.

## Secrets / config
Real secret values (the GitHub PAT, the VAPID private key, the
trigger-scan shared secret, the sync shared secret) go into
Cloudflare's own secret store only — `wrangler secret put <NAME>` or
the dashboard's Settings → Variables → "Secret" type. **Never** a
committed file, even a gitignored one — see `worker/index.js`'s own
docstring for the exact secret names it expects (`GITHUB_PAT`,
`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `TRIGGER_SECRET`,
`SYNC_SECRET`) and the Session 33/44 handoffs for their real values
(the VAPID public key is safe to share; the other four are not).
`.gitignore` already covers `.env`/`*secret*`/`*credential*`/`*.pem`
as a backstop, but the real rule is simpler: these five values never
get written to any file this repo tracks in the first place.

**`SYNC_SECRET` is different from the other four in one way** (Session
44, ARCHITECTURE.md §11a): the PWA itself needs to send it back on
every `/api/sync-status` call, but this is a plain static site with no
build step, so there's no way to inject a server-side secret into
deployed client JS without either a build step or committing it. The
resolution: after setting `SYNC_SECRET` as a Cloudflare secret (same
`wrangler secret put SYNC_SECRET` / dashboard flow as the others),
Elad enters that same value once per device into the PWA's own "🔄
Sync across devices" section — it's stored only in that device's
`localStorage` from then on, never in any file this repo tracks. A
device with no value entered (or the wrong one) just gets a 401 from
the Worker and falls back to fully local-only behavior — never a
broken UI.

## Dependencies (confirmed, not anticipated)
- Python 3.x — scanning pipeline (adapters, core, compliance, storage,
  usage). `httpx` for the production pipeline (ADR-0021); `playwright`
  is a discovery-only dependency (`requirements-discovery.txt`,
  ADR-0031), never installed by the GitHub Actions workflow.
- `sqlite3` (standard library) — dedup state (`scan_results.db`).
- PWA: plain HTML/CSS/JS, no framework, no build step — Web Push API +
  Service Worker for offline shell caching.
- Cloudflare Worker (`worker/`): plain JavaScript (ES modules), no
  framework, no npm dependencies at all — Web Push's RFC 8291/8292
  crypto is hand-implemented on `crypto.subtle` (Session 33) rather than
  the `web-push` npm package, since this repo has no verified build/
  bundle step for Cloudflare's Git-integration deploy to run against.
