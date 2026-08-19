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
 * - application_status ("applied"/not) per job_id.
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
const APPLIED_JOBS_KEY = "thescanner:applied_jobs";

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

/** Read this device's stored applied/not-applied marks.
 *
 * Shape: { [job_id]: true }. Absence of a key means not_applied — same
 * "don't store the default state" reasoning as loadRoleFilters above.
 */
function loadAppliedJobs() {
  try {
    const raw = localStorage.getItem(APPLIED_JOBS_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveAppliedJobs(appliedMap) {
  localStorage.setItem(APPLIED_JOBS_KEY, JSON.stringify(appliedMap));
}

function isApplied(jobId, appliedMap) {
  return appliedMap[jobId] === true;
}

/** Toggle one job's applied state. Pure — returns a new object, never
 * mutates `appliedMap`. Deletes the key on toggling back to
 * not_applied rather than storing an explicit `false`, for the same
 * "don't persist the default state" reason as toggleRoleFilter.
 */
function toggleApplied(jobId, appliedMap) {
  const next = { ...appliedMap };
  if (isApplied(jobId, appliedMap)) {
    delete next[jobId];
  } else {
    next[jobId] = true;
  }
  return next;
}
