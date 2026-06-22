// Ufind Marketplace — Service Worker
const CACHE_NAME = 'ufind-v1';

// Assets to pre-cache on install (shell)
const PRECACHE_URLS = [
  '/',
  '/static/images/icon-192.png',
  '/static/images/icon-512.png',
];

// ── Install ──────────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

// ── Activate ─────────────────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ── Fetch — Network-first, fall back to cache ─────────────────────────────────
self.addEventListener('fetch', (event) => {
  // Only handle GET requests and same-origin or static assets
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Skip non-http(s) requests (chrome-extension, etc.)
  if (!url.protocol.startsWith('http')) return;

  event.respondWith(
    fetch(event.request)
      .then((networkResponse) => {
        // Cache static assets (images, CSS, JS) on the fly
        if (url.pathname.startsWith('/static/')) {
          const clone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return networkResponse;
      })
      .catch(() => {
        // On failure, serve from cache
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          // If it's a navigation request and we have the root cached, serve that
          if (event.request.mode === 'navigate') {
            return caches.match('/');
          }
        });
      })
  );
});
