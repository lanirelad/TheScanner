"use strict";

/**
 * TheScanner PWA service worker (Session 15).
 *
 * Two deliberately different caching strategies, per the task's own
 * requirement — not the same strategy applied everywhere for simplicity:
 *
 * - The two JSON data files (latest_scan.json, usage_summary.json) are
 *   network-first: a fresh scan can land at any time, and showing stale
 *   job matches or a stale budget percentage while online would be a
 *   correctness problem, not just a UX nitpick. Falls back to the last
 *   cached copy only when the network request itself fails (offline).
 * - Everything else (the shell — index.html, styles.css, app.js,
 *   manifest.json, icons, the mascot image) is cache-first: none of it
 *   changes between deploys in a way that matters if it's a request or
 *   two stale, and cache-first is what makes the shell open instantly
 *   offline, which is the entire point of it being a PWA at all.
 */

const CACHE_NAME = "thescanner-shell-v4";
const DATA_FILES = ["latest_scan.json", "usage_summary.json"];

const SHELL_FILES = [
  "./",
  "index.html",
  "styles.css",
  "preferences.js",
  "app.js",
  "manifest.json",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "real_mascot.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  // Session 27: was already present here since Session 15, but flagging
  // it rather than assuming it's what fixed the real "needs a hard
  // refresh to see a deploy" bug Elad hit — skipWaiting() alone doesn't
  // hand control of already-open tabs to the new worker; that's what
  // clients.claim() below is for, and it wasn't correctly awaited.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  // Session 27: clients.claim() was already being called here, but not
  // wrapped in its own event.waitUntil — the browser is free to consider
  // "activate" finished (and potentially recycle this worker) as soon as
  // the cache-cleanup waitUntil above settles, without ever waiting for
  // claim() to actually finish handing control of already-open tabs to
  // this new worker. Each event.waitUntil() call independently extends
  // the event's lifetime, so this is a second one, not a replacement for
  // the cache-cleanup line above.
  event.waitUntil(self.clients.claim());
});

function isDataFileRequest(url) {
  return DATA_FILES.some((file) => url.pathname.endsWith(file));
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    const cache = await caches.open(CACHE_NAME);
    cache.put(request, response.clone());
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw err;
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  const cache = await caches.open(CACHE_NAME);
  cache.put(request, response.clone());
  return response;
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (isDataFileRequest(url)) {
    event.respondWith(networkFirst(event.request));
  } else {
    event.respondWith(cacheFirst(event.request));
  }
});
