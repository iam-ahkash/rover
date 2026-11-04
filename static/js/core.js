// Shared helpers, settings (kept on the phone) and live state for the phone app.

const $ = id => document.getElementById(id);
const IS_APK = !!window.AndroidBridge;     // running inside the Android app (android/), not a browser
const f = (x, d = 2) => (x == null || isNaN(x)) ? "—" : Number(x).toFixed(d);
const deg = r => r * 180 / Math.PI, rad = d => d * Math.PI / 180;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const cardinal = h => ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(h / 45) % 8];

const DEFAULTS = {
  model: "yolo11n", camId: "", camH: 1.30, fov: 95.7, fovManual: false,
  pitchOffset: 0, calibrated: false, pathMode: "opencv", allowGrass: true, stream: false,
  // sensor calibration (js/calib.js)
  accBias: [0, 0], gyroBias: [0, 0, 0], accCal: false, fovCal: false,
  compassOffset: 0, compassCal: null, gpsMaxAcc: 50,
  npuAccel: "npu",                 // which NNAPI accelerator runs YOLO in the app (js/yolo.js)
  edgeMargin: 0.15, edgeSens: 5,    // path edges: keep-away distance (m), edge sensitivity 1-10
};
const settings = (() => {
  try {
    const s = JSON.parse(localStorage.getItem("rover-settings") || "{}");
    return { ...DEFAULTS, ...s };
  } catch { return JSON.parse(JSON.stringify(DEFAULTS)); }
})();
// one-time switch to YOLO11n (benchmarked best on this phone, Nov 2026); can be changed back in Settings
if (!settings.yoloSwitch) { settings.model = "yolo11n"; settings.yoloSwitch = true; }
// one-time switch to the NPU in the Android app (YOLO11n 18 ms on the MediaTek APU vs 75 ms WebGPU, Nov 2026)
if (IS_APK && !settings.npuSwitch) { settings.model = "yolo11n-npu"; settings.npuSwitch = true; }
if (!IS_APK && settings.model === "yolo11n-npu") settings.model = "yolo11n";   // NPU needs the app
function saveSettings() { try { localStorage.setItem("rover-settings", JSON.stringify(settings)); } catch {} }

// ?path=ai or ?path=colour in the address picks the path detector (handy for demos)
const pathParam = new URLSearchParams(location.search).get("path");
if (["ai", "colour", "opencv"].includes(pathParam)) settings.pathMode = pathParam;

const state = {
  source: "none", camera: "—", camId: null, frameSize: null,
  imu: {}, orient: {}, pitch: null, gps: null, heading: null,
  fps: 0, inferMs: 0, backend: "—",
  boxes: [], obstacles: [], path: null, decision: {},
};

function pill(id, ok, text) {
  const el = $(id); el.className = "pill " + (ok ? "ok" : "bad");
  if (text) el.textContent = text;
}
