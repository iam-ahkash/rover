// Obstacles, without names: anything that blocks the free ground.
//  - edge obstacles: where the walkable ground ends (walls, kerbs, poles, bushes, feet...),
//    found from the path detector's free-space edge, so they need no object classes at all
//  - box obstacles: the object detector (COCO-SSD) used only as "something is there"
// Each obstacle gets a distance (m), sideways extent (m) and angle (°, negative = left).
// Uses globals: settings, focalPx, groundDistance, deg.

const OBST_MAX = 4;      // edge points farther than this are not reported as obstacles

// Typical real heights (m), only used for a box's distance when its bottom is hidden.
const TYPICAL_HEIGHT = { person: 1.7, bicycle: 1.05, car: 1.5, motorcycle: 1.1, bus: 3, truck: 3,
  bench: 0.85, dog: 0.55, cat: 0.3, chair: 0.9, couch: 0.85, "potted plant": 0.5, "dining table": 0.75,
  "fire hydrant": 0.75, "stop sign": 0.75, suitcase: 0.65, backpack: 0.45, bottle: 0.25, tv: 0.55 };

// ---------- box obstacles (detector, tracked across frames, class ignored) ----------
let boxTracks = [], nextBoxId = 1;

function iou(a, b) {
  const x1 = Math.max(a[0], b[0]), y1 = Math.max(a[1], b[1]);
  const x2 = Math.min(a[0] + a[2], b[0] + b[2]), y2 = Math.min(a[1] + a[3], b[1] + b[3]);
  const inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  return inter / (a[2] * a[3] + b[2] * b[3] - inter || 1);
}

function boxDistance(cls, [x, y, bw, bh], w, h, fpx) {
  if (y + bh < h - 3) {                                  // bottom visible: where it meets the floor
    const d = groundDistance(y + bh, h, fpx);
    if (d != null) return d;
  }
  const H = TYPICAL_HEIGHT[cls];
  return H && y > 3 && bh > 8 ? H * fpx / bh : null;
}

function trackBoxes(dets, w, h) {
  const used = new Set();
  for (const t of boxTracks) {
    let best = -1, bestIou = 0.25;
    dets.forEach((d, i) => {
      if (used.has(i)) return;
      const o = iou(t.box, d.bbox); if (o > bestIou) { bestIou = o; best = i; }
    });
    if (best >= 0) {
      used.add(best);
      t.box = t.box.map((v, k) => v + 0.6 * (dets[best].bbox[k] - v));
      t.score = dets[best].score; t.cls = dets[best].class; t.hits++; t.misses = 0;
    } else t.misses++;
  }
  dets.forEach((d, i) => {
    if (!used.has(i)) boxTracks.push({ id: nextBoxId++, cls: d.class, box: d.bbox.slice(),
                                       score: d.score, hits: 1, misses: 0, dist: null });
  });
  boxTracks = boxTracks.filter(t => t.misses <= 4);
  const fpx = focalPx(w, h);
  for (const t of boxTracks) {
    const d = boxDistance(t.cls, t.box, w, h, fpx);
    t.dist = d == null ? null : t.dist == null ? d : t.dist + 0.4 * (d - t.dist);
    if (t.dist != null) {
      t.xl = t.dist * (t.box[0] - w / 2) / fpx;
      t.xr = t.dist * (t.box[0] + t.box[2] - w / 2) / fpx;
    }
  }
  // seen in 2+ frames; frame-filling boxes are a common false hit unless very confident
  return boxTracks.filter(t => t.hits >= 2 && t.misses <= 2 &&
                               !(t.box[2] * t.box[3] > 0.5 * w * h && t.score < 0.6));
}

// ---------- edge obstacles (from the free-space edge) ----------
function edgeObstacles(path, w, h) {
  const fpx = focalPx(w, h), sx = w / path.pw, sy = h / path.ph, cols = [];
  for (let x = 0; x < path.pw; x++) {
    const b = path.boundary[x];
    if (b <= path.horizon + 1) { cols.push(null); continue; }      // free up to the horizon
    const z = b >= path.ph ? groundDistance(h, h, fpx) : groundDistance(b * sy, h, fpx);
    if (z == null || z > OBST_MAX) { cols.push(null); continue; }
    const u = (x + 0.5) * sx;
    cols.push({ x: z * (u - w / 2) / fpx, z, u, v: Math.min(h, b * sy) });
  }
  // group neighbouring columns at a similar distance into one obstacle
  const groups = [];
  let g = null;
  for (const c of cols) {
    if (c && g && Math.abs(c.z - g.at(-1).z) < 0.35 + 0.15 * c.z) g.push(c);
    else { if (g) groups.push(g); g = c ? [c] : null; }
  }
  if (g) groups.push(g);
  return groups.filter(p => p.length >= 3).map(p => {
    const near = p.reduce((a, c) => c.z < a.z ? c : a);
    return { kind: "edge", dist: near.z, xl: Math.min(...p.map(c => c.x)), xr: Math.max(...p.map(c => c.x)),
             angle: deg(Math.atan2(near.x, near.z)), pts: p.map(c => [c.u, c.v]), at: [near.u, near.v] };
  });
}

// All obstacles, nearest first.
function listObstacles(boxes, edges, w, h) {
  const fpx = focalPx(w, h);
  const fromBoxes = boxes.filter(t => t.dist != null).map(t => {
    const u = t.box[0] + t.box[2] / 2;
    return { kind: "box", dist: t.dist, xl: t.xl, xr: t.xr, angle: deg(Math.atan((u - w / 2) / fpx)),
             box: t.box, at: [u, t.box[1] + t.box[3]] };
  });
  return [...edges, ...fromBoxes].sort((a, b) => a.dist - b.dist);
}

function drawObstacles(ctx, obstacles, boxes) {
  ctx.lineWidth = 3; ctx.font = "bold 14px system-ui";
  for (const t of boxes) {                         // detector boxes, no names
    ctx.strokeStyle = t.dist != null && t.dist < 2 ? "#e5484d" : "#f2a93b";
    ctx.strokeRect(...t.box);
  }
  for (const o of obstacles) {
    const col = o.dist < 1 ? "#e5484d" : o.dist < 2 ? "#f2a93b" : "#ffd23f";
    if (o.kind === "edge") {
      ctx.strokeStyle = col; ctx.beginPath();
      o.pts.forEach((p, i) => i ? ctx.lineTo(...p) : ctx.moveTo(...p)); ctx.stroke();
    }
    const label = `${o.dist.toFixed(1)} m`, [u, v] = o.at, tw = ctx.measureText(label).width + 8;
    const x = Math.max(0, Math.min(ctx.canvas.width - tw, u - tw / 2)), y = Math.max(18, v - 6);
    ctx.fillStyle = "rgba(0,0,0,.6)"; ctx.fillRect(x, y - 15, tw, 18);
    ctx.fillStyle = col; ctx.fillText(label, x + 4, y - 1);
  }
}
