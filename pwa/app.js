"use strict";

/**
 * TheScanner PWA — read-only real-data screen (Session 15).
 *
 * Deliberately minimal: fetch the two JSON exports Session 14 already
 * builds (latest_scan.json, usage_summary.json) and render them. No role
 * selection, no "mark as applied", no theme persistence, no Web Push, no
 * manual-trigger button — all explicitly deferred to a later session so
 * this one only has to prove "real data on a real screen" works, without
 * any interactivity to also get right at the same time.
 */

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

function renderBudget(usage) {
  const fill = document.getElementById("budget-bar-fill");
  const numbers = document.getElementById("budget-numbers");
  const note = document.getElementById("budget-note");

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
}

function jobCardHTML(job) {
  const badgeLabel = job.scan_status === "new" ? "New" : "Still open";
  return `
    <div class="job-card">
      <div class="job-card-top">
        <div>
          <p class="job-title">${escapeHTML(job.title)}</p>
          <p class="job-meta">${escapeHTML(job.company)} — ${escapeHTML(job.location || "")}</p>
        </div>
        <span class="badge ${job.scan_status}">${badgeLabel}</span>
      </div>
      <span class="role-tag">${escapeHTML(job.role_category)}</span>
      <div>
        <a class="apply-link" href="${escapeAttribute(job.source_url)}" target="_blank" rel="noopener noreferrer">Apply →</a>
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

  const groups = [
    { status: "new", heading: "🆕 New" },
    { status: "still_open", heading: "📌 Still open" },
  ];

  container.innerHTML = groups
    .map((group) => {
      const jobs = scan.matches.filter((m) => m.scan_status === group.status);
      if (jobs.length === 0) return "";
      return `
        <div class="job-group">
          <h2>${group.heading} (${jobs.length})</h2>
          ${jobs.map(jobCardHTML).join("")}
        </div>`;
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

    document.getElementById("generated-at").textContent = formatGeneratedAt(scan.generated_at);
    renderSummaryStrip(scan);
    renderBudget(usage);
    renderJobGroups(scan);
  } catch (err) {
    renderError(`Couldn't load scan data: ${err.message}`);
  }
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

/** Cycles the corner mascot through its 4 captured flight-pose frames on a
 * simple interval — a lightweight stand-in for a real flap animation
 * without shipping a video/GIF. */
function initMascotAnimation() {
  const frame = document.getElementById("mascot-frame");
  let pose = 1;
  setInterval(() => {
    pose = (pose % 4) + 1;
    frame.src = `bat-frame-${pose}.png`;
  }, 500);
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("service-worker.js").catch((err) => {
      console.warn("Service worker registration failed:", err);
    });
  }
}

initThemeToggle();
initMascotAnimation();
registerServiceWorker();
main();
