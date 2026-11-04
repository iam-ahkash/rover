// GPS positioning and waypoint navigation, all on the phone.
//  - Kalman filter (position + velocity, per axis) smooths the GPS fixes in local metres
//  - camera heading from the phone's orientation (where the back camera points)
//  - walked trail + distance, saved waypoints, distance and turn angle to the chosen waypoint
// Uses globals from phone.html: state, deg, rad.

const R_EARTH = 6371000;
const nav = { origin: null, kx: null, ky: null, lastT: 0, lat: null, lon: null, acc: null,
              speed: 0, course: null, camHeading: null, heading: null, trail: [], walked: 0,
              waypoints: [], goalIdx: -1, fixes: 0 };

try { nav.waypoints = JSON.parse(localStorage.getItem("rover-waypoints") || "[]"); } catch {}
const saveWaypoints = () => { try { localStorage.setItem("rover-waypoints", JSON.stringify(nav.waypoints)); } catch {} };

const wrap180 = a => ((a + 540) % 360) - 180;
const toLocal = (lat, lon) => [rad(lon - nav.origin.lon) * R_EARTH * Math.cos(rad(nav.origin.lat)),
                               rad(lat - nav.origin.lat) * R_EARTH];
const toLatLon = (x, y) => [nav.origin.lat + deg(y / R_EARTH),
                            nav.origin.lon + deg(x / (R_EARTH * Math.cos(rad(nav.origin.lat))))];

function haversine(lat1, lon1, lat2, lon2) {
  const a = Math.sin(rad(lat2 - lat1) / 2) ** 2 +
            Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2;
  return 2 * R_EARTH * Math.asin(Math.sqrt(a));
}
function bearing(lat1, lon1, lat2, lon2) {
  const y = Math.sin(rad(lon2 - lon1)) * Math.cos(rad(lat2));
  const x = Math.cos(rad(lat1)) * Math.sin(rad(lat2)) - Math.sin(rad(lat1)) * Math.cos(rad(lat2)) * Math.cos(rad(lon2 - lon1));
  return (deg(Math.atan2(y, x)) + 360) % 360;
}

// 1-D constant-velocity Kalman filter: state [position, velocity]
const kfNew = (p, var0) => ({ x: p, v: 0, P: [[var0, 0], [0, 4]] });
function kfStep(f, z, R, dt, q) {
  f.x += f.v * dt;
  const [[a, b], [, d]] = f.P, dt2 = dt * dt;
  const P00 = a + 2 * dt * b + dt2 * d + q * dt2 * dt2 / 4, P01 = b + dt * d + q * dt2 * dt / 2, P11 = d + q * dt2;
  const S = P00 + R, K0 = P00 / S, K1 = P01 / S, y = z - f.x;
  f.x += K0 * y; f.v += K1 * y;
  const n01 = (1 - K0) * P01;
  f.P = [[(1 - K0) * P00, n01], [n01, P11 - K1 * P01]];
}

function navOnGps(c, t) {
  nav.fixes++;
  if (c.accuracy > settings.gpsMaxAcc) return;     // too poor to use (limit set in Calibration)
  if (!nav.origin) {
    nav.origin = { lat: c.latitude, lon: c.longitude };
    nav.kx = kfNew(0, c.accuracy ** 2); nav.ky = kfNew(0, c.accuracy ** 2); nav.lastT = t;
  }
  const dt = Math.max(0.05, Math.min(10, (t - nav.lastT) / 1000));
  nav.lastT = t;
  // q: how quickly walking speed can change (m/s²)²; tuned on a simulated walk with stops and turns
  const [zx, zy] = toLocal(c.latitude, c.longitude), R = Math.max(c.accuracy, 2) ** 2, q = 0.1;
  kfStep(nav.kx, zx, R, dt, q); kfStep(nav.ky, zy, R, dt, q);
  [nav.lat, nav.lon] = toLatLon(nav.kx.x, nav.ky.x);
  nav.acc = Math.sqrt((nav.kx.P[0][0] + nav.ky.P[0][0]) / 2);
  nav.speed = Math.hypot(nav.kx.v, nav.ky.v);
  nav.course = nav.speed > 0.7 ? (deg(Math.atan2(nav.kx.v, nav.ky.v)) + 360) % 360 : null;
  const last = nav.trail[nav.trail.length - 1];
  const step = last ? haversine(last[0], last[1], nav.lat, nav.lon) : Infinity;
  if (step > Math.max(3, nav.acc)) { if (last) nav.walked += step; nav.trail.push([nav.lat, nav.lon]); }
  if (nav.trail.length > 2000) nav.trail.shift();
}

// Direction the back camera points, from the absolute orientation (alpha, beta, gamma).
function navOnOrientation(e) {
  let h = null;
  if (e.webkitCompassHeading != null) h = e.webkitCompassHeading;           // iPhone (top edge)
  else if (e.absolute && e.alpha != null) {
    const a = rad(e.alpha), b = rad(e.beta), g = rad(e.gamma);
    const E = -(Math.cos(a) * Math.sin(g) + Math.sin(a) * Math.sin(b) * Math.cos(g));
    const N = Math.cos(a) * Math.sin(b) * Math.cos(g) - Math.sin(a) * Math.sin(g);
    if (Math.hypot(E, N) > 0.2) h = (deg(Math.atan2(E, N)) + 360) % 360;    // not when lying flat
    else h = (360 - e.alpha) % 360;
  }
  if (h == null) return;
  h = (h + (settings.compassOffset || 0) + 360) % 360;      // compass calibration (js/calib.js)
  nav.camHeading = nav.camHeading == null ? h : (nav.camHeading + 0.2 * wrap180(h - nav.camHeading) + 360) % 360;
  // while walking, GPS course is a good check on the compass (metal and magnets disturb it)
  nav.heading = nav.course == null ? nav.camHeading
    : (nav.camHeading + 0.5 * wrap180(nav.course - nav.camHeading) + 360) % 360;
}

