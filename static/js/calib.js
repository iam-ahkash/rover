// Sensor calibration, all saved on the phone with the other settings:
//  1. Tilt sensor (accelerometer) + gyroscope: measure the phone lying still on a table, turn it
//     around (top <-> bottom) and measure again. The table's own slope flips sign between the two,
//     the sensor's bias does not, so bias = average of the two and table slope = half the difference.
//     The gyroscope should read 0 while still, so its average is its bias.
//  2. Camera distance: tap where an object at a measured distance touches the floor (app.js) -> tilt correction.
//  3. Lens field of view: an object of known width at a known distance, tap its left and right edges.
//  4. Compass: walk straight with the camera forward (GPS course is the truth), or aim the camera at
//     a saved point at least 20 m away (its GPS bearing is the truth) -> heading correction.
//  5. GPS: which accuracy is good enough to use, and saving a spot averaged over 20 s.
// Uses globals: $, f, deg, rad, sleep, settings, saveSettings, state, nav, wrap180, bearing,
// haversine, focalPx, addWaypointAt, renderNav, showCalibration, KNOWN_CAMS, DEFAULTS.

const CAL = { collecting: null, tiltA: null, tap: null, busy: false };

// called from the devicemotion handler with raw readings
function calOnMotion(raw) { if (CAL.collecting) CAL.collecting.push(raw); }

async function collectMotion(ms) {
  CAL.collecting = [];
  await sleep(ms);
  const s = CAL.collecting; CAL.collecting = null;
  return s;
}
const mean = a => a.reduce((p, q) => p + q, 0) / a.length;
const std = a => { const m = mean(a); return Math.sqrt(mean(a.map(v => (v - m) ** 2))); };
const circMean = a => deg(Math.atan2(mean(a.map(v => Math.sin(rad(v)))), mean(a.map(v => Math.cos(rad(v))))));

function calSay(id, text, ok) {
  const el = $(id); el.innerHTML = text;
  el.style.color = ok === true ? "var(--go)" : ok === false ? "var(--stop)" : "var(--muted)";
}

// ---------- 1. tilt sensor + gyroscope ----------
async function calibrateTilt() {
  if (CAL.busy) return;
  if (!state.imuRaw) return calSay("cal-tilt-msg", "Press Start first (the motion sensor isn't running yet).", false);
  CAL.busy = true;
  const step = CAL.tiltA ? 2 : 1;
  calSay("cal-tilt-msg", `Step ${step} of 2: measuring, keep the phone still… (3 s)`);
  const s = await collectMotion(3000);
  CAL.busy = false;
  if (s.length < 15) return calSay("cal-tilt-msg", "Too few sensor readings — try again.", false);
  const ax = s.map(r => r.ax), ay = s.map(r => r.ay), az = s.map(r => r.az);
  if (Math.max(std(ax), std(ay), std(az)) > 0.3) { CAL.tiltA = null; $("cal-tilt").textContent = "Calibrate tilt & gyro";
    return calSay("cal-tilt-msg", "The phone moved — put it down on the table and don't touch it.", false); }
  const m = { ax: mean(ax), ay: mean(ay), az: mean(az),
              gyro: ["gx", "gy", "gz"].map(k => s[0][k] == null ? 0 : mean(s.map(r => r[k]))) };
  if (Math.abs(m.ax) > 2 || Math.abs(m.ay) > 2 || Math.abs(m.az) < 8) { CAL.tiltA = null; $("cal-tilt").textContent = "Calibrate tilt & gyro";
    return calSay("cal-tilt-msg", "Lay the phone flat, screen up, on a table (it isn't flat now).", false); }
  if (step === 1) {
    CAL.tiltA = m;
    $("cal-tilt").textContent = "Step 2: turned around — measure again";
    return calSay("cal-tilt-msg", "Now turn the phone around on the same spot (top where the bottom was), let go, and tap the button again.");
  }
  const A = CAL.tiltA; CAL.tiltA = null; $("cal-tilt").textContent = "Calibrate tilt & gyro";
  const bias = [(A.ax + m.ax) / 2, (A.ay + m.ay) / 2];
  const slope = deg(Math.atan(Math.hypot((A.ax - m.ax) / 2, (A.ay - m.ay) / 2) / Math.abs(m.az)));
  settings.accBias = bias.map(v => +v.toFixed(3));
  settings.gyroBias = A.gyro.map((v, i) => +((v + m.gyro[i]) / 2).toFixed(3));
  settings.accCal = true; saveSettings();
  resetGravity();
  calSay("cal-tilt-msg", `✓ Tilt sensor bias ${settings.accBias.map(v => f(v, 2)).join(", ")} m/s² ` +
    `(${f(deg(Math.atan(Math.hypot(...bias) / 9.81)), 1)}°) · gyro bias ${settings.gyroBias.map(v => f(v, 2)).join(", ")} °/s · ` +
    `your table slopes ${f(slope, 1)}°. Now redo the distance tap below.`, true);
  showCalStatus();
}

