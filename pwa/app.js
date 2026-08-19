"use strict";

/**
 * TheScanner PWA — real-data screen (Session 15) with local-only role
 * selection (Session 28) and a tri-state per-job status — not_set /
 * applied / ignored (Session 28's applied/not-applied, extended with
 * "ignored" in Session 30) — per ADR-0011/ADR-0014.
 *
 * Fetches the two JSON exports run.py builds (latest_scan.json,
 * usage_summary.json) and renders them. Role-category filtering and
 * per-job status both live entirely in this device's localStorage via
 * preferences.js (loaded before this file, see index.html) — they
 * never change what's fetched, never write anywhere the backend can see,
 * and are recomputed fresh from `currentScan` on every toggle rather
 * than persisted as rendered HTML. Still explicitly deferred: theme
 * persistence, Web Push, the manual-trigger button.
 */

// Session 28: the most recently fetched scan, kept so the delegated
// toggle/apply-button handlers below can re-render the job list after a
// localStorage change without re-fetching — the data itself hasn't
// changed, only which of it this device currently wants to see.
let currentScan = null;

const DATA_URLS = {
  latestScan: "latest_scan.json",
  usageSummary: "usage_summary.json",
};

async function loadJSON(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${url} responded ${response.status}`);
  }
  return response.json();
}

function formatGeneratedAt(isoTimestamp) {
  // latest_scan.json's generated_at is already ISO8601 UTC (run.py) — just
  // render it in the viewer's local time rather than reformatting by hand.
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) return isoTimestamp;
  return `Last scanned ${date.toLocaleString()}`;
}

function renderSummaryStrip(scan) {
  const strip = document.getElementById("summary-strip");
  const tiles = [
    { label: "Attempted", value: scan.companies_attempted, cls: "" },
    { label: "Succeeded", value: scan.companies_succeeded, cls: "" },
    { label: "Failed", value: scan.companies_failed, cls: scan.companies_failed > 0 ? "failed" : "" },
  ];
  strip.innerHTML = tiles
    .map(
      (t) => `
      <div class="summary-tile ${t.cls}">
        <div class="value">${t.value}</div>
        <div class="label">${t.label}</div>
      </div>`
    )
    .join("");
}

/** Session 31: the bare Failed count above tells you *that* something
 * broke but not *what* — latest_scan.json's `failures` list (Session 18)
 * has always carried the real company + error text, just never rendered.
 * A native <details> disclosure (see index.html) rather than custom
 * expand/collapse JS — it's free accessibility and keyboard support for
 * something that's genuinely optional detail, not primary content.
 * Hidden outright on a clean scan rather than shown empty.
 */
function renderFailures(scan) {
  const detail = document.getElementById("failures-detail");
  const summary = document.getElementById("failures-summary");
  const list = document.getElementById("failures-list");
  const failures = scan.failures || [];

  if (failures.length === 0) {
    detail.hidden = true;
    return;
  }

  detail.hidden = false;
  summary.textContent = `Failure details (${failures.length})`;
  list.innerHTML = failures
    .map(
      (f) => `
      <li>
        <span class="failure-company">${escapeHTML(f.company)}</span>
        <span class="failure-error">${escapeHTML(f.error)}</span>
      </li>`
    )
    .join("");
}

function renderBudget(usage) {
  const fill = document.getElementById("budget-bar-fill");
  const numbers = document.getElementById("budget-numbers");
  const note = document.getElementById("budget-note");
  const reset = document.getElementById("budget-reset");

  // percent_used is deliberately not clamped by usage/budget.py — going
  // over 100% is the real signal. The bar's own width IS visually capped
  // at 100% (a bar can't render past its track), but the "over-cap" class
  // and the printed number both still show the true, uncapped value.
  const percent = usage.percent_used;
  const barWidth = Math.min(percent, 100);
  fill.style.width = `${barWidth}%`;
  fill.classList.toggle("over-cap", percent > 100);

  numbers.innerHTML = `
    <span>${usage.minutes_used_this_month.toFixed(2)} / ${usage.minutes_cap} min</span>
    <span>${percent.toFixed(2)}%</span>
  `;

  if (usage.includes_checkin_overhead === false) {
    note.textContent =
      "Note: does not yet include the workflow's hourly check-in cost (only logged real scans count).";
  } else {
    note.textContent = "";
  }

  // Session 31: days_until_reset comes pre-computed from usage/budget.py
  // (same reset_day_of_month it used), not recalculated here — this file
  // has no business knowing GitHub's real billing-cycle day for Elad's
  // account, only displaying what the backend already resolved it to.
  if (typeof usage.days_until_reset === "number") {
    const label = usage.days_until_reset === 0 ? "Resets today" : `Resets in ${usage.days_until_reset} day${usage.days_until_reset === 1 ? "" : "s"}`;
    reset.textContent = `${label} (day ${usage.reset_day_of_month} of the month)`;
  } else {
    reset.textContent = "";
  }
}

function jobCardHTML(job, statuses) {
  const badgeLabel = job.scan_status === "new" ? "New" : "Still open";
  const applied = isApplied(job.job_id, statuses);
  const ignored = isIgnored(job.job_id, statuses);
  return `
    <div class="job-card ${applied ? "applied" : ""} ${ignored ? "ignored" : ""}">
      <div class="job-card-top">
        <div>
          <p class="job-title">${escapeHTML(job.title)}</p>
          <p class="job-meta">${escapeHTML(job.company)} — ${escapeHTML(job.location || "")}</p>
        </div>
        <span class="badge ${job.scan_status}">${badgeLabel}</span>
      </div>
      <span class="role-tag">${escapeHTML(job.label_en || job.role_category)}</span>
      <div class="job-card-actions">
        <a class="apply-link" href="${escapeAttribute(job.source_url)}" target="_blank" rel="noopener noreferrer">Apply →</a>
        <div class="job-card-buttons">
          <button type="button" class="mark-applied-btn" data-job-id="${escapeAttribute(job.job_id)}">
            ${applied ? "✓ Applied" : "Mark as applied"}
          </button>
          <button type="button" class="mark-ignored-btn" data-job-id="${escapeAttribute(job.job_id)}">
            ${ignored ? "🙈 Ignored" : "Ignore"}
          </button>
        </div>
      </div>
    </div>`;
}

function escapeHTML(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function escapeAttribute(value) {
  return (value ?? "").replace(/"/g, "&quot;");
}

function renderJobGroups(scan) {
  const container = document.getElementById("job-groups");

  if (scan.matches.length === 0) {
    container.innerHTML = '<p class="empty-state">No matches in the current scan.</p>';
    return;
  }

  // Session 28: client-side only — a job filtered out here is still in
  // `scan.matches`, still fetched, just not rendered. This never touches
  // roles.json or run.py; it's a display filter on top of data the
  // backend already decided to include (see preferences.js's
  // isRoleEnabled for why "no stored preference" defaults to showing
  // everything the backend already returned).
  const filters = loadRoleFilters();
  const visibleMatches = scan.matches.filter((job) => shouldShowJob(job, filters));

  if (visibleMatches.length === 0) {
    container.innerHTML = '<p class="empty-state">No matches for the roles you’ve selected — try enabling more above.</p>';
    return;
  }

  const statuses = loadJobStatuses();
  // Session 30: ignored jobs are pulled out of their normal new/
  // still_open grouping entirely and rendered in their own section at
  // the bottom instead. Applied jobs are NOT partitioned here — they
  // stay in `active`, same position and grouping as always, only
  // visually marked (jobCardHTML) — this is deliberately narrower than
  // Session 28's role-category filter, which hides jobs outright.
  const { active, ignored } = partitionByIgnored(visibleMatches, statuses);

  const groups = [
    { status: "new", heading: "🆕 New" },
    { status: "still_open", heading: "📌 Still open" },
  ];

  let html = groups
    .map((group) => {
      const jobs = active.filter((m) => m.scan_status === group.status);
      if (jobs.length === 0) return "";
      return `
        <div class="job-group">
          <h2>${group.heading} (${jobs.length})</h2>
          ${jobs.map((job) => jobCardHTML(job, statuses)).join("")}
        </div>`;
    })
    .join("");

  if (ignored.length > 0) {
    html += `
      <div class="job-group job-group-ignored">
        <h2>🙈 Ignored (${ignored.length})</h2>
        ${ignored.map((job) => jobCardHTML(job, statuses)).join("")}
      </div>`;
  }

  container.innerHTML = html;
}

/** One toggle per role category actually worth showing a control for
 * (see preferences.js's availableRoleCategories) — never fetches or
 * duplicates roles.json itself, since every category here already came
 * from data the backend already decided to include. Hides the whole
 * section rather than rendering an empty "Show roles" heading when
 * there's nothing to toggle yet (e.g. a scan with zero matches at all).
 */
function renderRoleFilters(scan) {
  const section = document.getElementById("role-filters");
  const container = document.getElementById("role-filter-toggles");
  const filters = loadRoleFilters();
  const categories = availableRoleCategories(scan.matches, filters);

  if (categories.length === 0) {
    section.hidden = true;
    return;
  }
  section.hidden = false;

  container.innerHTML = categories
    .map(({ role_category, label }) => {
      const checked = isRoleEnabled(role_category, filters);
      return `
        <label class="role-filter-toggle">
          <input type="checkbox" data-role-category="${escapeAttribute(role_category)}" ${checked ? "checked" : ""} />
          ${escapeHTML(label)}
        </label>`;
    })
    .join("");
}

function renderError(message) {
  document.getElementById("job-groups").innerHTML = `<p class="error-state">${escapeHTML(message)}</p>`;
}

async function main() {
  try {
    const [scan, usage] = await Promise.all([
      loadJSON(DATA_URLS.latestScan),
      loadJSON(DATA_URLS.usageSummary),
    ]);

    currentScan = scan;
    document.getElementById("generated-at").textContent = formatGeneratedAt(scan.generated_at);
    renderSummaryStrip(scan);
    renderFailures(scan);
    renderBudget(usage);
    renderRoleFilters(scan);
    renderJobGroups(scan);
  } catch (err) {
    renderError(`Couldn't load scan data: ${err.message}`);
  }
}

