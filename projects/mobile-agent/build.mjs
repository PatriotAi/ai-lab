#!/usr/bin/env node
// build.mjs — збирає ОДИН самодостатній HTML для телефону.
// Єдина відповідальність: вбудувати core.js, манифест, іконки й версію в src/app.html.
// Детермінований: однаковий вхід → побайтово однаковий вихід (це перевіряє тест build-sync).
//
// Запуск: node projects/mobile-agent/build.mjs
// Вихід:  projects/mobile-agent/dist/mobile-agent.html + version.json

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = join(HERE, "src");
const DIST = join(HERE, "dist");

// ── PNG-кодер (без залежностей) ────────────────────────────────────────────
const CRC_TABLE = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
})();
function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}
function encodePng(size, pixel) {
  const raw = Buffer.alloc(size * (size * 4 + 1));
  let p = 0;
  for (let y = 0; y < size; y++) {
    raw[p++] = 0; // filter: none
    for (let x = 0; x < size; x++) {
      const [r, g, b, a] = pixel(x, y);
      raw[p++] = r; raw[p++] = g; raw[p++] = b; raw[p++] = a;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8;   // bit depth
  ihdr[9] = 6;   // RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// ── Іконка: лаймовий квадрат зі скругленням + темна «бульбашка» з трьома крапками
const LIME = [212, 255, 79, 255];
const DARK = [11, 13, 15, 255];
const CLEAR = [0, 0, 0, 0];

function inRoundedRect(x, y, size, radius) {
  const max = size - 1;
  const cx = Math.min(Math.max(x, radius), max - radius);
  const cy = Math.min(Math.max(y, radius), max - radius);
  return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2;
}
const inCircle = (x, y, cx, cy, r) => (x - cx) ** 2 + (y - cy) ** 2 <= r * r;
function inTriangle(px, py, a, b, c) {
  const sign = (p1, p2, p3) => (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1]);
  const d1 = sign([px, py], a, b), d2 = sign([px, py], b, c), d3 = sign([px, py], c, a);
  const neg = d1 < 0 || d2 < 0 || d3 < 0;
  const pos = d1 > 0 || d2 > 0 || d3 > 0;
  return !(neg && pos);
}
function iconPixel(size) {
  const s = (f) => f * size;
  const tail = [[s(0.36), s(0.62)], [s(0.30), s(0.82)], [s(0.52), s(0.66)]];
  return (x, y) => {
    if (!inRoundedRect(x, y, size, s(0.22))) return CLEAR;
    const bubble = inCircle(x, y, s(0.5), s(0.46), s(0.28)) || inTriangle(x, y, ...tail);
    if (!bubble) return LIME;
    for (const dx of [0.38, 0.5, 0.62]) if (inCircle(x, y, s(dx), s(0.46), s(0.045))) return LIME;
    return DARK;
  };
}
const iconDataUri = (size) => "data:image/png;base64," + encodePng(size, iconPixel(size)).toString("base64");

// ── Збірка ─────────────────────────────────────────────────────────────────
/**
 * Чиста збірка: читає джерела, повертає готовий HTML. Нічого не пише на диск —
 * тому тест може порівняти результат із тим, що лежить у dist/ (перевірка синхронності).
 */
export function buildHtml() {
const core = readFileSync(join(SRC, "core.js"), "utf8");
const version = (core.match(/export const APP_VERSION\s*=\s*"([^"]+)"/) || [])[1];
if (!version) throw new Error("build: не знайдено APP_VERSION у core.js");

const icon192 = iconDataUri(192);
const icon512 = iconDataUri(512);

const manifest = {
  name: "Кишеньковий агент",
  short_name: "Агент",
  description: "AI-агент, що працює прямо зі смартфона — без ПК і без сервера.",
  start_url: ".",
  scope: ".",
  display: "standalone",
  orientation: "portrait",
  background_color: "#0b0d0f",
  theme_color: "#0b0d0f",
  lang: "uk",
  icons: [
    { src: icon192, sizes: "192x192", type: "image/png", purpose: "any" },
    { src: icon512, sizes: "512x512", type: "image/png", purpose: "any maskable" },
  ],
};
const manifestUri =
  "data:application/manifest+json;base64," + Buffer.from(JSON.stringify(manifest), "utf8").toString("base64");

const inlineCore = core.replace(/^export /gm, "");
const html = readFileSync(join(SRC, "app.html"), "utf8")
  .replace("__CORE__", () => inlineCore.trimEnd())
  .replace(/__MANIFEST_DATA_URI__/g, () => manifestUri)
  .replace(/__ICON192_DATA_URI__/g, () => icon192)
  .replace(/__VERSION__/g, () => version);

for (const left of html.match(/__[A-Z0-9_]+__/g) || []) {
  throw new Error(`build: незаповнений маркер ${left}`);
}
  return { html, version, manifest, manifestUri, icon192, icon512, sw: swSource(version) };
}

/**
 * Джерело service worker. Окремим файлом, бо реєстрація з blob:-URL заборонена
 * браузером (перевірено браузерним прогоном 2026-07-24). Кешує лише оболонку:
 * виклики API, ваги моделі й version.json не кешуються ніколи.
 */
function swSource(version) {
  return `// sw.js — офлайн-оболонка «Кишенькового агента» ${version}. Згенеровано build.mjs.
const CACHE = 'pocket-agent-${version}';
const SKIP = /\\/v1\\/|api\\.|esm\\.run|huggingface|version\\.json/;
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
`;
}

export const DIST_FILE = join(DIST, "mobile-agent.html");
export const SW_FILE = join(DIST, "sw.js");
export const VERSION_FILE = join(HERE, "version.json");

function main() {
  const { html, version, sw } = buildHtml();
  mkdirSync(DIST, { recursive: true });
  writeFileSync(DIST_FILE, html);
  writeFileSync(SW_FILE, sw);
  const versionJson = JSON.stringify(
    { version, notes: "Перший наскрізний зріз: офлайн-режим, нотатки, пошук, PWA.", updated: "2026-07-24" },
    null,
    2,
  ) + "\n";
  writeFileSync(VERSION_FILE, versionJson);
  writeFileSync(join(DIST, "version.json"), versionJson);
  const kb = (Buffer.byteLength(html) / 1024).toFixed(1);
  console.log(`✅ dist/: mobile-agent.html (${kb} КБ) + sw.js + version.json — версія ${version}`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
