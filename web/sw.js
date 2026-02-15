/**
 * Service Worker for Scriptum Reader
 *
 * Provides offline caching for:
 * - Core app files (HTML, CSS, JS)
 * - Audio files (cached on-demand)
 */

const STATIC_CACHE = 'scriptum-static-v3';
const AUDIO_CACHE = 'scriptum-audio-v1';

// Static files to cache on install (paths relative to /web/ scope)
const STATIC_FILES = [
    './',
    './library.html',
    './library.css',
    './library.js',
    './reader.html',
    './reader.js',
    './reader-text.html',
    './reader-text.js',
    './reader-text.css',
    './styles.css',
    './manifest.json',
    './icon-512.png'
];

// Install event - cache static files
self.addEventListener('install', (event) => {
    console.log('[SW] Installing service worker...');

    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then((cache) => {
                console.log('[SW] Caching static files');
                return cache.addAll(STATIC_FILES);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating service worker...');

    const VALID_CACHES = [STATIC_CACHE, AUDIO_CACHE];

    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (!VALID_CACHES.includes(cacheName)) {
                        console.log('[SW] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Only handle same-origin http/https requests
    if (!url.protocol.startsWith('http')) {
        return;
    }

    // Handle audio files differently - cache on first request
    if (isAudioFile(url.pathname)) {
        event.respondWith(cacheFirstAudio(event.request));
        return;
    }

    // For other files, try network first, fallback to cache
    event.respondWith(networkFirstStatic(event.request));
});

function isAudioFile(pathname) {
    return pathname.match(/\.(wav|mp3|m4a|ogg|webm)$/i);
}

/**
 * Cache-first strategy for audio files
 */
async function cacheFirstAudio(request) {
    const cache = await caches.open(AUDIO_CACHE);
    const cached = await cache.match(request);

    if (cached) {
        return cached;
    }

    try {
        const response = await fetch(request);
        if (response.ok) {
            try {
                await cache.put(request, response.clone());
            } catch (cacheError) {
                console.warn('[SW] Failed to cache audio:', request.url, cacheError);
            }
        }
        return response;
    } catch (error) {
        console.error('[SW] Audio fetch failed:', error);
        return new Response('Audio not available offline', {
            status: 503,
            headers: { 'Content-Type': 'text/plain' }
        });
    }
}

/**
 * Network-first strategy for static files.
 * Returns network response directly (including 404s).
 * Only falls back to cache on true network failure (offline).
 */
async function networkFirstStatic(request) {
    try {
        const response = await fetch(request);

        // Cache successful responses for offline use
        if (response.ok) {
            try {
                const cache = await caches.open(STATIC_CACHE);
                await cache.put(request, response.clone());
            } catch (cacheError) {
                console.warn('[SW] Failed to cache:', request.url, cacheError);
            }
        }

        // Return the network response as-is (including 404, 500, etc.)
        return response;
    } catch (error) {
        // Network truly failed (offline) — try cache
        console.log('[SW] Network failed, trying cache:', request.url);
        const cached = await caches.match(request);
        if (cached) {
            return cached;
        }

        // For navigation requests, fall back to library page
        if (request.mode === 'navigate') {
            const fallback = await caches.match('./library.html');
            if (fallback) return fallback;
        }

        return new Response('Offline', {
            status: 503,
            headers: { 'Content-Type': 'text/plain' }
        });
    }
}

// Handle messages from the main app
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'CACHE_AUDIO') {
        const urls = event.data.urls;
        caches.open(AUDIO_CACHE).then((cache) => {
            urls.forEach((url) => {
                fetch(url).then((response) => {
                    if (response.ok) {
                        cache.put(url, response);
                    }
                });
            });
        });
    }

    if (event.data && event.data.type === 'CLEAR_AUDIO_CACHE') {
        caches.delete(AUDIO_CACHE).then(() => {
            console.log('[SW] Audio cache cleared');
        });
    }
});