function navPosition() {
  if (nav.lat != null) return [nav.lat, nav.lon];
  return state.gps ? [state.gps.lat, state.gps.lon] : null;
}

function addWaypoint(name) {
  const p = navPosition();
  if (!p) return false;
  nav.waypoints.push({ name: name || `Point ${nav.waypoints.length + 1}`, lat: +p[0].toFixed(7), lon: +p[1].toFixed(7) });
  saveWaypoints();
  return true;
}

function addWaypointAt(lat, lon, name) {
  nav.waypoints.push({ name: name || `Point ${nav.waypoints.length + 1}`, lat: +lat.toFixed(7), lon: +lon.toFixed(7) });
  saveWaypoints();
}

// Distance, compass bearing and turn angle (relative to where the camera points) to the goal.
function navGoal() {
  const wp = nav.waypoints[nav.goalIdx], p = navPosition();
  if (!wp || !p) return null;
  const dist = haversine(p[0], p[1], wp.lat, wp.lon), brg = bearing(p[0], p[1], wp.lat, wp.lon);
  const rel = nav.heading == null ? null : wrap180(brg - nav.heading);
  return { name: wp.name, dist: +dist.toFixed(1), bearing: +brg.toFixed(0),
           rel: rel == null ? null : +rel.toFixed(0), arrived: dist < Math.max(4, nav.acc || 0) };
}

// Small map on the phone: trail, saved points, goal line and heading arrow (no internet needed).
function drawMiniMap(canvas) {
  const ctx = canvas.getContext("2d"), W = canvas.width = canvas.clientWidth * devicePixelRatio,
        H = canvas.height = canvas.clientHeight * devicePixelRatio;
  ctx.clearRect(0, 0, W, H);
  const p = navPosition();
  ctx.fillStyle = "#8a93a3"; ctx.font = `${12 * devicePixelRatio}px system-ui`;
  if (!p || !nav.origin) { ctx.fillText("waiting for GPS fix…", 10, 20 * devicePixelRatio); return; }
  const pts = [...nav.trail.map(t => toLocal(...t)), ...nav.waypoints.map(w => toLocal(w.lat, w.lon))];
  const me = toLocal(...p); pts.push(me);
  let span = 20;
  for (const q of pts) span = Math.max(span, Math.abs(q[0] - me[0]) * 2.2, Math.abs(q[1] - me[1]) * 2.2);
  const sc = Math.min(W, H) / span, X = x => W / 2 + (x - me[0]) * sc, Y = y => H / 2 - (y - me[1]) * sc;
  ctx.strokeStyle = "#2a303a"; ctx.lineWidth = 1;                   // scale bar
  const bar = span > 200 ? 100 : span > 60 ? 20 : 5;
  ctx.beginPath(); ctx.moveTo(10, H - 10); ctx.lineTo(10 + bar * sc, H - 10); ctx.strokeStyle = "#8a93a3"; ctx.stroke();
  ctx.fillText(`${bar} m`, 12, H - 14);
  ctx.strokeStyle = "#4c8dff"; ctx.lineWidth = 2 * devicePixelRatio; ctx.beginPath();
  nav.trail.forEach((t, i) => { const [x, y] = toLocal(...t); i ? ctx.lineTo(X(x), Y(y)) : ctx.moveTo(X(x), Y(y)); });
  ctx.stroke();
  nav.waypoints.forEach((w, i) => {
    const [x, y] = toLocal(w.lat, w.lon);
    ctx.fillStyle = i === nav.goalIdx ? "#ffd23f" : "#b07cff";
    ctx.beginPath(); ctx.arc(X(x), Y(y), 5 * devicePixelRatio, 0, 7); ctx.fill();
    ctx.fillText(w.name, X(x) + 8, Y(y) - 6);
    if (i === nav.goalIdx) {
      ctx.strokeStyle = "#ffd23f"; ctx.setLineDash([6, 6]); ctx.beginPath();
      ctx.moveTo(W / 2, H / 2); ctx.lineTo(X(x), Y(y)); ctx.stroke(); ctx.setLineDash([]);
    }
  });
  ctx.fillStyle = "rgba(76,141,255,.15)";                           // accuracy circle + me
  ctx.beginPath(); ctx.arc(W / 2, H / 2, Math.max(4, (nav.acc || 5) * sc), 0, 7); ctx.fill();
  ctx.save(); ctx.translate(W / 2, H / 2); ctx.rotate(rad(nav.heading || 0));
  ctx.fillStyle = "#e8ebf0"; ctx.beginPath();
  const k = 9 * devicePixelRatio; ctx.moveTo(0, -k * 1.4); ctx.lineTo(k * 0.8, k); ctx.lineTo(-k * 0.8, k); ctx.fill();
  ctx.restore();
}
