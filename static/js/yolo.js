// YOLO11n obstacle detector (Ultralytics, exported to ONNX at 320x320 with tools/export_models.py),
// run on the phone's GPU with onnxruntime-web (WebGPU). Same output shape as COCO-SSD's detect()
// ({bbox: [x, y, w, h], score, class}) so the tracker and planner don't change. The class is only
// used for the typical-size distance fallback; obstacles are shown without names.
// Benchmarked on this phone: ~120 ms per frame on WebGPU (COCO-SSD lite 130 ms), far more objects found.

const YOLO_SIZE = 320;
const COCO_NAMES = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
  "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
  "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
  "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
  "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich",
  "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed",
  "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave", "oven",
  "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"];

async function loadYolo() {
  if (!navigator.gpu) throw new Error("no WebGPU in this browser");
  ort.env.wasm.wasmPaths = new URL("vendor/ort/", location.href).href;
  ort.env.wasm.numThreads = 1;
  // Right after a restart the GPU may still be held by the previous run ("failed to allocate a
  // buffer"), so try a few times before falling back to COCO-SSD.
  let session;
  for (let attempt = 1; ; attempt++) {
    try {
      session = await ort.InferenceSession.create("vendor/models/yolo11n/yolo11n.onnx",
        { executionProviders: ["webgpu"], graphOptimizationLevel: "all" });
      break;
    } catch (e) {
      if (attempt >= 3) throw e;
      console.warn("YOLO attempt", attempt, e);
      await new Promise(r => setTimeout(r, 2000 * attempt));
    }
  }
  const canvas = document.createElement("canvas"); canvas.width = canvas.height = YOLO_SIZE;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  const input = new Float32Array(3 * YOLO_SIZE * YOLO_SIZE);

  async function detect(src, maxBoxes = 15, minScore = 0.3) {
    const vw = src.videoWidth || src.width, vh = src.videoHeight || src.height, n = YOLO_SIZE * YOLO_SIZE;
    const s = Math.min(YOLO_SIZE / vw, YOLO_SIZE / vh);            // letterbox, image at top-left
    ctx.fillStyle = "rgb(114,114,114)"; ctx.fillRect(0, 0, YOLO_SIZE, YOLO_SIZE);
    ctx.drawImage(src, 0, 0, vw * s, vh * s);
    const d = ctx.getImageData(0, 0, YOLO_SIZE, YOLO_SIZE).data;
    for (let i = 0; i < n; i++) { input[i] = d[4 * i] / 255; input[n + i] = d[4 * i + 1] / 255; input[2 * n + i] = d[4 * i + 2] / 255; }
    const out = (await session.run({ [session.inputNames[0]]: new ort.Tensor("float32", input, [1, 3, YOLO_SIZE, YOLO_SIZE]) }))[session.outputNames[0]];
    const p = out.data, N = out.dims[2], C = out.dims[1] - 4, cand = [];
    for (let i = 0; i < N; i++) {                                  // [1, 84, N]: cx, cy, w, h, 80 scores
      let best = 0, cls = 0;
      for (let c = 0; c < C; c++) { const v = p[(4 + c) * N + i]; if (v > best) { best = v; cls = c; } }
      if (best < minScore) continue;
      const w = p[2 * N + i] / s, h = p[3 * N + i] / s, x = p[i] / s - w / 2, y = p[N + i] / s - h / 2;
      const x0 = Math.max(0, x), y0 = Math.max(0, y);
      cand.push({ bbox: [x0, y0, Math.min(vw, x + w) - x0, Math.min(vh, y + h) - y0], score: best, class: COCO_NAMES[cls] });
    }
    out.dispose?.();
    cand.sort((a, b) => b.score - a.score);
    const keep = [];                                               // class-agnostic NMS: one box per thing
    for (const c of cand) {
      if (keep.length >= maxBoxes) break;
      if (keep.every(k => iou(k.bbox, c.bbox) < 0.45)) keep.push(c);
    }
    return keep;
  }
  return { detect, name: "YOLO11n", engine: "webgpu" };
}

// YOLO11n on the phone's NPU (Android app only, android/src/.../NpuYolo.java). The frame goes to
// the native side as a small JPEG; TensorFlow Lite runs the network on the MediaTek APU through
// Android's Neural Networks API and sends back the boxes. Same detect() result as above.
// accel: "npu" (MDLA), "neuron", "dsp", "nnapi-gpu" or "cpu".
async function loadYoloNpu(accel = "npu") {
  if (!window.AndroidBridge?.npuInit) throw new Error("NPU needs the Android app");
  const r = AndroidBridge.npuInit(accel);
  if (!r.startsWith("ok")) throw new Error(r.replace(/^ERROR /, ""));
  const canvas = document.createElement("canvas"), ctx = canvas.getContext("2d");
  const det = { name: "YOLO11n", engine: accel === "cpu" ? "cpu (tflite)" : accel === "npu" ? "NPU" : accel,
                initMs: +r.split(" ")[1], npuMs: 0, preMs: 0 };
  det.detect = async (src, maxBoxes = 15, minScore = 0.3) => {
    const vw = src.videoWidth || src.width, vh = src.videoHeight || src.height;
    if (canvas.width !== vw || canvas.height !== vh) { canvas.width = vw; canvas.height = vh; }
    ctx.drawImage(src, 0, 0, vw, vh);
    const res = JSON.parse(AndroidBridge.npuDetect(canvas.toDataURL("image/jpeg", 0.85), minScore, maxBoxes));
    if (res.error) throw new Error(res.error);
    det.npuMs = res.ms; det.preMs = res.pre;
    return res.boxes.map(([x, y, w, h, score, c]) => ({ bbox: [x, y, w, h], score, class: COCO_NAMES[c] }));
  };
  return det;
}