// ---------- 3. lens field of view ----------
function startFovTap() {
  const W = parseFloat($("cal-w").value), D = parseFloat($("cal-d").value);
  if (!state.frameSize) return calSay("cal-fov-msg", "Press Start first.", false);
  if (!(W > 0) || !(D > 0)) return calSay("cal-fov-msg", "Enter the object's width and its distance first.", false);
  CAL.tap = { mode: "fov", us: [], W, D };
  calSay("cal-fov-msg", "Tap the object's <b>left edge</b> in the picture…");
  $("stage").scrollIntoView({ behavior: "smooth", block: "center" });
}

// overlay taps: returns true when a calibration step used the tap
function calTap(e) {
  if (!CAL.tap) return false;
  const [w, h] = state.frameSize, r = overlay.getBoundingClientRect();
  const u = (e.clientX - r.left) / r.width * w;
  if (CAL.tap.mode === "fov") {
    CAL.tap.us.push(u);
    if (CAL.tap.us.length === 1) { calSay("cal-fov-msg", "…now tap its <b>right edge</b>."); return true; }
    const { W, D } = CAL.tap, px = Math.abs(CAL.tap.us[1] - CAL.tap.us[0]); CAL.tap = null;
    if (px < 10) { calSay("cal-fov-msg", "The two taps are too close — use a wider object or come closer.", false); return true; }
    const fpx = px * D / W, fov = 2 * deg(Math.atan((Math.max(w, h) / 2) / fpx));
    if (fov < 30 || fov > 150) { calSay("cal-fov-msg", `That gives ${f(fov, 0)}°, which can't be right — check the width and distance.`, false); return true; }
    settings.fov = +fov.toFixed(1); settings.fovManual = true; settings.fovCal = true; saveSettings();
    $("set-fov").value = settings.fov; boxTracks.forEach(t => t.dist = null);
    calSay("cal-fov-msg", `✓ Lens field of view ${settings.fov}° (focal length ${f(fpx, 0)} px). Redo the distance tap after this.`, true);
    showCalibration(); showCalStatus();
    return true;
  }
  return false;
}

// ---------- 4. compass ----------
async function calibrateCompassWalk() {
  if (CAL.busy) return;
  if (nav.lat == null) return calSay("cal-compass-msg", "Needs a GPS fix — go outdoors and wait for the GPS pill.", false);
  CAL.busy = true;
  const diffs = [], end = Date.now() + 30000;
  while (Date.now() < end && diffs.length < 25) {
    calSay("cal-compass-msg", `Walk straight, camera pointing forward, at a normal pace… ${Math.ceil((end - Date.now()) / 1000)} s · ` +
      `${diffs.length} readings${nav.course == null ? " (walk a bit faster)" : ""}`);
    if (nav.course != null && nav.camHeading != null) diffs.push(wrap180(nav.course - nav.camHeading));
    await sleep(1000);
  }
  CAL.busy = false;
  if (diffs.length < 8) return calSay("cal-compass-msg", "Not enough walking readings — walk faster (over 0.7 m/s) in a straight line and try again.", false);
  const spread = Math.sqrt(mean(diffs.map(d => wrap180(d - circMean(diffs)) ** 2)));
  if (spread > 25) return calSay("cal-compass-msg", `Readings vary by ±${f(spread, 0)}° — walk straighter, away from cars and metal, and try again.`, false);
  applyCompass(circMean(diffs), `walking (${diffs.length} readings, ±${f(spread, 0)}°)`);
}

