// This root-scope service worker exists only to replace and unregister
// any stale service worker previously registered at the "/" scope.
// The real service worker lives at /web/sw.js with scope /web/.

self.addEventListener('install', () => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        // Clear any caches left by the old root SW
        caches.keys().then((names) =>
            Promise.all(names.map((name) => caches.delete(name)))
        ).then(() => self.clients.claim())
         .then(() => self.registration.unregister())
    );
});

// Do NOT intercept any fetches — pass everything through to the network
