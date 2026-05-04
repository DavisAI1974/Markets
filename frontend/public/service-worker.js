/**
 * markets-watch service worker.
 * Strategy: cache-first for app shell (HTML/JS/CSS), network-first for /api/*.
 * Future: handle web push notifications for high-confidence signals.
 */

const APP_CACHE = "markets-watch-v1";
const SHELL = ["/", "/index.html", "/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(APP_CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== APP_CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Always go network for API + SSE
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(event.request).catch(() => new Response("offline", { status: 503 })));
    return;
  }
  // Cache-first for app shell
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request).then((res) => {
      if (res.ok && event.request.method === "GET") {
        const clone = res.clone();
        caches.open(APP_CACHE).then((cache) => cache.put(event.request, clone));
      }
      return res;
    }).catch(() => caches.match("/")))
  );
});

// Web Push placeholder; activate when push subscriptions are wired
self.addEventListener("push", (event) => {
  const data = event.data ? event.data.json() : { title: "markets-watch", body: "new signal" };
  event.waitUntil(self.registration.showNotification(data.title || "markets-watch", {
    body: data.body || "",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    tag: data.tag || "signal",
  }));
});
