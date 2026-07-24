// sw.js — офлайн-оболонка «Кишенькового агента» 0.1.0. Згенеровано build.mjs.
const CACHE = 'pocket-agent-0.1.0';
const SKIP = /\/v1\/|api\.|esm\.run|huggingface|version\.json/;
self.addEventListener('install', e => { self.skipWaiting(); });
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || SKIP.test(e.request.url)) return;
  e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request).then(res => {
    const copy = res.clone();
    caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {});
    return res;
  })));
});
