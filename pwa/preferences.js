"use strict";

/**
 * Local-only device preferences (Session 28, ADR-0011/ADR-0014) +
 * cross-device status sync (Session 44, same ADRs — see the note
 * below on why this doesn't reopen either one).
 *
 * Two things live here, both stored in this device's own localStorage
 * and NEVER sent anywhere as part of the shared scan pipeline — no
 * run.py write path, no shared-repo file:
 *
 * - Which role categories this device wants to see (a client-side
 *   display filter on top of latest_scan.json's matches — it does not
 *   change what roles.json/the backend scan looks for at all). Stays
 *   local-only, full stop — this session's sync feature explicitly
 *   does not touch it (see PROGRESS.md's Session 44 addendum for why:
 *   a display filter isn't a decision worth preserving the way an
 *   applied/ignored mark is).
 * - Per-job local status: not_set / applied / ignored (Session 30
 *   extended this from Session 28's plain applied/not-applied boolean;
 *   Session 44 extends it again — see JOB_STATUS_KEY below for both
 *   migration stories). This one now ALSO syncs to a single-owner
 *   Worker endpoint (`/api/sync-status`, worker/index.js) so the same
 *   person's own multiple devices converge on the same marks — this
 *   is NOT a reversal of ADR-0011/0014: there is still exactly one
 *   real owner, still no accounts, still no other install's data ever
 *   reachable from this one. It's the same person's own devices
 *   catching up with each other, nothing else.
 *
 * Deliberately a separate file from app.js, not just a separate
 * section of it: app.js's bottom section calls main()/initThemeToggle()/
 * registerServiceWorker() immediately on load, which needs a real DOM
 * and successfully-fetchable JSON to run without throwing. Most
 * functions in *this* file are still pure functions or thin
 * localStorage wrappers with no DOM access — Session 44's sync
 * functions are the first real exception (they do call `fetch`), kept
 * clearly separated in their own section below and designed to be
 * tested with a faked `fetch` rather than a real network call (see
 * pwa/tests/preferences.test.html). This project has no Node.js-based
 * JS test runner (none existed before Session 28, and this sandbox has
 * no Node.js installed at all) — the test harness runs these functions
 * directly in a real browser instead, which is exactly the environment
 * this code actually runs in anyway.
 */

const ROLE_FILTERS_KEY = "thescanner:role_filters";

/** Session 28's original key: { [job_id]: true } meant "applied," any
 * other job simply had no entry. Read-only from here on — never
 * written to again — kept purely so loadJobStatuses() below can migrate
 * a device's existing marks forward without ever deleting the source
 * data it migrated from. Real risk considered before choosing a
 * migration over a clean break: Elad has been actively using this PWA
 * since Session 28 shipped (he's the one who reported Session 27's
 * caching bug from real usage), so a clean break risks silently
 * discarding marks he's already made — not a risk worth taking to save
 * a few lines of code. */
const LEGACY_APPLIED_JOBS_KEY = "thescanner:applied_jobs";

/** Session 30's tri-state key, Session 44 changes its VALUE SHAPE.
 *
 * Session 30 shape (now itself legacy, still read below):
 *   { [job_id]: "applied" | "ignored" } — no stored "not_set" value,
 *   absence of a key meant not_set.
 *
 * Session 44 shape: { [job_id]: { status, updated_at } }. Two real
 * changes, both forced by cross-device sync being genuinely correct
 * rather than a compromise:
 *
 * 1. Every entry now carries `updated_at` (an ISO8601 string) so a
 *    merge with another device's data can tell which edit actually
 *    happened more recently — see mergeStatuses() below.
 * 2. Setting a job back to NOT_SET now stores an explicit
 *    `{status: "not_set", updated_at}` TOMBSTONE instead of deleting
 *    the key. This reverses Session 28/30's "don't persist the default
 *    state" convention for this one key on purpose: without a
 *    tombstone, clearing a mark on this device would just make the
 *    key disappear locally, so a later pull from another device (or
 *    the Worker) that still has the OLD "applied"/"ignored" entry
 *    would have no way to know the clear ever happened and would
 *    silently resurrect it. A tombstone with a real timestamp lets
 *    the same last-write-wins rule that resolves every other conflict
 *    also resolve "was this explicitly un-marked more recently than
 *    it was marked" correctly. At this app's real scale (one person,
 *    a status that changes a few times a day) an ever-growing set of
 *    tombstones is not a real storage concern — see PROGRESS.md's
 *    Session 44 addendum.
 */
