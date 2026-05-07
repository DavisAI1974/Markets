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

// Web Push: incoming notification from backend.send_to_all
self.addEventListener("push", (event) => {
  let data = { title: "markets-watch", body: "new signal" };
  try { data = event.data ? event.data.json() : data; } catch { /* malformed */ }
  const opts = {
    body: data.body || "",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    tag: data.tag || "signal",
    data: { url: data.url || "/", signal_id: data.signal_id || null },
    requireInteraction: !!data.cascade_event,  // cascade events stay until tapped
    vibrate: data.cascade_event ? [200, 100, 200] : [100],
  };
  event.waitUntil(
    self.registration.showNotification(data.title || "markets-watch", opts)
  );
});

// Notification tap: focus existing tab if open, else open a new one to the
// signal detail (or root).
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.signal_id)
    ? `/signal/${event.notification.data.signal_id}`
    : "/";
  event.waitUntil((async () => {
    const all = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const c of all) {
      if (c.url.includes(self.location.origin)) {
        await c.focus();
        try { await c.navigate(target); } catch { /* detached / cross-origin */ }
        return;
      }
    }
    await self.clients.openWindow(target);
  })());
});
