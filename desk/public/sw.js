// Rule 1: /api/* is never cached or touched. Rule 2: everything else is network-first, last copy when offline.
// A push carries no text: on a push this worker asks /api/pending (with the access code kept in IndexedDB) what to say.
const VER = "logement-v14";
const SHELL = ["/", "/app.css", "/app.js", "/format.js", "/geo.js", "/fonts/geist.woff2", "/icons/icon-192.png"];

self.addEventListener("install", (e) => { e.waitUntil(caches.open(VER).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener("activate", (e) => { e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VER).map((k) => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener("fetch", (e) => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin || u.pathname.startsWith("/api/")) return;
  e.respondWith(fetch(r).then((res) => { if (res.ok) { const copy = res.clone(); caches.open(VER).then((c) => c.put(r, copy)); } return res; })
    .catch(() => caches.match(r).then((m) => m || (r.mode === "navigate" ? caches.match("/") : Response.error()))));
});

function readToken() {
  return new Promise((resolve) => {
    const open = indexedDB.open("desk", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("kv");
    open.onerror = () => resolve("");
    open.onsuccess = () => { const g = open.result.transaction("kv").objectStore("kv").get("token"); g.onsuccess = () => resolve(g.result || ""); g.onerror = () => resolve(""); };
  });
}

self.addEventListener("push", (e) => {
  e.waitUntil((async () => {
    let body = "A new flat matches", url = "/";
    try {
      const token = await readToken();
      { const r = await fetch("/api/pending", { headers: token ? { "x-token": token } : {}, cache: "no-store" }); if (r.ok) { const p = await r.json(); if (p.body) body = p.body; if (typeof p.url === "string") url = p.url; } }
    } catch (err) { /* keep the generic line */ }
    await self.registration.showNotification("Logement", { body, icon: "/icons/icon-192.png", badge: "/icons/icon-192.png", tag: "logement", renotify: true, data: { url } });
  })());
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(url.startsWith("https://") ? self.clients.openWindow(url) : self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((ws) => { for (const w of ws) { if ("focus" in w) return w.focus(); } return self.clients.openWindow("/"); }));
});