async function calibrateCompassAim() {
  const wp = nav.waypoints[+$("cal-compass-wp").value];
  if (!wp) return calSay("cal-compass-msg", "Save a spot first (GPS card), at least 20 m away, and pick it here.", false);
  if (nav.lat == null || nav.camHeading == null) return calSay("cal-compass-msg", "Needs a GPS fix and the compass — wait for both.", false);
  const dist = haversine(nav.lat, nav.lon, wp.lat, wp.lon);
  if (dist < Math.max(20, 4 * (nav.acc || 5))) return calSay("cal-compass-msg",
    `${wp.name} is only ${f(dist, 0)} m away — it must be at least ${f(Math.max(20, 4 * (nav.acc || 5)), 0)} m for a good result.`, false);
  CAL.busy = true;
  calSay("cal-compass-msg", `Keep the camera aimed at ${wp.name}… (3 s)`);
  const hs = [];
  for (let i = 0; i < 15; i++) { hs.push(nav.camHeading); await sleep(200); }
  CAL.busy = false;
  applyCompass(wrap180(bearing(nav.lat, nav.lon, wp.lat, wp.lon) - circMean(hs)), `aiming at ${wp.name} (${f(dist, 0)} m)`);
}

function applyCompass(diff, how) {
  if (Math.abs(diff) > 60) return calSay("cal-compass-msg",
    `The compass is ${f(diff, 0)}° off — too much to be a simple offset. Wave the phone in a figure 8 a few times, move away from metal, and try again.`, false);
  settings.compassOffset = +wrap180((settings.compassOffset || 0) + diff).toFixed(1);
  settings.compassCal = how; saveSettings();
  nav.camHeading = null;                                        // restart the smoothing
  calSay("cal-compass-msg", `✓ Compass corrected by ${f(diff, 1)}° (total ${settings.compassOffset}°) from ${how}.`, true);
  showCalStatus();
}

// ---------- 5. GPS ----------
async function saveAveragedSpot() {
  if (CAL.busy) return;
  if (!state.gps) return calSay("cal-gps-msg", "No GPS fix yet.", false);
  CAL.busy = true;
  const fixes = [], end = Date.now() + 20000; let lastT = 0;
  while (Date.now() < end) {
    const g = state.gps;
    if (g && g.t !== lastT && g.acc <= settings.gpsMaxAcc) { fixes.push(g); lastT = g.t; }
    calSay("cal-gps-msg", `Stand still… ${Math.ceil((end - Date.now()) / 1000)} s · ${fixes.length} fixes`);
    await sleep(500);
  }
  CAL.busy = false;
  if (fixes.length < 3) return calSay("cal-gps-msg", `Only ${fixes.length} good fixes — go outdoors and try again.`, false);
  const wt = fixes.map(g => 1 / Math.max(g.acc, 1) ** 2), sw = wt.reduce((p, q) => p + q, 0);
  const lat = fixes.reduce((p, g, i) => p + g.lat * wt[i], 0) / sw, lon = fixes.reduce((p, g, i) => p + g.lon * wt[i], 0) / sw;
  const acc = 1 / Math.sqrt(sw);
  const name = $("wp-name").value.trim() || `Spot ${nav.waypoints.length + 1}`;
  addWaypointAt(lat, lon, name); $("wp-name").value = ""; renderNav(); fillCompassWaypoints();
  calSay("cal-gps-msg", `✓ Saved “${name}” from ${fixes.length} fixes (about ±${f(acc, 1)} m, single fix ±${f(mean(fixes.map(g => g.acc)), 0)} m).`, true);
}

// ---------- status + controls ----------
function fillCompassWaypoints() {
  const sel = $("cal-compass-wp"), v = sel.value;
  sel.length = 0;
  if (!nav.waypoints.length) sel.add(new Option("— no saved spots —", ""));
  nav.waypoints.forEach((w, i) => sel.add(new Option(w.name, i)));
  if (v !== "" && v < nav.waypoints.length) sel.value = v;
}

