// Service worker: keeps the whole app and its ML models on the phone so it runs with no Mac and
// no network after the first load. App files are served from the cache and refreshed in the
// background when the Mac happens to be reachable; models never change, so they stay cached.
const VERSION = "rover-v6";
const TILES = "rover-tiles";                         // OpenStreetMap tiles seen on the phone
const TILE_MAX = 4000;
const APP = ["./", "manifest.webmanifest", "icon.svg", "js/core.js", "js/camera.js", "js/obstacles.js", "js/yolo.js", "js/cvision.js", "js/path.js",
             "js/planner.js", "js/nav.js", "js/map.js", "js/recorder.js", "js/app.js", "js/calib.js"];
const VENDOR = ["vendor/tf.min.js", "vendor/opencv.js", "vendor/leaflet/leaflet.js", "vendor/leaflet/leaflet.css", "vendor/tf-backend-wasm.min.js", "vendor/coco-ssd.min.js",
                "vendor/ort/ort.webgpu.min.js", "vendor/ort/ort-wasm-simd-threaded.jsep.mjs", "vendor/ort/ort-wasm-simd-threaded.jsep.wasm",
                "vendor/models/yolo11n/yolo11n.onnx",
                "vendor/tfjs-backend-wasm.wasm", "vendor/tfjs-backend-wasm-simd.wasm",
                "vendor/tfjs-backend-wasm-threaded-simd.wasm"];
const MODELS = ["vendor/models/ssdlite_mobilenet_v2/", "vendor/models/deeplab_ade20k/"];

async function modelFiles(dir) {                    // model.json + the weight shards it lists
  const j = await (await fetch(dir + "model.json")).json();
  return [dir + "model.json", ...j.weightsManifest.flatMap(g => g.paths.map(p => dir + p))];
}

self.addEventListener("install", e => e.waitUntil((async () => {
  const cache = await caches.open(VERSION);
  const models = (await Promise.all(MODELS.map(modelFiles))).flat();
  await cache.addAll([...APP, ...VENDOR, ...models].map(u => new Request(u, { cache: "reload" })));
  self.skipWaiting();
})()));

self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== VERSION && k !== TILES) await caches.delete(k);
  await self.clients.claim();
})()));

// Map tiles: from the phone's cache when seen before, else the network (and keep a copy).
async function tile(req) {
  const cache = await caches.open(TILES);
  const hit = await cache.match(req.url);
  if (hit) return hit;
  try {
    const r = await fetch(req.url, { mode: "cors" });
    if (r.ok) {
      await cache.put(req.url, r.clone());
      if (Math.random() < 0.02) cache.keys().then(k => k.slice(0, Math.max(0, k.length - TILE_MAX)).forEach(x => cache.delete(x)));
    }
    return r;
  } catch { return new Response("", { status: 504 }); }
}

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.hostname === "tile.openstreetmap.org") return e.respondWith(tile(e.request));
  if (e.request.method !== "GET" || url.origin !== location.origin ||
      url.pathname.startsWith("/ws/") || url.pathname.startsWith("/api/")) return;
  if (e.request.mode === "navigate" && url.pathname !== "/") return;   // only the phone app page
  e.respondWith((async () => {
    const cache = await caches.open(VERSION);
    const key = e.request.mode === "navigate" ? "./" : e.request;
    const hit = await cache.match(key, { ignoreSearch: true });
    const fresh = fetch(e.request.mode === "navigate" ? "./" : e.request.url, { cache: "no-cache" }).then(r => {
      if (r.ok) cache.put(key, r.clone());
      return r;
    }).catch(() => null);
    if (hit) {
      if (!url.pathname.startsWith("/vendor/")) e.waitUntil(fresh);   // refresh app files quietly
      return hit;
    }
    return (await fresh) || new Response("offline and not cached", { status: 503 });
  })());
});
