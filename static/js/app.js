// Phone app: sensors -> camera -> obstacle detection -> free path -> planner -> screen + on-phone log.
// Everything runs on the phone; the Mac is only needed to load the page the first time
// (after that the service worker serves it offline). Streaming to the Mac is optional (Settings).

const ROVER_HALF_WIDTH = 0.20;                        // rover half width (m); safety margin = settings.edgeMargin
const ACTION_COLOURS = { FORWARD: "#2fbf71", LEFT: "#f2a93b", RIGHT: "#f2a93b", STOP: "#e5484d", "NO PATH": "#e5484d" };
const overlay = $("overlay"), octx = overlay.getContext("2d");
let detector = null, gravity = null, ws = null;
const resetGravity = () => { gravity = null; };   // after a tilt calibration

// ---------- sensors ----------
async function startSensors() {
  try {
    if (typeof DeviceMotionEvent?.requestPermission === "function") {   // iPhone only
      await DeviceMotionEvent.requestPermission(); await DeviceOrientationEvent.requestPermission();
    }
  } catch (e) { console.warn(e); }
  addEventListener("devicemotion", e => {
    const a = e.accelerationIncludingGravity || {}, r = e.rotationRate || {};
    if (a.x == null) return;
    const raw = { ax: a.x, ay: a.y, az: a.z, gx: r.beta, gy: r.gamma, gz: r.alpha };
    state.imuRaw = raw; calOnMotion(raw);              // js/calib.js measures the biases from these
    const [bx, by] = settings.accBias, gb = settings.gyroBias;   // calibrated readings
    state.imu = { ax: a.x - bx, ay: a.y - by, az: a.z,
                  gx: r.beta == null ? null : r.beta - gb[0], gy: r.gamma == null ? null : r.gamma - gb[1],
                  gz: r.alpha == null ? null : r.alpha - gb[2] };
    const g = [state.imu.ax, state.imu.ay, state.imu.az];    // low-pass: steady gravity, ignores bumps
    gravity = gravity ? gravity.map((v, i) => v + 0.1 * (g[i] - v)) : g;
    const n = Math.hypot(...gravity), sign = /iPhone|iPad/.test(navigator.userAgent) ? -1 : 1;
    state.pitch = deg(Math.asin(Math.max(-1, Math.min(1, sign * gravity[2] / n))));  // back camera tilt down
    state.roll = deg(Math.atan2(sign * gravity[0], sign * gravity[1]));               // sideways lean
    pill("s-imu", true);
  });
  const onOrient = e => {
    state.orient = { alpha: e.alpha, beta: e.beta, gamma: e.gamma };
    navOnOrientation(e);
    if (nav.heading != null) state.heading = nav.heading;
  };
  addEventListener("deviceorientationabsolute", onOrient);
  addEventListener("deviceorientation", onOrient);
  if (!("geolocation" in navigator)) return pill("s-gps", false, "no GPS");
  navigator.geolocation.watchPosition(p => {
    const c = p.coords;
    state.gps = { lat: c.latitude, lon: c.longitude, acc: c.accuracy, speed: c.speed, course: c.heading, t: p.timestamp };
    navOnGps(c, p.timestamp);
    pill("s-gps", c.accuracy <= settings.gpsMaxAcc, `GPS ±${Math.round(c.accuracy)} m`);
  }, err => pill("s-gps", false, err.code === 3 ? "GPS: searching…" : "GPS: " + err.message),
     { enableHighAccuracy: true, maximumAge: 0, timeout: 20000 });
}

// ---------- ML ----------
async function pickBackend() {
  for (const b of ["webgl", "wasm", "cpu"]) {
    try {
      if (b === "wasm") tf.wasm.setWasmPaths(new URL("vendor/", location.href).href);
      if (await tf.setBackend(b)) { await tf.ready(); return b; }
    } catch (e) { console.warn("backend", b, e); }
  }
  return tf.getBackend();
}

