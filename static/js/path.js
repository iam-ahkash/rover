// Path (free-space) detection: which part of the camera image is ground you can drive on.
// Runs on a small copy of the frame, entirely on the phone. Two detectors:
//   colour - learns what the ground just in front looks like and finds the connected ground
//            that matches it (fast, adapts to tiles, tar, paths, grass)
//   ai     - DeepLab v3 (ADE20K) semantic segmentation: labels floor, road, sidewalk, path,
//            grass, earth... per pixel (slower, understands the scene)
// Uses globals: settings, state, focalPx, cameraPitch, rad, cvs + cvFreeMask (js/cvision.js).

const PATH_LONG = 128;                       // analysis size: 96 x 128 for a portrait frame
const SEG_LONG = 192;                        // DeepLab input (long side); ~1 s on the phone at 224
const pathCanvas = document.createElement("canvas");
const pathCtx = pathCanvas.getContext("2d", { willReadFrequently: true });

// ADE20K class ids that count as walkable / drivable ground
const GROUND_CLASSES = { floor: 4, road: 7, grass: 10, sidewalk: 12, earth: 14, rug: 29, field: 30,
                         sand: 47, path: 53, runway: 55, land: 95 };
const GRASS_CLASSES = new Set([10, 30]);

const groundColour = { mean: null, var: null };
const seg = { model: null, mask: null, pw: 0, ph: 0, t: 0, ms: 0, status: "off" };

function pathSize(w, h) {
  return w >= h ? [PATH_LONG, Math.round(PATH_LONG * h / w)] : [Math.round(PATH_LONG * w / h), PATH_LONG];
}

// Horizon row in analysis pixels (rows above it can never be ground).
function horizonRow(w, h, ph) {
  if (!hasPitch()) return 0;
  const v = h / 2 - focalPx(w, h) * Math.tan(rad(cameraPitch()));
  return Math.max(0, Math.min(ph, v * ph / h));
}

// ---------- colour detector ----------
function colourMask(src, pw, ph) {
  pathCanvas.width = pw; pathCanvas.height = ph;
  pathCtx.drawImage(src, 0, 0, pw, ph);
  const d = pathCtx.getImageData(0, 0, pw, ph).data, n = pw * ph;
  const Y = new Float32Array(n), Cb = new Float32Array(n), Cr = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const r = d[4 * i], g = d[4 * i + 1], b = d[4 * i + 2];
    Y[i] = 0.299 * r + 0.587 * g + 0.114 * b;
    Cb[i] = 128 - 0.1687 * r - 0.3313 * g + 0.5 * b;
    Cr[i] = 128 + 0.5 * r - 0.4187 * g - 0.0813 * b;
  }
  // Seed: the patch of ground just in front (bottom centre of the image).
  const x0 = Math.round(pw * 0.3), x1 = Math.round(pw * 0.7), y0 = Math.round(ph * 0.85);
  const s = [0, 0, 0], q = [0, 0, 0]; let c = 0;
  for (let y = y0; y < ph; y++) for (let x = x0; x < x1; x++) {
    const i = y * pw + x, f = [Y[i], Cb[i], Cr[i]];
    for (let k = 0; k < 3; k++) { s[k] += f[k]; q[k] += f[k] * f[k]; }
    c++;
  }
  const mean = s.map(v => v / c), vr = q.map((v, k) => Math.max(v / c - mean[k] ** 2, 0));
  // Only learn from the seed when it is fairly uniform (not an object right in front).
  const uniform = vr[0] < 40 * 40 && vr[1] < 12 * 12 && vr[2] < 12 * 12;
  if (!groundColour.mean) { groundColour.mean = mean; groundColour.var = vr; }
  else if (uniform) {
    groundColour.mean = groundColour.mean.map((m, k) => m + 0.15 * (mean[k] - m));
    groundColour.var = groundColour.var.map((v, k) => v + 0.15 * (vr[k] - v));
  }
  const [mY, mB, mR] = groundColour.mean;
  const vY = Math.max(groundColour.var[0], 14 * 14), vB = Math.max(groundColour.var[1], 4 * 4),
        vR = Math.max(groundColour.var[2], 4 * 4);
  const raw = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    // brightness counts less than colour so shadows on the path still look like path
    const dist = (Y[i] - mY) ** 2 / (4 * vY) + (Cb[i] - mB) ** 2 / vB + (Cr[i] - mR) ** 2 / vR;
    raw[i] = dist < 10 ? 1 : 0;
  }
  // 3x3 majority filter removes speckle
  const m = new Uint8Array(n);
  for (let y = 1; y < ph - 1; y++) for (let x = 1; x < pw - 1; x++) {
    let k = 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) k += raw[(y + dy) * pw + x + dx];
    m[y * pw + x] = k >= 5 ? 1 : 0;
  }
  for (let x = 0; x < pw; x++) m[(ph - 1) * pw + x] = raw[(ph - 1) * pw + x];
  return m;
}