const JOB_STATUS_KEY = "thescanner:job_status";

/** Sentinel `updated_at` for data migrated forward from a shape that
 * never recorded a real timestamp at all (Session 28's boolean key,
 * or Session 30/pre-Session-44 entries under this same key). The
 * oldest possible timestamp, not "now" — using "now" would make
 * genuinely old, unknown-age local marks incorrectly outrank real,
 * dated data pulled from another device during this device's very
 * first sync; the epoch correctly lets any real timestamp win instead.
 */
const UNKNOWN_UPDATED_AT = "1970-01-01T00:00:00.000Z";

const JOB_STATUS = Object.freeze({
  NOT_SET: "not_set",
  APPLIED: "applied",
  IGNORED: "ignored",
});

/** Read this device's stored role-category toggles.
 *
 * Shape: { [role_category]: false }. A category is only ever written
 * here when the user explicitly turns it OFF — there is no stored
 * `true` value, since "on" is already the implicit default (see
 * isRoleEnabled below). Malformed/missing storage fails safe to "no
 * overrides at all" (everything shows), not a thrown error.
 */
function loadRoleFilters() {
  try {
    const raw = localStorage.getItem(ROLE_FILTERS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveRoleFilters(filters) {
  localStorage.setItem(ROLE_FILTERS_KEY, JSON.stringify(filters));
}

/** Is `roleCategory` enabled for display, given this device's stored
 * filters?
 *
 * Default-enabled, not default-disabled: a role_category with no entry
 * in `filters` at all is shown. This is what "match whatever roles.json
 * currently has enabled" (the task's own requirement) reduces to in
 * practice — every match in latest_scan.json already only ever comes
 * from a category the backend's own roles.json `enabled` flag allowed
 * through (core/filters.py's RoleLocationFilter, Session 11) — so
 * "no local override yet" and "show everything the backend already
 * decided to include" are the same thing, with no need for this file
 * to know roles.json's contents at all.
 */
function isRoleEnabled(roleCategory, filters) {
  return filters[roleCategory] !== false;
}

/** Pure predicate: should `job` render, given this device's filters? */
function shouldShowJob(job, filters) {
  return isRoleEnabled(job.role_category, filters);
}

/** Toggle one role category's stored state. Pure — returns a new
 * object, never mutates `filters`. Deletes the key entirely when
 * toggling back to enabled, rather than storing an explicit `true`,
 * so a device that never touches the settings panel keeps an empty,
 * trivially-inspectable `{}` in localStorage indefinitely.
 */
function toggleRoleFilter(roleCategory, filters) {
  const next = { ...filters };
  if (isRoleEnabled(roleCategory, filters)) {
    next[roleCategory] = false;
  } else {
    delete next[roleCategory];
  }
  return next;
}

/** Every role category worth showing a toggle for: every category
 * actually present in this scan's matches, unioned with any category
 * this device has an opinion about from a previous scan (so turning a
 * category off persists across a run where it happens to have zero
 * current matches, instead of silently forgetting the preference).
 * Pure function of (matches, filters) — no I/O.
 *
 * Returns [{role_category, label}], ordered by first appearance in
 * `matches` (stable, not alphabetical-resorted every render) with any
 * filter-only categories appended after.
 */
function availableRoleCategories(matches, filters) {
  const labels = new Map();
  for (const job of matches) {
    if (!labels.has(job.role_category)) {
      labels.set(job.role_category, job.label_en || job.role_category);
    }
  }
  for (const roleCategory of Object.keys(filters)) {
    if (!labels.has(roleCategory)) {
      // A category the device has an opinion about but with zero
      // matches in *this* scan — no label_en available from anywhere,
      // so the raw key is the honest fallback (same fail-safe spirit
      // as run.py's _role_label()).
      labels.set(roleCategory, roleCategory);
    }
  }
  return Array.from(labels.entries()).map(([role_category, label]) => ({ role_category, label }));
}

function _readJSON(key) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

/** Read this device's per-job statuses, migrating BOTH older shapes
 * forward on every read rather than as a one-time destructive
 * migration step — simpler, and there's no window where a read could
 * observe a half-migrated state, since nothing is ever deleted:
 *
 * - Session 28's legacy boolean key (`{ [job_id]: true }`).
 * - Pre-Session-44 entries under JOB_STATUS_KEY itself that are still
 *   a plain string (`"applied"`/`"ignored"`) rather than the new
 *   `{status, updated_at}` object shape.
 *
 * Both get UNKNOWN_UPDATED_AT stamped on since their real edit time
 * was never recorded. A legacy/old-shape entry is only honored when
 * the current key has no NEW-shape opinion for that job_id at all —
 * once a job has a real `{status, updated_at}` entry (including one
 * written by a NOT_SET tombstone), older generations are permanently
 * superseded for that job_id, same "touch it once under the new model
 * and the new model owns it from then on" behavior Session 30 already
 * established for its own migration.
 */
function loadJobStatuses() {
  const legacyBoolean = _readJSON(LEGACY_APPLIED_JOBS_KEY);
  const current = _readJSON(JOB_STATUS_KEY);

  const merged = {};
  for (const jobId of Object.keys(legacyBoolean)) {
    if (legacyBoolean[jobId] === true) {
      merged[jobId] = { status: JOB_STATUS.APPLIED, updated_at: UNKNOWN_UPDATED_AT };
    }
  }
  for (const jobId of Object.keys(current)) {
    const value = current[jobId];
    if (typeof value === "string") {
      // Pre-Session-44 shape under this same key — real timestamp unknown.
      merged[jobId] = { status: value, updated_at: UNKNOWN_UPDATED_AT };
    } else if (value && typeof value === "object" && typeof value.status === "string") {
      merged[jobId] = value;
    }
  }
  return merged;
}

function saveJobStatuses(statuses) {
  localStorage.setItem(JOB_STATUS_KEY, JSON.stringify(statuses));
}

/** Reads just the status string out of a `{status, updated_at}` entry
 * (or a missing entry, or — belt and suspenders — a not-yet-migrated
 * plain string, since callers occasionally hold a `statuses` object
 * built by hand in a test rather than one that went through
 * loadJobStatuses()). Any tombstone (`status: "not_set"`) reads
 * exactly the same as a missing entry, by design — see JOB_STATUS_KEY's
 * docstring above for why a tombstone exists on disk at all despite
 * meaning the same "not set" thing a plain absence used to.
 */
function getJobStatus(jobId, statuses) {
  const entry = statuses[jobId];
  if (!entry) return JOB_STATUS.NOT_SET;
  if (typeof entry === "string") return entry;
  return entry.status || JOB_STATUS.NOT_SET;
}

function isApplied(jobId, statuses) {
  return getJobStatus(jobId, statuses) === JOB_STATUS.APPLIED;
}

function isIgnored(jobId, statuses) {
  return getJobStatus(jobId, statuses) === JOB_STATUS.IGNORED;
}

/** Set one job's status outright. Pure — returns a new object, never
 * mutates `statuses`. Always stores a real `{status, updated_at}`
 * entry now, INCLUDING for NOT_SET (a tombstone) — see JOB_STATUS_KEY's
 * docstring above for why this is a deliberate reversal of the
 * previous "don't persist the default state" behavior, forced by
 * needing NOT_SET to be able to win a cross-device merge against an
 * older applied/ignored entry. `updatedAt` defaults to the real
 * current time but is a real parameter (not hardcoded) precisely so
 * tests can pass a fixed value instead and get deterministic,
 * comparable timestamps. This is still the one place that enforces
 * the tri-state's mutual exclusivity: setting a job to any status
 * always fully replaces whatever it was before — there is no code
 * path that could leave a job marked both applied and ignored at once.
 */
function setJobStatus(jobId, statuses, newStatus, updatedAt = new Date().toISOString()) {
  return { ...statuses, [jobId]: { status: newStatus, updated_at: updatedAt } };
}

/** Toggle one job between APPLIED and NOT_SET. If the job was IGNORED,
 * this moves it straight to APPLIED (not NOT_SET) — clicking "Mark as
 * applied" is a real statement of intent about this specific status,
 * not a blind toggle of whatever was there before.
 */
function toggleApplied(jobId, statuses, updatedAt = new Date().toISOString()) {
  const next = isApplied(jobId, statuses) ? JOB_STATUS.NOT_SET : JOB_STATUS.APPLIED;
  return setJobStatus(jobId, statuses, next, updatedAt);
}

/** Toggle one job between IGNORED and NOT_SET — same "was it already
 * applied? then move straight to ignored" reasoning as toggleApplied.
 */
function toggleIgnored(jobId, statuses, updatedAt = new Date().toISOString()) {
  const next = isIgnored(jobId, statuses) ? JOB_STATUS.NOT_SET : JOB_STATUS.IGNORED;
  return setJobStatus(jobId, statuses, next, updatedAt);
}

/** Split `matches` into the jobs that stay in their normal new/
 * still_open groups and the ones that move to the Ignored section.
 * Pure function of (matches, statuses) — no I/O. Applied jobs are
 * deliberately NOT split out here — they stay wherever `matches`
 * already puts them, same position and grouping as before this
 * session, only visually marked (see app.js's jobCardHTML).
 */
function partitionByIgnored(matches, statuses) {
  const active = [];
  const ignored = [];
  for (const job of matches) {
    (isIgnored(job.job_id, statuses) ? ignored : active).push(job);
  }
  return { active, ignored };
}

// --- Cross-device status sync (Session 44) --------------------------------
//
// See worker/index.js's own matching section for the server side of
// this (GET/POST /api/sync-status, same KV namespace as push
// subscriptions, one fixed key since there's exactly one real owner).

const SYNC_ENDPOINT = "/api/sync-status";

/** Where this device's copy of the shared sync secret lives: this
 * device's own localStorage, entered once by Elad via the Sync
 * section in the app itself (see app.js's initSyncSettings) — NEVER a
 * committed file, not even a gitignored one (DEPLOY.md's existing
 * rule for every other secret in this project, and it applies here
 * for the same reason: this repo's PWA assets are served byte-for-
 * byte from git with no build step, so anything in a tracked file
 * would ship in the deployed JS verbatim). An empty string (never
 * configured, or the user cleared it) is a valid, common state — sync
 * calls below simply get a 401 from the Worker and fail closed to
 * local-only behavior, exactly as if the device were offline.
 */
const SYNC_SECRET_KEY = "thescanner:sync_secret";

function getSyncSecret() {
  try {
    return localStorage.getItem(SYNC_SECRET_KEY) || "";
  } catch {
    return "";
  }
}

function setSyncSecret(secret) {
  localStorage.setItem(SYNC_SECRET_KEY, secret);
}

/** Pure merge, no network/localStorage — kept separate from the
 * fetch-based functions below so the one part of this feature where a
 * subtle bug would be genuinely hard to notice from casual use (a
 * timestamp comparison that's backwards, or off by one operator) has
 * real, direct, dependency-free test coverage. That kind of bug would
 * silently make older data win sometimes — exactly the shape of thing
 * that only surfaces as "why did my ignore come back" days later, not
 * immediately on the call that caused it.
 *
 * Conflict rule: last-write-wins by `updated_at`, remote or local,
 * whichever is more recent — deliberately the simplest correct rule
 * for this task, not a placeholder for something fancier. A status
 * one person changes a few times a day from whichever device happens
 * to be in hand has genuinely rare real conflicts; when the rare
 * double-edit does happen, "whichever happened most recently in
 * wall-clock time wins" is exactly what a real person expects, with
 * none of the bookkeeping a general vector-clock/CRDT scheme would
 * need for far more contentious multi-writer scenarios this app will
 * never actually have.
 */
function mergeStatuses(localStatuses, remoteStatuses) {
  const merged = { ...localStatuses };
  for (const jobId of Object.keys(remoteStatuses || {})) {
    const remoteEntry = remoteStatuses[jobId];
    const localEntry = merged[jobId];
    if (
      remoteEntry &&
      typeof remoteEntry.updated_at === "string" &&
      (!localEntry || new Date(remoteEntry.updated_at).getTime() > new Date(localEntry.updated_at).getTime())
    ) {
      merged[jobId] = remoteEntry;
    }
  }
  return merged;
}

/** Fire-and-forget push of this device's full current statuses map up
 * to the Worker. Always sends the WHOLE map, never a diff: the Worker
 * merges by timestamp regardless of what it already has, so
 * re-sending unchanged entries is harmless, and it's what makes first-
 * sync migration free (see JOB_STATUS_KEY's docstring + worker/
 * index.js's handlePostSyncStatus) rather than a separate one-time
 * code path. Never throws and never returns anything the caller needs
 * to check: a failed push (offline, wrong/missing secret, Worker
 * down) must never block or error the UI, since localStorage already
 * holds the authoritative local write and the next successful sync —
 * from this device or another — will catch it up regardless.
 */
async function pushStatusesToServer(statuses) {
  try {
    await fetch(SYNC_ENDPOINT, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-sync-secret": getSyncSecret(),
      },
      body: JSON.stringify({ statuses }),
    });
  } catch {
    // Deliberately swallowed — see docstring above.
  }
}

/** The Worker's current full statuses map, or {} on ANY failure
 * (offline, wrong/missing secret, Worker down, malformed response) —
 * never a thrown error, so a caller can always safely merge the
 * result with local state without a separate try/catch of its own.
 */
async function fetchRemoteStatuses() {
  try {
    const response = await fetch(SYNC_ENDPOINT, {
      method: "GET",
      cache: "no-store",
      headers: { "x-sync-secret": getSyncSecret() },
    });
    if (!response.ok) return {};
    const body = await response.json();
    return (body && body.statuses) || {};
  } catch {
    return {};
  }
}

/** The real orchestration this session adds, and the only function
 * here that touches localStorage, the network, AND returns a result a
 * caller acts on: pull the Worker's latest map, merge it with
 * whatever's currently local (via mergeStatuses — including any
 * pre-existing local-only history loadJobStatuses() already
 * normalizes forward), save the merged result as this device's new
 * local truth, then push that same merged result back up so the
 * Worker ends up holding the union too, not just whichever side
 * happened to be freshest per job_id. Call this on app load and again
 * whenever the tab regains visibility (see app.js's initSyncSettings)
 * — never on a fixed timer, since this data changes at most a few
 * times a day and polling on an interval would just be unneeded
 * Worker/KV traffic for no real freshness benefit. The push-back is
 * intentionally NOT awaited (see pushStatusesToServer) — only the
 * pull needs to finish before this function can return a real merged
 * result.
 */
async function syncStatuses() {
  const local = loadJobStatuses();
  const remote = await fetchRemoteStatuses();
  const merged = mergeStatuses(local, remote);
  saveJobStatuses(merged);
  pushStatusesToServer(merged);
  return merged;
}

/** A real, honest connectivity check — separate from
 * fetchRemoteStatuses()/pushStatusesToServer() above, which both
 * deliberately fail silently to keep the normal background-sync path
 * (app load, visibility change) simple and never-blocking. This one
 * exists only so the Sync settings UI (app.js's initSyncSettings) can
 * tell a real person "that secret didn't work" instead of quietly
 * pretending everything's fine the same way the background path does
 * on purpose. Returns true only for an actual 2xx response.
 */
async function checkSyncConnection() {
  try {
    const response = await fetch(SYNC_ENDPOINT, {
      method: "GET",
      cache: "no-store",
      headers: { "x-sync-secret": getSyncSecret() },
    });
    return response.ok;
  } catch {
    return false;
  }
}
