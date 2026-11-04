// Direction planner: turns the free-space edge into points on the floor (metres), adds the
// obstacles the object detector found, then tries headings from -35° to +35° and picks the one
// with the longest clear corridor (as wide as the rover), preferring the goal direction and
// avoiding sudden swings.
// Uses globals from phone.html: focalPx, groundDistance, imageRowAt, ROVER_HALF_WIDTH, settings.edgeMargin, deg, rad.

const PLAN = { maxHeading: 35, step: 5, far: 8, stopD: 0.6, slowD: 2.0 };
let planLast = 0, planSmooth = 0;

// Free-space edge -> floor points {x: metres right, z: metres ahead}
function floorPoints(path, w, h, fpx) {
  const pts = [], sx = w / path.pw, sy = h / path.ph;
  for (let x = 0; x < path.pw; x++) {
    const u = (x + 0.5) * sx, b = path.boundary[x];
    let Z = b <= path.horizon + 1 ? PLAN.far : groundDistance(b * sy, h, fpx);
    if (Z == null || Z > PLAN.far) Z = PLAN.far;
    pts.push({ x: Z * (u - w / 2) / fpx, z: Z, far: Z >= PLAN.far, kind: "edge" });
  }
  return pts;
}

function planPath(path, confirmed, w, h, goalRel) {
  const fpx = focalPx(w, h), lane = ROVER_HALF_WIDTH + settings.edgeMargin;
  const pts = hasPitch() ? floorPoints(path, w, h, fpx) : [];
  for (const t of confirmed) {                       // detected objects are obstacles too
    if (t.dist == null || t.xl == null) continue;
    // frame-filling boxes are a common false hit of SSD detectors; the path detector already
    // sees anything that really fills the view, so only trust them when very confident
    if (t.box[2] * t.box[3] > 0.5 * w * h && t.score < 0.6) continue;
    for (let k = 0; k <= 4; k++) pts.push({ x: t.xl + (t.xr - t.xl) * k / 4, z: t.dist, far: false, kind: "object" });
  }
  const half = Math.max(10, Math.min(PLAN.maxHeading, deg(Math.atan((w / 2) / fpx)) - 6));
  const cands = [];
  const nSteps = Math.floor(half / PLAN.step);
  for (let k = -nSteps; k <= nSteps; k++) {                // symmetric, includes 0° (straight)
    const a = k * PLAN.step, r = rad(a), s = Math.sin(r), c = Math.cos(r);
    let clear = PLAN.far;
    for (const p of pts) {
      if (p.far) continue;
      const along = p.x * s + p.z * c, lat = Math.abs(p.x * c - p.z * s);
      if (along > 0 && lat < lane) clear = Math.min(clear, along);
    }
    cands.push({ a, clear });
  }
  const g = goalRel == null ? 0 : Math.max(-half, Math.min(half, goalRel));
  let best = cands[0];
  for (const c of cands) {
    c.score = Math.min(c.clear, 5) / 5 - 0.35 * Math.abs(c.a - g) / (2 * half)
              - 0.15 * Math.abs(c.a - planLast) / (2 * half);
    if (c.score > best.score) best = c;
  }
  planLast = best.a;
  planSmooth += 0.35 * (best.a - planSmooth);

  let action, throttle = 0;
  if (path.freeFrac < 0.03) action = "NO PATH";
  else if (best.clear < PLAN.stopD) action = "STOP";
  else {
    action = Math.abs(planSmooth) < 7 ? "FORWARD" : planSmooth < 0 ? "LEFT" : "RIGHT";
    throttle = +Math.min(0.7, 0.2 + 0.12 * best.clear).toFixed(2);
  }
  const moving = action !== "STOP" && action !== "NO PATH";
  const straight = cands.reduce((p, c) => Math.abs(c.a) < Math.abs(p.a) ? c : p);
  return {
    action, throttle, steer: moving ? +(planSmooth / half).toFixed(2) : 0,
    heading: +planSmooth.toFixed(1), clear: +best.clear.toFixed(2), ahead: +straight.clear.toFixed(2),
    goal: goalRel == null ? null : +goalRel.toFixed(0), half,
    cands: cands.map(c => [c.a, +c.clear.toFixed(2)]),
    pts: pts.filter((p, i) => p.kind === "object" || i % 2 === 0).map(p => [+p.x.toFixed(2), +p.z.toFixed(2), p.kind === "object" ? 1 : 0]),
  };
}

