self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open('jarvis-v1').then((cache) => cache.addAll([
      '/',
      '/static/manifest.json',
      '/static/icon-192.png',
      '/static/icon-512.png'
    ]))
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