async function loop() {
  let frames = 0, t0 = performance.now(), lastSeg = 0;
  while (true) {
    if (video.readyState >= 2) {
      const w = video.videoWidth, h = video.videoHeight;
      if (state.frameSize?.[0] !== w || state.frameSize?.[1] !== h) {
        state.frameSize = [w, h];
        $("stage").style.aspectRatio = `${w} / ${h}`;
        $("stage").style.width = `min(100%, ${(62 * w / h).toFixed(1)}vh)`;
      }
      const t = performance.now();
      const dets = await detector.detect(video, 15, 0.3);  // low threshold; tracker needs 2+ frames
      state.inferMs = performance.now() - t;
      state.boxes = trackBoxes(dets, w, h);
      if (settings.pathMode === "ai" && seg.status === "ready" && performance.now() - lastSeg > 1000) {
        try { await runSegmentation(video, w, h); } catch (e) { seg.status = "error: " + e.message; }
        lastSeg = performance.now();
      }
      const path = detectPath(video, w, h);
      const flow = cvs.ready ? cvFlow(video, path.pw, path.ph) : null;   // OpenCV optical flow
      const edges = hasPitch() ? edgeObstacles(path, w, h) : [];
      state.path = path;
      state.obstacles = listObstacles(state.boxes, edges, w, h);
      const goal = navGoal();
      state.decision = planPath(path, state.boxes, w, h, goal && !goal.arrived ? goal.rel : null);
      // optical flow sees anything growing fast in the middle of the view (works without distances)
      state.ttc = flow?.ttc ?? null;
      if (state.ttc != null && state.ttc < 1.0 && state.decision.throttle > 0)
        Object.assign(state.decision, { action: "STOP", throttle: 0, steer: 0, why: "closing in" });
      overlay.width = w; overlay.height = h;
      drawPath(octx, path, state.decision, w, h, goal?.name);
      if (path.source === "opencv") drawBlobs(octx, cvs.blobs, path, w, h);
      drawFlow(octx, flow, w, h);
      drawObstacles(octx, state.obstacles, state.boxes);
      recSample();
      frames++;
      if (performance.now() - t0 > 1000) { state.fps = frames; frames = 0; t0 = performance.now(); }
    }
    await new Promise(r => requestAnimationFrame(r));
  }
}

// ---------- screen ----------
function render() {
  const d = state.decision;
  if (d.action) { $("decision").textContent = d.action + (d.action === "LEFT" || d.action === "RIGHT" ? ` ${Math.abs(d.heading).toFixed(0)}°` : "");
                  $("decision").style.color = ACTION_COLOURS[d.action]; }
  $("perf").innerHTML = `${state.fps} fps · ${f(state.inferMs, 0)} ms · ${state.backend}${detector?.npuMs ? ` (net ${f(detector.npuMs, 0)})` : ""}<br>` +
    `path: ${state.path?.source === "ai" ? `AI ${f(seg.ms, 0)} ms` : state.path?.source === "opencv" ? `OpenCV ${f(cvs.ms, 0)} ms`
            : settings.pathMode === "ai" ? "AI " + seg.status : settings.pathMode === "opencv" ? "OpenCV " + cvs.status : "colour"}` +
    (cvs.flow ? `<br>flow ${cvs.flow.n} pts · ${cvs.flow.moving ? "moving" : "still"}${Math.abs(cvs.flow.turn) > 15 ? (cvs.flow.turn > 0 ? " · turning L" : " · turning R") : ""}` : "") +
    `<br>clear ${f(d.clear, 1)} m` + (REC.session ? `<br><span style="color:var(--stop)">● REC</span>` : "");
  $("dets").innerHTML = !hasPitch() ? `<li class="hint">waiting for the motion sensor…</li>` : state.obstacles.length
    ? state.obstacles.slice(0, 6).map(o => `<li><b>obstacle</b> ${o.dist.toFixed(2)} m,
        ${Math.abs(o.angle) < 5 ? "ahead" : `${Math.abs(o.angle).toFixed(0)}° ${o.angle < 0 ? "left" : "right"}`}
        <span class="hint">${(o.xr - o.xl).toFixed(1)} m wide</span></li>`).join("")
    : `<li class="hint">nothing within ${OBST_MAX} m</li>`;
  if (state.ttc != null) $("dets").innerHTML = `<li style="color:${state.ttc < 1.5 ? "var(--stop)" : "var(--warn)"}"><b>closing in</b> on something ahead · ${state.ttc.toFixed(1)} s to contact (optical flow)</li>` + $("dets").innerHTML;
  const o = state.orient;
  $("tilt").innerHTML = `${f(state.pitch, 1)}° ${state.pitch > 0 ? "down" : "up"} · roll ${f(state.roll, 0)}°`;
  $("compass").textContent = state.heading == null ? "—" : `${f(state.heading, 0)}° ${cardinal(state.heading)}`;
  renderNav();
}

