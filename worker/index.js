/**
 * TheScanner Cloudflare Worker (Session 33, ADR-0012/ADR-0029/ADR-0029a;
 * Session 44 adds /api/sync-status, ADR-0011/0014 cross-device sync).
 *
 * Extends the previously assets-only `thescanner` Worker with real
 * server-side logic for four routes; everything else still falls
 * through to the static `pwa/` assets exactly as before this session —
 * confirmed via Cloudflare's current docs (not assumed) that this is
 * the *default* behavior with no extra config needed: `assets.run_worker_first`
 * defaults to `false`, meaning a static asset is served first whenever
 * one matches, and this fetch handler only ever runs for a request that
 * matched no file under `pwa/` at all. None of `/api/push-subscribe`,
 * `/api/trigger-scan`, `/api/notify`, `/api/sync-status` exist as
 * static files, so they reach this handler naturally without needing
 * `run_worker_first` set.
 *
 * Bindings this Worker expects (see wrangler.jsonc + the Session 33/44
 * handoffs for exactly which of these Elad still needs to add):
 * - `env.SUBSCRIPTIONS` — the `thescanner-subscriptions` KV namespace
 *   (kv_namespaces binding in wrangler.jsonc). Session 44 reuses this
 *   same namespace/binding for the sync-status blob too (key
 *   `sync:job-status`, see handleGetSyncStatus/handlePostSyncStatus
 *   below) rather than adding a second namespace — one KV namespace to
 *   create/bind/never-accidentally-delete (see this file's Session 41
 *   history in wrangler.jsonc) is strictly simpler than two, and KV's
 *   per-key value-size limit (25MB) is nowhere near a concern for one
 *   person's job-status map.
 * - `env.GITHUB_PAT` — Cloudflare secret, a fine-grained PAT scoped to
 *   this repo only, `Actions: write` permission only.
 * - `env.TRIGGER_SECRET` — Cloudflare secret, a shared value the PWA
 *   sends back on every `/api/trigger-scan` call (see that handler).
 * - `env.SYNC_SECRET` — Cloudflare secret (Session 44), a shared value
 *   the PWA sends back on every `/api/sync-status` call (see
 *   checkSyncSecret below). Deliberately a SEPARATE secret from
 *   TRIGGER_SECRET, not a reuse: they protect different blast radii
 *   (one can only kick off a GitHub Actions run; the other can read/
 *   write real job-status data) — matching this file's existing
 *   one-secret-per-concern pattern (TRIGGER_SECRET / VAPID keys are
 *   already separate for the same reason). See DEPLOY.md for why the
 *   PWA never stores this value in a committed file at all — Elad
 *   enters it once per device into the Sync section's own field, and
 *   it lives from then on only in that device's localStorage
 *   (pwa/preferences.js's getSyncSecret/setSyncSecret), the same place
 *   every other local, per-device value already lives.
 * - `env.VAPID_PUBLIC_KEY` / `env.VAPID_PRIVATE_KEY` — Cloudflare
 *   secrets (see the Session 33 handoff for the real generated values;
 *   the public key is also needed by the *PWA*, in a future session, to
 *   call `PushManager.subscribe()` — safe to hardcode there since it's
 *   public by design, unlike the private key).
 *
 * None of these secret values are ever logged, echoed in a response
 * body, or written to any file this repo tracks.
 */

import { buildVapidJwt, encryptPushPayload } from "./webpush.js";

const REPO_OWNER = "lanirelad";
const REPO_NAME = "TheScanner";
const WORKFLOW_FILE = "scan.yml";
const GITHUB_API_VERSION = "2022-11-28"; // the long-supported stable default (through 2028) per GitHub's own docs — nothing here needs whatever the newer 2026-03-10 version adds
const VAPID_SUBJECT = "mailto:elad@globus.co.il";

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

