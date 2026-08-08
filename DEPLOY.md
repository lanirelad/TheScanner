# DEPLOY.md — Deployment / Installation Notes

## Current status
Not deployed anywhere. Local development only.

## Runtime architecture (decided — see DECISIONS.md ADR-0009, 0012, 0013)
- **Compute:** GitHub Actions, scheduled twice daily + manual
  `workflow_dispatch` trigger. Free tier easily covers this.
- **Shared data:** committed to the repo as JSON/SQLite after each scan run.
- **Client:** a PWA (manifest.json + service worker), installable on
  Android, works as a normal tab on the laptop. Hosted via GitHub Pages
  (free). Dark/light theme built in.
- **Push notifications:** Cloudflare Worker (free tier) stores Web Push
  subscriptions and sends notifications when a scan finds new matches. No
  third-party messaging account (Telegram, etc.) involved.
- **Local-only state:** role/tag filters and `application_status` live in
  each device's local storage (IndexedDB/localStorage) — never touch the
  backend. This is what makes multiple independent installs safe.

## Secrets / config
When the Cloudflare Worker is set up, its credentials (API tokens, VAPID
keys for Web Push) go in Cloudflare's own secret store / a local `.env` —
never committed. Add `.env` to `.gitignore` on day one.

## Dependencies (anticipated, confirm when each phase starts)
- Python 3.x — scanning pipeline (adapters, core, compliance, storage)
- `requests` (ATS JSON APIs)
- `beautifulsoup4` + `playwright` (HTML fallback adapter)
- `sqlite3` (standard library)
- PWA: plain HTML/CSS/JS + Web Push API + Service Worker — no heavy
  framework needed for a job listing UI this size
- Cloudflare Worker: JavaScript/TypeScript, `web-push` library or Cloudflare's
  native Web Push support
