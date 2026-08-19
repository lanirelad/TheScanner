"use strict";

/**
 * Local-only device preferences (Session 28, ADR-0011/ADR-0014).
 *
 * Two things live here, both stored in this device's own localStorage
 * and NEVER sent anywhere — no backend field, no run.py write path, no
 * shared-repo file:
 *
 * - Which role categories this device wants to see (a client-side
 *   display filter on top of latest_scan.json's matches — it does not
 *   change what roles.json/the backend scan looks for at all).
 * - Per-job local status: not_set / applied / ignored (Session 30
 *   extended this from Session 28's plain applied/not-applied boolean —
 *   see JOB_STATUS_KEY below for the migration story).
 *
 * Deliberately a separate file from app.js, not just a separate
 * section of it: app.js's bottom section calls main()/initThemeToggle()/
 * registerServiceWorker() immediately on load, which needs a real DOM
 * and successfully-fetchable JSON to run without throwing. Every
 * function in *this* file is a pure function or a thin localStorage
 * wrapper — no DOM access, no network, no side effect on load — so it
 * can be loaded and tested on its own (see pwa/tests/preferences.test.html)
 * without ever touching app.js's bootstrap at all. This project has no
 * Node.js-based JS test runner (none existed before this session, and
 * this sandbox has no Node.js installed at all) — the test harness runs
 * these functions directly in a real browser instead, which is exactly
 * the environment this code actually runs in anyway.
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

/** Session 30's tri-state key. Shape: { [job_id]: "applied" | "ignored" }.
 * No stored "not_set" value — same "don't persist the default state"
 * reasoning as ROLE_FILTERS_KEY above; absence of a key (in both this
 * key and the legacy one) means not_set. */
const JOB_STATUS_KEY = "thescanner:job_status";

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

/** Read this device's per-job statuses, migrating Session 28's legacy
 * key forward on every read rather than as a one-time destructive
 * migration step — simpler, and there's no window where a read could
 * observe a half-migrated state, since nothing is ever deleted.
 *
 * A legacy `true` entry is only honored when the new key has no opinion
 * for that job_id at all — once a job has been explicitly touched under
 * the new tri-state model (including being explicitly toggled back to
 * not_set, i.e. deleted from the new key), the legacy entry is
 * permanently superseded for that job_id. In practice this means: an
 * old "applied" mark keeps showing as applied until the user interacts
 * with that specific job again, at which point it's fully governed by
 * the new key from then on.
 */
function loadJobStatuses() {
  const legacy = _readJSON(LEGACY_APPLIED_JOBS_KEY);
  const current = _readJSON(JOB_STATUS_KEY);
  const merged = {};
  for (const jobId of Object.keys(legacy)) {
    if (legacy[jobId] === true) {
      merged[jobId] = JOB_STATUS.APPLIED;
    }
  }
  Object.assign(merged, current);
  return merged;
}

function saveJobStatuses(statuses) {
  localStorage.setItem(JOB_STATUS_KEY, JSON.stringify(statuses));
}

function getJobStatus(jobId, statuses) {
  return statuses[jobId] || JOB_STATUS.NOT_SET;
}

function isApplied(jobId, statuses) {
  return getJobStatus(jobId, statuses) === JOB_STATUS.APPLIED;
}

function isIgnored(jobId, statuses) {
  return getJobStatus(jobId, statuses) === JOB_STATUS.IGNORED;
}

/** Set one job's status outright. Pure — returns a new object, never
 * mutates `statuses`. Deletes the key for NOT_SET rather than storing
 * it explicitly, same "don't persist the default state" reasoning as
 * toggleRoleFilter. This is the one place that enforces the tri-state's
 * mutual exclusivity: setting a job to any status always fully replaces
 * whatever it was before — there is no code path that could leave a
 * job marked both applied and ignored at once.
 */
function setJobStatus(jobId, statuses, newStatus) {
  const next = { ...statuses };
  if (newStatus === JOB_STATUS.NOT_SET) {
    delete next[jobId];
  } else {
    next[jobId] = newStatus;
  }
  return next;
}

/** Toggle one job between APPLIED and NOT_SET. If the job was IGNORED,
 * this moves it straight to APPLIED (not NOT_SET) — clicking "Mark as
 * applied" is a real statement of intent about this specific status,
 * not a blind toggle of whatever was there before.
 */
function toggleApplied(jobId, statuses) {
  const next = isApplied(jobId, statuses) ? JOB_STATUS.NOT_SET : JOB_STATUS.APPLIED;
  return setJobStatus(jobId, statuses, next);
}

/** Toggle one job between IGNORED and NOT_SET — same "was it already
 * applied? then move straight to ignored" reasoning as toggleApplied.
 */
function toggleIgnored(jobId, statuses) {
  const next = isIgnored(jobId, statuses) ? JOB_STATUS.NOT_SET : JOB_STATUS.IGNORED;
  return setJobStatus(jobId, statuses, next);
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
