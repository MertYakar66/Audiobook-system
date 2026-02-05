/**
 * Service Worker for Read-Along Reader
 * 
 * Provides offline caching for:
 * - Core app files (HTML, CSS, JS)
 * - Audio files (cached on-demand)
 */

const CACHE_NAME = 'readalong-v1';
const STATIC_CACHE = 'readalong-static-v1';
const AUDIO_CACHE = 'readalong-audio-v1';

// Static files to cache on install
const STATIC_FILES = [
    '/index.html',
    '/styles.css',
    '/reader.js',
    '/manifest.json'
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

    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== STATIC_CACHE && cacheName !== AUDIO_CACHE) {
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

    // Handle audio files differently - cache on first request
    if (isAudioFile(url.pathname)) {
        event.respondWith(cacheFirstAudio(event.request));
        return;
    }

    // For other files, try network first, fallback to cache
    event.respondWith(networkFirstStatic(event.request));
});

/**
 * Check if URL is an audio file
 */
function isAudioFile(pathname) {
    return pathname.match(/\.(wav|mp3|m4a|ogg|webm)$/i);
}

/**
 * Cache-first strategy for audio files
 * - Serves from cache if available
 * - Otherwise fetches from network and caches
 */
async function cacheFirstAudio(request) {
    const cache = await caches.open(AUDIO_CACHE);
    const cached = await cache.match(request);

    if (cached) {
        console.log('[SW] Serving audio from cache:', request.url);
        return cached;
    }

    try {
        const response = await fetch(request);

        // Only cache successful responses
        if (response.ok) {
            console.log('[SW] Caching audio file:', request.url);
            cache.put(request, response.clone());
        }

        return response;
    } catch (error) {
        console.error('[SW] Audio fetch failed:', error);
        // Return a custom offline audio response or error
        return new Response('Audio not available offline', { status: 503 });
    }
}

/**
 * Network-first strategy for static files
 * - Tries network first
 * - Falls back to cache if offline
 */
async function networkFirstStatic(request) {
    try {
        const response = await fetch(request);

        // Update cache with fresh response
        if (response.ok) {
            const cache = await caches.open(STATIC_CACHE);
            cache.put(request, response.clone());
        }

        return response;
    } catch (error) {
        console.log('[SW] Network failed, trying cache:', request.url);
        const cached = await caches.match(request);

        if (cached) {
            return cached;
        }

        // For navigation requests, return index.html
        if (request.mode === 'navigate') {
            return caches.match('/index.html');
        }

        return new Response('Offline', { status: 503 });
    }
}

// Handle messages from the main app
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'CACHE_AUDIO') {
        // Pre-cache specific audio files
        const urls = event.data.urls;
        caches.open(AUDIO_CACHE).then((cache) => {
            urls.forEach((url) => {
                fetch(url).then((response) => {
                    if (response.ok) {
                        cache.put(url, response);
                        console.log('[SW] Pre-cached audio:', url);
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