async function sha256Hex(text) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** POST /api/push-subscribe — stores one browser's real PushSubscription
 * object (endpoint + keys.p256dh + keys.auth), keyed by a SHA-256 hash of
 * its endpoint URL rather than the raw endpoint string. Two reasons for
 * hashing rather than using the endpoint directly as the KV key: it
 * caps the key at a fixed, short length regardless of how long a given
 * push service's endpoint URL happens to be, and it avoids the endpoint
 * URL itself (which a subscribed device's push-service identity can be
 * inferred from) sitting as a plainly-readable KV key name.
 */
async function handlePushSubscribe(request, env) {
  if (!env.SUBSCRIPTIONS) {
    return json({ ok: false, error: "SUBSCRIPTIONS KV namespace is not bound yet (see wrangler.jsonc)" }, 500);
  }

  let subscription;
  try {
    subscription = await request.json();
  } catch {
    return json({ ok: false, error: "request body is not valid JSON" }, 400);
  }

  const keys = subscription && subscription.keys;
  if (
    !subscription ||
    typeof subscription.endpoint !== "string" ||
    !keys ||
    typeof keys.p256dh !== "string" ||
    typeof keys.auth !== "string"
  ) {
    return json({ ok: false, error: "not a valid PushSubscription object (need endpoint, keys.p256dh, keys.auth)" }, 400);
  }

  const key = `sub:${await sha256Hex(subscription.endpoint)}`;
  await env.SUBSCRIPTIONS.put(key, JSON.stringify(subscription));
  return json({ ok: true });
}

/** POST /api/trigger-scan — dispatches a real workflow_dispatch event
 * against .github/workflows/scan.yml, using env.GITHUB_PAT. Protected by
 * a shared secret (env.TRIGGER_SECRET) checked against an
 * X-Trigger-Secret request header — deliberately simple (ADR: see the
 * task's own "don't over-engineer full auth for a personal single-owner
 * app" instruction), not real user auth. A future PWA session sends this
 * same header value from a "Scan now" button; the exact value lives only
 * in Cloudflare's secret store and whatever Elad puts in the PWA's own
 * config, never committed here.
 */
async function handleTriggerScan(request, env) {
  const provided = request.headers.get("x-trigger-secret");
  if (!env.TRIGGER_SECRET || provided !== env.TRIGGER_SECRET) {
    return json({ ok: false, error: "unauthorized" }, 401);
  }
  if (!env.GITHUB_PAT) {
    return json({ ok: false, error: "GITHUB_PAT secret is not configured on this Worker yet" }, 500);
  }

  const dispatchUrl = `https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW_FILE}/dispatches`;
  let githubResponse;
  try {
    githubResponse = await fetch(dispatchUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_PAT}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "thescanner-worker",
        "content-type": "application/json",
      },
      // return_run_details (GitHub, 2026-02-19 changelog): without this,
      // the endpoint's long-documented behavior is 204 No Content with
      // no way to know which run this call started; asking for it lets
      // a future PWA session link straight to the real run.
      body: JSON.stringify({ ref: "main", return_run_details: true }),
    });
  } catch (err) {
    return json({ ok: false, error: `could not reach GitHub's API: ${err.message}` }, 502);
  }

  if (githubResponse.status === 204) {
    return json({ ok: true, message: "Scan triggered." });
  }
  if (githubResponse.ok) {
    let details = null;
    try {
      details = await githubResponse.json();
    } catch {
      // A 2xx with an unparseable/empty body is still a real success —
      // just without the extra run_url/html_url details to relay.
    }
    return json({ ok: true, message: "Scan triggered.", details });
  }

  const errorText = await githubResponse.text().catch(() => "");
  return json(
    { ok: false, error: `GitHub API responded ${githubResponse.status}`, detail: errorText.slice(0, 500) },
    502
  );
}

/** POST /api/notify — sends a real Web Push notification (RFC 8291
 * encryption + RFC 8292 VAPID signing, see worker/webpush.js) carrying
 * `body`'s JSON as the payload to every subscription currently stored in
 * KV. This is the endpoint the scan workflow will call after a real scan
 * finds new matches — wiring that caller is explicitly a separate future
 * session (per this session's task scope), not built here. A dead/
 * expired subscription (the push service returns 404/410) is removed
 * from KV on the spot rather than left to fail forever on every future
 * notify call.
 */
