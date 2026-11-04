// Classic computer vision with OpenCV.js (WebAssembly, stored on the phone), no names, no training:
//  1. Free ground: blur -> YCrCb -> Canny edges (strong brightness or weak colour) act as walls -> flood fill from the ground just
//     in front of the camera (several seeds) -> morphological close/open. Edges of kerbs, walls, poles,
//     boxes stop the fill even when they are the same colour as the floor.
//  2. Obstacle blobs: holes in the free ground (contour hierarchy) = things with ground all around.
//  3. Optical flow (Lucas-Kanade on Shi-Tomasi corners): how the picture moves between frames ->
//     turning left/right, moving or still, and "looming": things in the middle that grow quickly
//     (time to contact), which flags an obstacle you are closing in on, whatever it is.
// Uses globals: state, settings, sleep.

const cvs = { ready: false, status: "off", canvas: document.createElement("canvas"), prevGray: null, prevPts: null,
              lastT: 0, ms: 0, flowMs: 0, flow: null, blobs: [] };
cvs.ctx = cvs.canvas.getContext("2d", { willReadFrequently: true });

async function loadOpenCV() {
  cvs.status = "loading";
  try {
    await new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = "vendor/opencv.js"; s.async = true; s.onload = res; s.onerror = () => rej(new Error("opencv.js not found"));
      document.head.appendChild(s);
    });
    if (window.cv instanceof Promise) window.cv = await window.cv;
    else if (!cv.Mat) await new Promise(r => { cv.onRuntimeInitialized = r; });
    cvs.ready = true; cvs.status = "ready";
  } catch (e) { cvs.status = "failed: " + e.message; }
}

function cvFrame(src, pw, ph) {
  if (cvs.canvas.width !== pw || cvs.canvas.height !== ph) { cvs.canvas.width = pw; cvs.canvas.height = ph; }
  cvs.ctx.drawImage(src, 0, 0, pw, ph);
  return cv.matFromImageData(cvs.ctx.getImageData(0, 0, pw, ph));
}