function renderNav() {
  $("nav-pos").innerHTML = nav.lat == null
    ? (state.gps ? `GPS too rough (±${f(state.gps.acc, 0)} m) — go outdoors / wait…` : "waiting for GPS fix…")
    : `${f(nav.lat, 6)}, ${f(nav.lon, 6)} · ±${f(nav.acc, 1)} m<br>` +
      `heading ${f(nav.heading, 0)}° ${nav.heading != null ? cardinal(nav.heading) : ""} · ${f(nav.speed, 1)} m/s · walked ${f(nav.walked, 0)} m`;
  const sel = $("wp-goal");
  if (sel.options.length !== nav.waypoints.length + 1) {
    sel.length = 1; nav.waypoints.forEach((w, i) => sel.add(new Option(w.name, i))); sel.value = nav.goalIdx;
  }
  const g = navGoal(), d = state.decision || {};
  if (!g) $("nav-goal").textContent = nav.goalIdx >= 0 ? "waiting for position…" : "";
  else if (g.arrived) $("nav-goal").innerHTML = `✅ <b>Arrived at ${g.name}</b>`;
  else {
    const turn = g.rel == null ? "" : Math.abs(g.rel) < 10 ? "straight ahead" : `turn ${Math.abs(g.rel)}° ${g.rel < 0 ? "left" : "right"}`;
    $("nav-goal").innerHTML = `→ <b>${g.name}</b>: ${f(g.dist, 0)} m · ${turn}<br><span class="hint">path says: ${d.action || "—"} ${d.heading != null ? f(d.heading, 0) + "°" : ""}</span>`;
  }
  if (typeof L !== "undefined" && navPosition()) updateMap();   // OpenStreetMap (js/map.js)
  else drawMiniMap($("minimap"));                               // plain map until a fix / no Leaflet
}

// ---------- calibration: tap where something touches the floor at a measured distance ----------
overlay.addEventListener("click", e => {
  if (calTap(e)) return;                       // lens / other calibration taps (js/calib.js)
  const [w, h] = state.frameSize || [0, 0], D = parseFloat($("cal-d").value);
  if (!w || !hasPitch()) return void ($("cal-msg").textContent = "Start first and hold the phone still.");
  if (!(D > 0)) return void ($("cal-msg").textContent = "Enter the measured distance first.");
  const r = overlay.getBoundingClientRect(), v = (e.clientY - r.top) / r.height * h;
  const below = rad(cameraPitch()) + Math.atan((v - h / 2) / focalPx(w, h));
  const offset = deg(Math.atan(settings.camH / D) - below) + (settings.pitchOffset || 0);
  if (Math.abs(offset) > 12) return void ($("cal-msg").textContent =
    `That needs a ${offset.toFixed(0)}° correction — check the camera height and tap exactly where the object meets the floor.`);
  settings.pitchOffset = +offset.toFixed(2); settings.calibrated = true; saveSettings();
  boxTracks.forEach(t => t.dist = null);
  showCalibration(); showCalStatus();
});
function showCalibration() {
  $("cal-msg").style.color = settings.calibrated ? "var(--go)" : "var(--warn)";
  $("cal-msg").textContent = settings.calibrated
    ? `✓ Calibrated: height ${settings.camH} m · tilt correction ${settings.pitchOffset}° · FOV ${settings.fov}°`
    : "Not calibrated yet (distances may be off by 10–30%).";
}