async function handleNotify(request, env) {
  if (!env.SUBSCRIPTIONS) {
    return json({ ok: false, error: "SUBSCRIPTIONS KV namespace is not bound yet (see wrangler.jsonc)" }, 500);
  }
  if (!env.VAPID_PUBLIC_KEY || !env.VAPID_PRIVATE_KEY) {
    return json({ ok: false, error: "VAPID keys are not configured on this Worker yet" }, 500);
  }

  let payload;
  try {
    payload = await request.json();
  } catch {
    return json({ ok: false, error: "request body is not valid JSON" }, 400);
  }

  const payloadBytes = new TextEncoder().encode(JSON.stringify(payload ?? {}));

  const listKeys = [];
  let cursor;
  do {
    const page = await env.SUBSCRIPTIONS.list({ prefix: "sub:", cursor });
    listKeys.push(...page.keys.map((k) => k.name));
    cursor = page.cursor || undefined;
  } while (cursor);

  let sent = 0;
  let removed = 0;
  const failures = [];

  for (const key of listKeys) {
    const raw = await env.SUBSCRIPTIONS.get(key);
    if (!raw) continue;
    const subscription = JSON.parse(raw);

    try {
      const endpointOrigin = new URL(subscription.endpoint).origin;
      const jwt = await buildVapidJwt(endpointOrigin, VAPID_SUBJECT, env.VAPID_PUBLIC_KEY, env.VAPID_PRIVATE_KEY);
      const body = await encryptPushPayload(payloadBytes, subscription.keys.p256dh, subscription.keys.auth);

      const pushResponse = await fetch(subscription.endpoint, {
        method: "POST",
        headers: {
          "content-type": "application/octet-stream",
          "content-encoding": "aes128gcm",
          ttl: "86400",
          authorization: `vapid t=${jwt}, k=${env.VAPID_PUBLIC_KEY}`,
        },
        body,
      });

      if (pushResponse.status === 404 || pushResponse.status === 410) {
        await env.SUBSCRIPTIONS.delete(key);
        removed++;
        continue;
      }
      if (!pushResponse.ok) {
        failures.push({ key, status: pushResponse.status });
        continue;
      }
      sent++;
    } catch (err) {
      failures.push({ key, error: err.message });
    }
  }

  return json({ ok: true, sent, removed, failed: failures.length, failures });
}

// --- Cross-device status sync (Session 44, ADR-0011/0014) -------------
//
// Elad's applied/ignored marks are still local-only in the ADR-0011
// sense that matters — no OTHER install of this app can ever see or
// affect them, and there is still exactly one real owner. This is
// purely about that one owner's own multiple devices (PC + phone)
// converging on the same marks over time, so a single KV key holds
// the entire status map rather than anything per-device or per-user.

const SYNC_STATUS_KEY = "sync:job-status";

/** Real, minimal last-write-wins-by-`updated_at` merge — the exact
 * same rule pwa/preferences.js's mergeStatuses() implements
 * client-side, reimplemented independently here rather than shared:
 * worker/ and pwa/ are genuinely different JS execution environments
 * in this build-step-free project (no bundler to make a shared import
 * meaningful), so the Worker's own merge-on-write needs to be correct
 * on its own even if some client is ever running stale JS that skips
 * merging locally. Deliberately the simplest correct rule for this
 * task, not a placeholder for something fancier: a status one person
 * changes a few times a day from whichever device is in hand has
 * genuinely rare real conflicts, and "most recent wall-clock edit
 * wins" is exactly what a real person expects in that case — see
 * pwa/preferences.js's own docstring for the fuller reasoning.
 */