// ---------- 1 + 2: free ground and obstacle blobs ----------
function cvFreeMask(src, pw, ph, top) {
  const t0 = performance.now();
  const rgba = cvFrame(src, pw, ph), rgb = new cv.Mat(), blur = new cv.Mat(), ycc = new cv.Mat(), ch = new cv.MatVector(),
        eY = new cv.Mat(), eA = new cv.Mat(), eB = new cv.Mat(), edges = new cv.Mat(), fillImg = new cv.Mat(),
        mask = cv.Mat.zeros(ph + 2, pw + 2, cv.CV_8UC1), k3 = cv.Mat.ones(3, 3, cv.CV_8U),
        k5 = cv.getStructuringElement(cv.MORPH_ELLIPSE, new cv.Size(5, 5)), free = new cv.Mat();
  const parts = [];
  try {
    cv.cvtColor(rgba, rgb, cv.COLOR_RGBA2RGB);
    cv.GaussianBlur(rgb, blur, new cv.Size(5, 5), 0);
    // YCrCb: shadows mostly change brightness (Y), real boundaries usually change colour too
    cv.cvtColor(blur, ycc, cv.COLOR_RGB2YCrCb);
    cv.split(ycc, ch);
    const Y = ch.get(0), Cr = ch.get(1), Cb = ch.get(2); parts.push(Y, Cr, Cb);
    // edge sensitivity (Calibration slider, 1-10, default 5): higher = more edges, the fill stops sooner
    const k = Math.pow(1.25, 5 - (settings.edgeSens || 5));
    cv.Canny(Y, eY, 80 * k, 200 * k);                // only strong brightness edges
    cv.Canny(Cr, eA, 12 * k, 36 * k); cv.Canny(Cb, eB, 12 * k, 36 * k);   // weak colour edges count
    cv.bitwise_or(eY, eA, edges); cv.bitwise_or(edges, eB, edges);
    cv.dilate(edges, edges, k3);                     // close small gaps so the fill can't leak
    // fill on (Y/3, 1.5 Cr, 1.5 Cb): brightness changes count a third as much as colour changes
    const y3 = new cv.Mat(), cr2 = new cv.Mat(), cb2 = new cv.Mat(), v = new cv.MatVector(); parts.push(y3, cr2, cb2);
    Y.convertTo(y3, -1, 0.35, 0); Cr.convertTo(cr2, -1, 1.5, -64); Cb.convertTo(cb2, -1, 1.5, -64);
    v.push_back(y3); v.push_back(cr2); v.push_back(cb2); cv.merge(v, fillImg); v.delete();
    // edges (value 1) block the fill; nothing above the horizon can be ground
    const inner = mask.roi(new cv.Rect(1, 1, pw, ph));
    cv.threshold(edges, inner, 0, 1, cv.THRESH_BINARY);
    if (top > 0) inner.roi(new cv.Rect(0, 0, pw, Math.min(ph, top))).setTo(new cv.Scalar(1));
    inner.delete();
    const lo = new cv.Scalar(4 * k, 5 * k, 5 * k), hi = new cv.Scalar(4 * k, 5 * k, 5 * k), rect = new cv.Rect();
    const flags = 8 | cv.FLOODFILL_MASK_ONLY | (255 << 8);
    for (const fx of [0.5, 0.35, 0.65, 0.2, 0.8]) {   // seeds along the bottom; skip ones on an edge
      for (const fy of [0.95, 0.88]) {
        const x = Math.round(fx * (pw - 1)), y = Math.round(fy * (ph - 1));
        if (mask.ucharPtr(y + 1, x + 1)[0] === 0) cv.floodFill(fillImg, mask, new cv.Point(x, y), new cv.Scalar(0), rect, lo, hi, flags);
      }
    }
    const filled = mask.roi(new cv.Rect(1, 1, pw, ph));
    cv.threshold(filled, free, 254, 255, cv.THRESH_BINARY);
    filled.delete();
    cv.morphologyEx(free, free, cv.MORPH_CLOSE, k5);   // fill joints/cracks inside the ground
    cv.morphologyEx(free, free, cv.MORPH_OPEN, k3);    // drop thin leaks
    cvs.blobs = cvBlobs(free, pw, ph);
    const out = new Uint8Array(pw * ph), d = free.data;
    for (let i = 0; i < out.length; i++) out[i] = d[i] ? 1 : 0;
    cvs.ms = performance.now() - t0;
    return out;
  } finally {
    [rgba, rgb, blur, ycc, ch, eY, eA, eB, edges, fillImg, mask, k3, k5, free, ...parts].forEach(m => m.delete());
  }
}

// Obstacles with ground all around them = holes in the free-ground region (contour hierarchy).
function cvBlobs(free, pw, ph) {
  const work = free.clone(), contours = new cv.MatVector(), hier = new cv.Mat(), blobs = [];
  try {
    cv.findContours(work, contours, hier, cv.RETR_CCOMP, cv.CHAIN_APPROX_SIMPLE);
    for (let i = 0; i < contours.size(); i++) {
      const parent = hier.data32S[4 * i + 3], c = contours.get(i);
      if (parent >= 0) {                                         // a hole inside the ground
        const a = cv.contourArea(c), r = cv.boundingRect(c);
        if (a >= pw * ph * 0.002) blobs.push({ x: r.x, y: r.y, w: r.width, h: r.height, area: a });
      }
      c.delete();
    }
  } finally { work.delete(); contours.delete(); hier.delete(); }
  return blobs;
}