// Draw the free space, distance marks, chosen corridor and goal marker on the camera overlay.
function drawPath(ctx, path, plan, w, h, goalLabel) {
  const fpx = focalPx(w, h), sx = w / path.pw, sy = h / path.ph, lane = ROVER_HALF_WIDTH + settings.edgeMargin;
  ctx.fillStyle = path.source === "ai" ? "rgba(0,200,200,.22)" : path.source === "opencv" ? "rgba(76,141,255,.22)" : "rgba(47,191,113,.22)";
  ctx.beginPath(); ctx.moveTo(0, h);
  for (let x = 0; x < path.pw; x++) ctx.lineTo((x + 0.5) * sx, Math.min(h, path.boundary[x] * sy));
  ctx.lineTo(w, h); ctx.closePath(); ctx.fill();

  ctx.font = "12px system-ui"; ctx.lineWidth = 1;
  for (const d of [1, 2, 3, 5]) {
    const v = imageRowAt(d, h, fpx);
    if (v == null || v < 0 || v > h) continue;
    ctx.strokeStyle = "rgba(255,255,255,.25)";
    ctx.beginPath(); ctx.moveTo(0, v); ctx.lineTo(w, v); ctx.stroke();
    ctx.fillStyle = "rgba(255,255,255,.75)"; ctx.fillText(`${d} m`, 4, v - 3);
  }
  if (!plan) return;
  // corridor along the chosen heading, up to the clear distance
  const r = rad(plan.heading), s = Math.sin(r), c = Math.cos(r);
  const proj = (X, Z) => { const v = imageRowAt(Z, h, fpx); return v == null ? null : [w / 2 + fpx * X / Z, v]; };
  const left = [], right = [];
  for (const d of [0.4, 0.7, 1, 1.5, 2, 3, 4, 6, 8]) {
    if (d > plan.clear) break;
    const X = d * s, Z = d * c;
    const L = proj(X - lane * c, Z + lane * s), R = proj(X + lane * c, Z - lane * s);
    if (L && R) { left.push(L); right.push(R); }
  }
  const col = { FORWARD: "#2fbf71", LEFT: "#f2a93b", RIGHT: "#f2a93b" }[plan.action] || "#e5484d";
  if (left.length > 1) {
    ctx.fillStyle = col + "40"; ctx.strokeStyle = col; ctx.lineWidth = 3;
    ctx.beginPath();
    left.forEach((p, i) => i ? ctx.lineTo(...p) : ctx.moveTo(...p));
    [...right].reverse().forEach(p => ctx.lineTo(...p));
    ctx.closePath(); ctx.fill(); ctx.stroke();
  }
  // goal marker at the top, when the waypoint is within the view
  if (plan.goal != null && goalLabel) {
    const a = Math.max(-plan.half - 10, Math.min(plan.half + 10, plan.goal));
    const u = w / 2 + fpx * Math.tan(rad(a));
    ctx.fillStyle = "#ffd23f"; ctx.font = "bold 15px system-ui"; ctx.textAlign = "center";
    ctx.fillText(Math.abs(plan.goal) > plan.half + 10 ? (plan.goal < 0 ? "◀ " : "") + goalLabel + (plan.goal > 0 ? " ▶" : "")
                                                       : "▼ " + goalLabel, Math.max(40, Math.min(w - 40, u)), 60);
    ctx.textAlign = "start";
  }
}