// ---------- AI detector (DeepLab ADE20K) ----------
async function loadSegmentation() {
  seg.status = "loading";
  try {
    seg.model = await tf.loadGraphModel("vendor/models/deeplab_ade20k/model.json");
    // the first run compiles the GPU shaders (~10 s); do it now, not in the middle of driving
    seg.status = "warming up";
    const short = SEG_LONG * 3 / 4;
    for (const shape of [[1, SEG_LONG, short, 3], [1, short, SEG_LONG, 3]]) {
      const out = tf.tidy(() => seg.model.execute(tf.zeros(shape, "int32")));
      await out.data(); out.dispose();
    }
    seg.status = "ready";
  } catch (e) { seg.status = "failed: " + e.message; }
}

async function runSegmentation(src, w, h) {
  if (!seg.model) return;
  const long = SEG_LONG;
  const sw = w >= h ? long : Math.round(long * w / h), sh = w >= h ? Math.round(long * h / w) : long;
  const t0 = performance.now();
  const labels = tf.tidy(() => {
    const img = tf.image.resizeBilinear(tf.browser.fromPixels(src), [sh, sw]);
    return tf.squeeze(seg.model.execute(tf.cast(tf.expandDims(img), "int32")));
  });
  const [lh, lw] = labels.shape, L = await labels.data();
  labels.dispose();
  const allowed = new Set(Object.values(GROUND_CLASSES).filter(c => settings.allowGrass || !GRASS_CLASSES.has(c)));
  const [pw, ph] = pathSize(w, h), m = new Uint8Array(pw * ph);
  for (let y = 0; y < ph; y++) {
    const sy = Math.min(lh - 1, Math.floor((y + 0.5) * lh / ph));
    for (let x = 0; x < pw; x++) {
      const sx = Math.min(lw - 1, Math.floor((x + 0.5) * lw / pw));
      m[y * pw + x] = allowed.has(L[sy * lw + sx]) ? 1 : 0;
    }
  }
  Object.assign(seg, { mask: m, pw, ph, t: performance.now(), ms: performance.now() - t0 });
}

// ---------- free-space edge ----------
// For each column, walk up from the bottom while the pixels are ground (gaps of 1-2 px allowed).
// boundary[x] = top-most ground row reached; ph means "blocked right at the bottom".
function freeBoundary(mask, pw, ph, top) {
  const b = new Int16Array(pw);
  for (let x = 0; x < pw; x++) {
    let last = ph, miss = 0;
    for (let y = ph - 1; y >= top; y--) {
      if (mask[y * pw + x]) { last = y; miss = 0; } else if (++miss >= 3) break;
    }
    b[x] = last;
  }
  const out = new Int16Array(pw);           // median of 5 columns
  for (let x = 0; x < pw; x++) {
    const win = [];
    for (let k = -2; k <= 2; k++) win.push(b[Math.max(0, Math.min(pw - 1, x + k))]);
    out[x] = win.sort((p, q) => p - q)[2];
  }
  return out;
}

function detectPath(src, w, h) {
  const [pw, ph] = pathSize(w, h);
  const top = Math.ceil(horizonRow(w, h, ph));
  const aiFresh = settings.pathMode === "ai" && seg.mask && seg.pw === pw && seg.ph === ph &&
                  performance.now() - seg.t < 2000;
  const useCv = !aiFresh && settings.pathMode === "opencv" && cvs.ready;
  const mask = aiFresh ? seg.mask : useCv ? cvFreeMask(src, pw, ph, top) : colourMask(src, pw, ph);
  const boundary = freeBoundary(mask, pw, ph, top);
  let free = 0;
  for (let x = 0; x < pw; x++) free += ph - boundary[x];
  return { pw, ph, mask, boundary, horizon: top, source: aiFresh ? "ai" : useCv ? "opencv" : "colour",
           freeFrac: free / (pw * Math.max(1, ph - top)) };
}