function mergeJobStatuses(current, incoming) {
  const merged = { ...current };
  for (const jobId of Object.keys(incoming || {})) {
    const incomingEntry = incoming[jobId];
    const currentEntry = merged[jobId];
    if (
      incomingEntry &&
      typeof incomingEntry.updated_at === "string" &&
      (!currentEntry || new Date(incomingEntry.updated_at).getTime() > new Date(currentEntry.updated_at).getTime())
    ) {
      merged[jobId] = incomingEntry;
    }
  }
  return merged;
}

function checkSyncSecret(request, env) {
  const provided = request.headers.get("x-sync-secret");
  return Boolean(env.SYNC_SECRET) && provided === env.SYNC_SECRET;
}

/** GET /api/sync-status — the full current synced map,
 * `{ [job_id]: { status, updated_at } }`. Used on PWA load and again
 * whenever the tab regains visibility (see app.js) — never polled on
 * a timer, since this data changes at most a few times a day and a
 * fixed interval would just be unneeded KV traffic for no real
 * freshness benefit.
 */
async function handleGetSyncStatus(request, env) {
  if (!env.SUBSCRIPTIONS) {
    return json({ ok: false, error: "SUBSCRIPTIONS KV namespace is not bound yet (see wrangler.jsonc)" }, 500);
  }
  if (!checkSyncSecret(request, env)) {
    return json({ ok: false, error: "unauthorized" }, 401);
  }

  const raw = await env.SUBSCRIPTIONS.get(SYNC_STATUS_KEY);
  return json({ ok: true, statuses: raw ? JSON.parse(raw) : {} });
}

/** POST /api/sync-status — merges the request body's `statuses` map
 * into the stored map (mergeJobStatuses, above) and returns the full
 * merged result in the same response, so the caller can reconcile in
 * one round-trip instead of needing a follow-up GET. The client is
 * expected to send its ENTIRE current local map every time, not a
 * diff — see pwa/preferences.js's syncStatuses() for why: it means a
 * device's very first push already carries forward any pre-existing
 * Session 28/30 local-only history (already normalized into this
 * shape by loadJobStatuses()'s migration), so first-sync migration
 * falls out of the normal merge path for free, with no separate
 * one-time migration endpoint or flag needed anywhere.
 */
async function handlePostSyncStatus(request, env) {
  if (!env.SUBSCRIPTIONS) {
    return json({ ok: false, error: "SUBSCRIPTIONS KV namespace is not bound yet (see wrangler.jsonc)" }, 500);
  }
  if (!checkSyncSecret(request, env)) {
    return json({ ok: false, error: "unauthorized" }, 401);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "request body is not valid JSON" }, 400);
  }
  if (!body || typeof body.statuses !== "object" || body.statuses === null) {
    return json({ ok: false, error: "body must be { statuses: { [job_id]: { status, updated_at } } }" }, 400);
  }

  const raw = await env.SUBSCRIPTIONS.get(SYNC_STATUS_KEY);
  const current = raw ? JSON.parse(raw) : {};
  const merged = mergeJobStatuses(current, body.statuses);

  await env.SUBSCRIPTIONS.put(SYNC_STATUS_KEY, JSON.stringify(merged));
  return json({ ok: true, statuses: merged });
}

// Per-path method maps rather than a single POST-only assumption
// (Session 44) — /api/sync-status genuinely needs both GET (pull) and
// POST (push), unlike the three Session 33 routes, which stay
// POST-only exactly as before.
const ROUTES = {
  "/api/push-subscribe": { POST: handlePushSubscribe },
  "/api/trigger-scan": { POST: handleTriggerScan },
  "/api/notify": { POST: handleNotify },
  "/api/sync-status": { GET: handleGetSyncStatus, POST: handlePostSyncStatus },
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const methods = ROUTES[url.pathname];

    if (!methods) {
      return json({ ok: false, error: "not found" }, 404);
    }
    const handler = methods[request.method];
    if (!handler) {
      return json({ ok: false, error: `method not allowed, use ${Object.keys(methods).join(" or ")}` }, 405);
    }

    return handler(request, env);
  },
};
