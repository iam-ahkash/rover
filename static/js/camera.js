// One camera at the lowest resolution the phone offers (prefers the ultra-wide lens), plus the
// camera geometry that turns image rows into distances along the floor.

// Lenses of this phone (factory calibration, `adb shell dumpsys media.camera`): long-side field of view.
const KNOWN_CAMS = {
  "0": { name: "main", fov: 69.6 },
  "2": { name: "macro", fov: 71.6 },
  "3": { name: "ultra-wide", fov: 95.7 },
  "4": { name: "main (multi)", fov: 69.6 },
};
const video = $("video");
const camIdOf = label => (label.match(/camera2? ?(\d+)/i) || label.match(/^(\d+)/) || [])[1];
let backCams = [];

function stopCamera() {
  if (video.srcObject) { video.srcObject.getTracks().forEach(t => t.stop()); video.srcObject = null; }
}

async function openCamera(deviceId) {
  stopCamera();
  const c = { width: { ideal: 320 }, height: { ideal: 240 }, frameRate: { ideal: 15, max: 30 } };
  if (deviceId) c.deviceId = { exact: deviceId };
  else c.facingMode = { ideal: "environment" };
  const stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: c });
  video.srcObject = stream;
  await video.play();
  const track = stream.getVideoTracks()[0], label = track.label || "", s = track.getSettings();
  const known = KNOWN_CAMS[camIdOf(label)];
  state.source = "camera"; state.camId = camIdOf(label);
  state.camera = `${known ? known.name : label || "camera"} ${s.width}×${s.height}`;
  if (known && !settings.fovManual) settings.fov = known.fov;
  return known;
}

async function startCamera() {
  await openCamera();                                  // first open unlocks the lens names
  backCams = (await navigator.mediaDevices.enumerateDevices())
    .filter(d => d.kind === "videoinput" && !/front/i.test(d.label));
  const sel = $("set-cam");
  sel.length = 1;
  for (const d of backCams) {
    const k = KNOWN_CAMS[camIdOf(d.label)];
    sel.add(new Option(k ? `${k.name} — ${k.fov}°` : d.label || d.deviceId.slice(0, 8), d.deviceId));
  }
  const ultra = backCams.find(d => KNOWN_CAMS[camIdOf(d.label)]?.name === "ultra-wide");
  const pick = backCams.find(d => d.deviceId === settings.camId) || ultra;
  sel.value = settings.camId && pick ? pick.deviceId : "";
  if (pick) { stopCamera(); await sleep(500); await openCamera(pick.deviceId); }
}

// ---------- geometry ----------
const hasPitch = () => state.pitch != null;
const cameraPitch = () => state.pitch + (settings.pitchOffset || 0);

// Pinhole camera: focal length in pixels from the field of view across the long side.
function focalPx(w, h) { return (Math.max(w, h) / 2) / Math.tan(rad(settings.fov) / 2); }

// Distance along the floor to image row v (camera height + downward tilt from the accelerometer).
function groundDistance(v, h, fpx) {
  if (!hasPitch()) return null;
  const below = rad(cameraPitch()) + Math.atan((v - h / 2) / fpx);   // angle below the horizon
  // near the horizon the distance blows up; past ~88° (pointing straight down) the ray is behind the feet
  if (below < rad(1.5) || below > rad(88)) return null;
  return Math.min(settings.camH / Math.tan(below), 20);
}

// Image row where a floor point d metres ahead appears.
function imageRowAt(d, h, fpx) {
  if (!hasPitch()) return null;
  return h / 2 + fpx * Math.tan(Math.atan(settings.camH / d) - rad(cameraPitch()));
}