/** Delegated (not per-checkbox) so re-rendering #role-filter-toggles on
 * every scan load never needs to re-attach listeners. Guards on
 * `currentScan` being loaded — a click can't reach a checkbox that
 * renderRoleFilters() never rendered, but the guard is cheap and honest
 * about the real dependency rather than assuming ordering. */
function initRoleFilterToggles() {
  document.getElementById("role-filter-toggles").addEventListener("change", (event) => {
    const checkbox = event.target.closest("input[data-role-category]");
    if (!checkbox || !currentScan) return;
    saveRoleFilters(toggleRoleFilter(checkbox.dataset.roleCategory, loadRoleFilters()));
    renderJobGroups(currentScan);
  });
}

/** Delegated on #job-groups for the same reason — job cards are
 * rebuilt wholesale on every renderJobGroups() call, so a listener
 * bound to one button's DOM node would be lost on the very next
 * re-render. Handles both status buttons here rather than two separate
 * listeners, since they share the same "load statuses, toggle one
 * job_id, save, re-render" shape and the same container. */
function initJobActionButtons() {
  document.getElementById("job-groups").addEventListener("click", (event) => {
    const applyBtn = event.target.closest(".mark-applied-btn");
    const ignoreBtn = event.target.closest(".mark-ignored-btn");
    if ((!applyBtn && !ignoreBtn) || !currentScan) return;

    const statuses = loadJobStatuses();
    const jobId = (applyBtn || ignoreBtn).dataset.jobId;
    const next = applyBtn ? toggleApplied(jobId, statuses) : toggleIgnored(jobId, statuses);
    saveJobStatuses(next);
    renderJobGroups(currentScan);
  });
}

/** Theme toggle — cosmetic only this session, per scope: resets to dark
 * on every reload, no localStorage persistence yet (deferred). */
function initThemeToggle() {
  const button = document.getElementById("theme-toggle");
  button.addEventListener("click", () => {
    const isLight = document.documentElement.getAttribute("data-theme") === "light";
    if (isLight) {
      document.documentElement.removeAttribute("data-theme");
      button.textContent = "🌙 Dark";
    } else {
      document.documentElement.setAttribute("data-theme", "light");
      button.textContent = "☀️ Light";
    }
  });
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("service-worker.js").catch((err) => {
      console.warn("Service worker registration failed:", err);
    });
  }
}

initThemeToggle();
initRoleFilterToggles();
initJobActionButtons();
registerServiceWorker();
main();
