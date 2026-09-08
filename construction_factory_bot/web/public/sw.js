/*
 * Service Worker — PWA (TZ: "Mobil versiya (PWA) — sayt mobil telefonda
 * ilova kabi ishlaydi, offline rejimda katalog va buyurtma saqlaydi").
 *
 * Strategiya: network-first — tarmoq mavjud bo'lsa har doim yangi ma'lumot,
 * tarmoq uzilganda esa oxirgi saqlangan nusxa (offline rejim).
 */
const CACHE_NAME = "construction-crm-v1";
const SHELL = ["/", "/index.html", "/style.css", "/app.js", "/app_v5.js", "/manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL).catch(() => null))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  // API so'rovlari keshlanmaydi — har doim yangi ma'lumot kerak
  if (url.pathname.startsWith("/api/") || url.pathname === "/health") return;

  event.respondWith(
    fetch(req)
      .then((res) => {
        // Muvaffaqiyatli javobni keshlab qo'yamiz (offline uchun)
        const copy = res.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(req, copy)).catch(() => null);
        return res;
      })
      .catch(() =>
        caches.match(req).then((cached) => cached || caches.match("/index.html"))
      )
  );
});