// ---------- 3: optical flow ----------
function cvFlow(src, pw, ph) {
  const t0 = performance.now(), now = performance.now();
  const rgba = cvFrame(src, pw, ph), gray = new cv.Mat();
  cv.cvtColor(rgba, gray, cv.COLOR_RGBA2GRAY); rgba.delete();
  const dt = (now - cvs.lastT) / 1000; cvs.lastT = now;
  let result = null;
  if (cvs.prevGray && cvs.prevGray.cols === pw && cvs.prevGray.rows === ph && cvs.prevPts && cvs.prevPts.rows >= 8 && dt < 1) {
    const next = new cv.Mat(), st = new cv.Mat(), err = new cv.Mat();
    cv.calcOpticalFlowPyrLK(cvs.prevGray, gray, cvs.prevPts, next, st, err, new cv.Size(15, 15), 2,
      new cv.TermCriteria(cv.TermCriteria_EPS | cv.TermCriteria_COUNT, 10, 0.03));
    const vecs = [], cx = pw / 2, cy = ph / 2;
    for (let i = 0; i < st.rows; i++) {
      if (!st.data[i]) continue;
      const x0 = cvs.prevPts.data32F[2 * i], y0 = cvs.prevPts.data32F[2 * i + 1];
      const x1 = next.data32F[2 * i], y1 = next.data32F[2 * i + 1];
      if (Math.hypot(x1 - x0, y1 - y0) > pw / 4) continue;              // bad match
      vecs.push([x0, y0, x1, y1]);
    }
    next.delete(); st.delete(); err.delete();
    if (vecs.length >= 6) {
      const med = a => { const s = a.slice().sort((p, q) => p - q); return s[s.length >> 1]; };
      const dx = med(vecs.map(v => v[2] - v[0])), dy = med(vecs.map(v => v[3] - v[1]));
      // looming: after removing the common shift, points in the middle third moving away from the
      // centre = something getting bigger. tau = r / (dr/dt) is the time to contact.
      const taus = [];
      for (const [x0, y0, x1, y1] of vecs) {
        if (Math.abs(x0 - cx) > pw / 3 || Math.abs(y0 - cy) > ph / 3) continue;
        const r0 = Math.hypot(x0 - cx, y0 - cy), r1 = Math.hypot(x1 - dx - cx, y1 - dy - cy);
        if (r0 > 4 && r1 - r0 > 0.05) taus.push(r0 / ((r1 - r0) / dt));
      }
      const centre = vecs.filter(v => Math.abs(v[0] - cx) <= pw / 3 && Math.abs(v[1] - cy) <= ph / 3).length;
      const ttc = taus.length >= Math.max(4, centre * 0.5) ? med(taus) : null;
      const s = Math.max(state.frameSize?.[0] || pw, state.frameSize?.[1] || ph) / Math.max(pw, ph);
      result = { n: vecs.length, dx: dx * s, dy: dy * s, turn: dx / dt * s,           // px/s in camera pixels
                 moving: Math.hypot(dx, dy) > 0.3 || taus.length > 3, ttc: ttc != null && ttc < 10 ? ttc : null,
                 vecs: vecs.map(v => v.map(c => c * s)) };
    }
  }
  // new corners every frame (cheap at this size) for the next step
  cvs.prevPts?.delete();
  cvs.prevPts = new cv.Mat();
  cv.goodFeaturesToTrack(gray, cvs.prevPts, 80, 0.01, 5);
  cvs.prevGray?.delete(); cvs.prevGray = gray;
  cvs.flow = result;
  cvs.flowMs = performance.now() - t0;
  return result;
}

function drawFlow(ctx, flow, w, h) {
  if (!flow) return;
  ctx.strokeStyle = "rgba(120,220,255,.85)"; ctx.lineWidth = 1.5;
  for (const [x0, y0, x1, y1] of flow.vecs) {
    const ex = x0 + (x1 - x0) * 3, ey = y0 + (y1 - y0) * 3;         // 3x longer so they are visible
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(ex, ey); ctx.stroke();
    ctx.fillStyle = "rgba(120,220,255,.85)"; ctx.fillRect(ex - 1, ey - 1, 2, 2);
  }
  if (flow.ttc != null && flow.ttc < 3) {
    ctx.strokeStyle = "#e5484d"; ctx.lineWidth = 3;
    ctx.strokeRect(w / 6, h / 6, w * 2 / 3, h * 2 / 3);
    ctx.fillStyle = "#e5484d"; ctx.font = "bold 16px system-ui";
    ctx.fillText(`closing in · ${flow.ttc.toFixed(1)} s`, w / 6 + 6, h / 6 + 20);
  }
}

function drawBlobs(ctx, blobs, path, w, h) {
  const sx = w / path.pw, sy = h / path.ph;
  ctx.strokeStyle = "rgba(255,120,200,.9)"; ctx.lineWidth = 2; ctx.setLineDash([5, 4]);
  for (const b of blobs) {
    // only holes inside the walkable area (below the free-ground edge), not gaps up in the scenery
    const col = Math.min(path.pw - 1, Math.round(b.x + b.w / 2));
    if (b.y + b.h <= path.boundary[col]) continue;
    ctx.strokeRect(b.x * sx, b.y * sy, b.w * sx, b.h * sy);
  }
  ctx.setLineDash([]);
}