// ---------- optional stream to the Mac (off by default) ----------
function connect() {
  if (!settings.stream || ws || IS_APK) return;
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/phone`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => pill("s-net", true, "Mac: streaming");
  ws.onclose = () => { ws = null; pill("s-net", false, settings.stream ? "Mac: not reachable" : "Mac: off");
                       if (settings.stream) setTimeout(connect, 3000); };
}
const frameCanvas = document.createElement("canvas");
function sendState() {
  if (!ws || ws.readyState !== 1) return;
  const p = state.path;
  ws.send(JSON.stringify({ type: "state", t: Date.now(), imu: state.imu, orient: state.orient, heading: state.heading,
    gps: state.gps, pitch: state.pitch, frameSize: state.frameSize, fps: state.fps, inferMs: Math.round(state.inferMs),
    backend: state.backend, model: state.model || settings.model, camera: state.camera, camH: settings.camH, fov: settings.fov,
    stereo: "off (one camera)", pitchOffset: settings.pitchOffset || 0, decision: state.decision, segStatus: seg.status,
    tracks: state.boxes.map(t => ({ cls: "obstacle", dist: t.dist == null ? null : +t.dist.toFixed(2), method: "floor",
      bbox: t.box.map(v => +v.toFixed(1)), xl: t.xl, xr: t.xr })),
    obstacles: state.obstacles.map(o => ({ kind: o.kind, dist: +o.dist.toFixed(2), angle: +o.angle.toFixed(0) })),
    path: p && { src: p.source, free: +p.freeFrac.toFixed(3), pw: p.pw, ph: p.ph, b: Array.from(p.boundary), segMs: Math.round(seg.ms) },
    nav: { lat: nav.lat, lon: nav.lon, acc: nav.acc == null ? null : +nav.acc.toFixed(1), speed: +nav.speed.toFixed(2),
           heading: nav.heading == null ? null : +nav.heading.toFixed(0), walked: +nav.walked.toFixed(1),
           goal: navGoal(), waypoints: nav.waypoints } }));
}
function sendFrame() {
  if (!ws || ws.readyState !== 1 || ws.bufferedAmount > 200000 || video.readyState < 2) return;
  frameCanvas.width = video.videoWidth; frameCanvas.height = video.videoHeight;
  frameCanvas.getContext("2d").drawImage(video, 0, 0);
  frameCanvas.toBlob(b => b && b.arrayBuffer().then(buf => ws.send(buf)), "image/jpeg", 0.6);
}

// ---------- controls ----------
$("set-model").value = settings.model;
$("set-model").onchange = e => { settings.model = e.target.value; saveSettings(); location.reload(); };
$("set-path").value = settings.pathMode;
$("set-path").onchange = e => { settings.pathMode = e.target.value; saveSettings(); };
$("set-grass").checked = settings.allowGrass;
$("set-grass").onchange = e => { settings.allowGrass = e.target.checked; saveSettings(); };
$("set-h").value = settings.camH;
$("set-h").onchange = e => { settings.camH = parseFloat(e.target.value) || DEFAULTS.camH; saveSettings(); showCalibration(); showCalStatus(); };
$("set-fov").value = settings.fov;
$("set-fov").onchange = e => { settings.fov = parseFloat(e.target.value) || DEFAULTS.fov; settings.fovManual = true; settings.fovCal = false; saveSettings(); showCalibration(); showCalStatus(); };
$("set-cam").onchange = async e => {
  settings.camId = e.target.value; settings.fovManual = false; saveSettings();
  try { await openCamera(e.target.value || undefined); $("set-fov").value = settings.fov; pill("s-cam", true, state.camera); }
  catch (err) { pill("s-cam", false, "camera: " + err.name); }
};
$("set-stream").checked = settings.stream;
$("set-stream").onchange = e => {
  settings.stream = e.target.checked; saveSettings();
  if (settings.stream) connect(); else { ws?.close(); pill("s-net", false, "Mac: off"); }
};
const setHeight = m => { settings.camH = m; settings.pitchOffset = 0; settings.calibrated = false; $("set-h").value = m; saveSettings(); showCalibration(); showCalStatus(); };
$("preset-hand").onclick = () => setHeight(1.3);
$("preset-rover").onclick = () => setHeight(0.2);
$("cal-reset").onclick = () => { if (confirm("Reset the calibration of all sensors?")) resetAllCalibration(); };
$("wp-save").onclick = () => {
  if (addWaypoint($("wp-name").value.trim())) { $("wp-name").value = ""; renderNav(); }
  else $("nav-goal").textContent = "No GPS fix yet — can't save this spot.";
};
$("wp-goal").onchange = e => { nav.goalIdx = +e.target.value; renderNav(); };
$("wp-clear").onclick = () => { if (confirm("Delete all saved points?")) { nav.waypoints = []; nav.goalIdx = -1; saveWaypoints(); renderNav(); } };
$("trail-clear").onclick = () => { nav.trail = []; nav.walked = 0; renderNav(); };
$("rec-btn").onclick = async () => {
  if (REC.session) { await recStop(); $("rec-btn").textContent = "● Start recording"; $("rec-btn").classList.remove("danger"); }
  else { await recStart(); $("rec-btn").textContent = "■ Stop recording"; $("rec-btn").classList.add("danger"); }
  recRender();
};
showCalibration();
pill("s-net", false, settings.stream ? "Mac: connecting" : "Mac: off");
recRender();

(function checkBrowser() {
  const missing = [];
  if (!window.isSecureContext) missing.push("page is not secure (open http://localhost:8080 via adb, or https://)");
  if (!navigator.mediaDevices?.getUserMedia) missing.push("camera API not available in this browser");
  if (!("indexedDB" in window)) missing.push("no on-phone storage (IndexedDB)");
  if (missing.length) $("hint").innerHTML = "⚠️ " + missing.join("<br>⚠️ ");
})();

// offline: in the Android app every file is inside the APK; in a browser the service worker keeps them
if (IS_APK) {
  pill("s-off", true, "built-in (APK)");
  document.querySelector("#set-stream").closest("label").style.display = "none";   // needs the Mac server
  pill("s-net", true, "drive mode: off"); $("s-net").id = "s-drive";
} else if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").then(() => navigator.serviceWorker.ready).then(() => {
    pill("s-off", true, "offline ready");
  }).catch(e => pill("s-off", false, "offline: " + e.message));
}
if (!IS_APK) addEventListener("online", () => pill("s-off", true, "offline ready"));

// Drive mode (Android app): pin the app, Do Not Disturb, steady CPU/GPU speed, full screen,
// so the models get the whole phone. Tap the pill to switch it off/on.
let driving = false;
function setDrive(on) {
  if (!IS_APK) return;
  const got = AndroidBridge.driveMode(on);
  driving = on;
  pill("s-drive", on, on ? "drive mode: " + (got || "on") : "drive mode: off");
  if (on && /dnd-needs-permission/.test(got)) $("hint").textContent =
    "Allow \"Do Not Disturb access\" for Rover Phone ML in the screen that opened, then come back (only once).";
}
if (IS_APK) $("s-drive").onclick = () => setDrive(!driving);

// NPU: hide the option in a browser; in the app, a button times every accelerator (NpuYolo.java)
if (!IS_APK) $("set-model").querySelector('[value="yolo11n-npu"]').remove();
else {
  $("npu-row").style.display = "";
  $("npu-bench").onclick = async () => {
    $("npu-bench").disabled = true; $("npu-msg").textContent = "Timing YOLO11n on each accelerator… (the picture pauses)";
    await sleep(50);
    const names = { npu: "NPU (MDLA)", neuron: "NPU (Neuron, auto)", dsp: "DSP", "nnapi-gpu": "GPU (NNAPI)", cpu: "CPU, 4 cores" };
    const r = JSON.parse(AndroidBridge.npuBench(20));
    $("npu-msg").innerHTML = r.map(x => `${names[x.accel] || x.accel}: <b>${x.ms != null ? x.ms + " ms" : "not available"}</b>` +
      (x.initMs != null ? ` <span class="hint">(start ${(x.initMs / 1000).toFixed(1)} s)</span>` : "")).join("<br>") +
      `<br><span class="hint">WebGPU in the browser engine: ~75 ms</span>`;
    $("npu-bench").disabled = false;
  };
}

$("start").onclick = async () => {
  $("start").disabled = true; $("start").textContent = "Starting…";
  setDrive(true);
  await startSensors();
  for (let i = 0; i < 3; i++) {     // camera can be busy for a moment (another tab / app letting go)
    try { await startCamera(); pill("s-cam", true, state.camera); showCalStatus(); break; }
    catch (e) { pill("s-cam", false, "camera: " + e.name + (e.name === "NotReadableError" ? " (close other tabs/apps using it)" : "")); await sleep(1500); }
  }
  connect();
  setInterval(render, 200);
  setInterval(() => { sendState(); }, 250);
  setInterval(sendFrame, 500);
  setInterval(() => REC.session && recRender(), 5000);
  $("hint").textContent = "Loading the ML model (from the phone's storage)…";
  try {
    state.backend = await pickBackend();
    const loadModel = base => cocoSsd.load({ base, modelUrl:
      `vendor/models/${base === "lite_mobilenet_v2" ? "ssdlite_mobilenet_v2" : "ssd_mobilenet_v2"}/model.json` });
    let base = settings.model, note = "";
    if (base === "yolo11n-npu") {   // YOLO11n on the MediaTek NPU (Android app); else the GPU
      try { detector = await loadYoloNpu(settings.npuAccel || "npu"); }
      catch (e) { console.warn("NPU", e); note = " (NPU unavailable: " + (e.message || e) + ", using GPU)"; base = "yolo11n"; }
    }
    if (base === "yolo11n" && !detector) {   // YOLO11n on the GPU (WebGPU); COCO-SSD fast if that can't start
      try { detector = await loadYolo(); }
      catch (e) { console.warn("YOLO", e); note += " (YOLO unavailable: " + (e.message || e) + ")"; base = "lite_mobilenet_v2"; }
    }
    if (!detector) {
      try { detector = await loadModel(base); }
      catch (e) {                   // e.g. "Accurate" picked but never downloaded while online
        if (base === "lite_mobilenet_v2") throw e;
        base = "lite_mobilenet_v2"; detector = await loadModel(base); note = " (accurate not stored offline)";
      }
    }
    state.model = base;
    if (base.startsWith("yolo11n")) state.backend = detector.engine || "webgpu";   // tf backend stays for DeepLab only
    pill("s-ml", !note || base.startsWith("yolo11n"), { "yolo11n-npu": "ML: YOLO11n · NPU", yolo11n: "ML: YOLO11n · GPU",
      lite_mobilenet_v2: "ML: fast", mobilenet_v2: "ML: accurate" }[base] + note);
    $("hint").textContent = "Running on the phone. Set the camera height, calibrate once, then record.";
    $("start").style.display = "none";
    loop();
    await loadOpenCV();             // classic vision: edges + flood fill + optical flow (js/cvision.js)
    loadSegmentation();
  } catch (e) {
    pill("s-ml", false, "ML failed");
    $("hint").textContent = "Could not load the model: " + e;
  }
};