function showCalStatus() {
  const row = (ok, name, text) => `<div>${ok ? "✅" : "⬜"} <b>${name}</b> <span class="hint">${text}</span></div>`;
  const known = KNOWN_CAMS[state.camId];
  $("cal-status").innerHTML =
    row(settings.accCal, "Tilt & gyro", settings.accCal ? `bias ${settings.accBias.map(v => f(v, 2)).join(", ")} m/s²` : "not done (step 1)") +
    row(settings.calibrated, "Camera distance", settings.calibrated ? `height ${settings.camH} m · tilt correction ${settings.pitchOffset}°` : `height ${settings.camH} m · tap not done (step 2)`) +
    row(settings.fovCal || (known && !settings.fovManual), "Lens", `${settings.fov}° ${settings.fovCal ? "measured" : known && !settings.fovManual ? "(factory value)" : "(typed in)"}`) +
    row(settings.compassCal, "Compass", settings.compassCal ? `${settings.compassOffset}° from ${settings.compassCal}` : "not done (step 4)") +
    row(true, "GPS", `uses fixes better than ±${settings.gpsMaxAcc} m`) +
    row(true, "Path edges", `keeps ${Math.round(settings.edgeMargin * 100)} cm away · sensitivity ${settings.edgeSens}/10`);
}

function resetAllCalibration() {
  Object.assign(settings, { pitchOffset: 0, calibrated: false, fovManual: false, fovCal: false, accBias: [0, 0],
    gyroBias: [0, 0, 0], accCal: false, compassOffset: 0, compassCal: null, gpsMaxAcc: DEFAULTS.gpsMaxAcc,
    edgeMargin: DEFAULTS.edgeMargin, edgeSens: DEFAULTS.edgeSens });
  if (KNOWN_CAMS[state.camId]) settings.fov = KNOWN_CAMS[state.camId].fov;
  $("set-fov").value = settings.fov; $("cal-gps-acc").value = settings.gpsMaxAcc;
  saveSettings(); resetGravity(); nav.camHeading = null; CAL.tiltA = null; CAL.tap = null;
  $("cal-tilt").textContent = "Calibrate tilt & gyro";
  ["cal-tilt-msg", "cal-fov-msg", "cal-compass-msg", "cal-gps-msg"].forEach(id => calSay(id, ""));
  showCalibration(); showCalStatus(); showEdge();
}

// ---------- 6. path edges ----------
function showEdge() {
  $("edge-margin").value = settings.edgeMargin; $("edge-sens").value = settings.edgeSens;
  $("edge-margin-v").textContent = `${Math.round(settings.edgeMargin * 100)} cm (corridor ${Math.round((ROVER_HALF_WIDTH + settings.edgeMargin) * 200)} cm)`;
  $("edge-sens-v").textContent = `${settings.edgeSens} / 10${settings.edgeSens === 5 ? " (default)" : settings.edgeSens > 5 ? " (more edges)" : " (fewer edges)"}`;
}
$("edge-margin").oninput = e => { settings.edgeMargin = +e.target.value; saveSettings(); showEdge(); showCalStatus(); };
$("edge-sens").oninput = e => { settings.edgeSens = +e.target.value; saveSettings(); showEdge(); showCalStatus(); };
$("edge-default").onclick = () => { settings.edgeMargin = DEFAULTS.edgeMargin; settings.edgeSens = DEFAULTS.edgeSens; saveSettings(); showEdge(); showCalStatus(); };
showEdge();

$("cal-tilt").onclick = calibrateTilt;
$("cal-fov").onclick = startFovTap;
$("cal-compass-walk").onclick = calibrateCompassWalk;
$("cal-compass-aim").onclick = calibrateCompassAim;
$("cal-compass-reset").onclick = () => { settings.compassOffset = 0; settings.compassCal = null; saveSettings(); nav.camHeading = null;
                                         calSay("cal-compass-msg", "Compass correction removed."); showCalStatus(); };
$("cal-gps-acc").value = settings.gpsMaxAcc;
$("cal-gps-acc").onchange = e => { settings.gpsMaxAcc = +e.target.value; saveSettings(); showCalStatus(); };
$("cal-gps-save").onclick = saveAveragedSpot;
$("cal-reset-all").onclick = () => { if (confirm("Reset the calibration of all sensors?")) resetAllCalibration(); };
fillCompassWaypoints(); showCalStatus();
setInterval(() => { if ($("cal-compass-wp").options.length !== Math.max(1, nav.waypoints.length)) fillCompassWaypoints(); }, 2000);
