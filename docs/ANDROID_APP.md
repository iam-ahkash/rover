# Rover Phone ML — Android app

**File:** `android/out/RoverPhoneML.apk` (55 MB, version 1.0, package `com.rover.phoneml`)
**Needs:** Android 8.0 or newer with a back camera. GPS and Wi-Fi are optional.
Tested on a Xiaomi 22011211C running LineageOS.

The phone becomes the rover's brain. It finds the free ground, detects obstacles with their
distance and direction, plans where to drive, follows GPS waypoints on an OpenStreetMap map, and
records everything on the phone. **Everything runs on the phone.** No Mac, server, internet or SIM
is needed. Only map tiles use the internet, and only the first time an area is viewed.

---

## 1. Install

**Option A — from the Mac (USB or Wireless debugging):**
```bash
adb install -r "android/out/RoverPhoneML.apk"
```

**Option B — copy the file to the phone:** send `RoverPhoneML.apk` to the phone (LocalSend, USB,
Drive, email…). Open it in the phone's Files app and tap **Install**. If Android asks, allow
*Install unknown apps* for the app you opened it with.

To update, install the new APK over the old one. Your settings, saved spots and recordings stay.
Updates must be signed with the same key (`android/keystore/rover.jks`), so keep that file.

## 2. First start

1. Open **Rover Phone ML**. Allow **Camera** and **Location** (choose *While using the app*, *Precise*).
2. Tap **Start camera, sensors & ML**. **Drive mode** switches on (see §3).
   - The first time, Android asks to **pin the app**. Accept.
   - The first time, the **Do Not Disturb access** screen opens. Switch it on for Rover Phone ML,
     then go back. This is only needed once.
3. Wait about 5–10 s. The pills should turn green:

| Pill | Meaning |
|---|---|
| `ultra-wide 240×320` | Camera on (one lens, smallest size) |
| `ML: YOLO11n` | Obstacle model running on the GPU. `ML: fast (YOLO unavailable…)` = fallback to COCO-SSD |
| `IMU` | Tilt sensor working (needed for distances) |
| `GPS ±3 m` | Location fix (go outdoors if it says *searching*) |
| `built-in (APK)` | All files are inside the app; works offline |
| `drive mode: …` | What Drive mode switched on. **Tap it to switch Drive mode off or on.** |

## 3. Drive mode — the models get the whole phone

Android does not let an app stop other apps. Drive mode does the closest safe thing:

| What | Effect |
|---|---|
| **App pinning** | No other app can come to the front (no pop-ups, no accidental switching). This matters because the camera and models pause when the app isn't in front. |
| **Do Not Disturb** (alarms only) | Notifications and calls are held back while driving. Your previous setting comes back when Drive mode ends. |
| **Sustained performance** | Steady CPU/GPU speed instead of bursts and throttling, on phones that support it. The pill shows `steady-speed` if so. |
| **Screen kept on, full screen** | The phone never locks or dims while the app is open. |

**To leave:** tap the `drive mode` pill. Or **press and hold Back + Overview (□)** to unpin, or
swipe up and hold on gesture navigation. If *App pinning* is off in Settings → Security, the app
still runs, but it isn't pinned (the pill says `pin-failed`).

## 4. Using it

### Screen
- **Big label (top left):** the driving command: **FORWARD / LEFT n° / RIGHT n° / STOP / NO PATH**.
- **Green/orange corridor:** the chosen way ahead, as wide as the rover.
- **Blue/green fill:** free ground.
- **Red/orange/yellow lines and boxes:** obstacles (under 1 m / under 2 m / further), each with a distance.
- **Light-blue arrows:** optical flow (how the picture moves).
- A **"closing in · 0.8 s"** frame means something in the middle is approaching fast, so the command is **STOP**.
- **Top right:** fps, model time, path detector, motion and turning, clear distance.

### Obstacles card
Each obstacle is shown as **obstacle · distance · angle (left/right) · width**, nearest first.
Object names are never shown.

### Calibrate once (better distances)
1. Tap **🚶 Handheld (1.3 m)** or **🚗 Rover (0.2 m)**, or type the camera height.
2. Put something on the floor at a measured distance (for example 2.00 m) and type the distance.
3. **Tap the camera picture exactly where it touches the floor.** The card shows ✓ Calibrated.

### GPS navigation
- **📍 Save here** saves the current spot. **Tap the map** to add a destination anywhere.
- **Go to** picks a destination. The card shows its distance and the turn to make, and the planner
  steers towards it along the free path.
- **⌖** follows you again after you pan the map. **⤢** shows everything.
- Map tiles you have seen are kept for offline use.

### Recording
1. **● Start recording** saves 2 samples per second on the phone.
2. **■ Stop recording**.
3. **CSV** or **JSON** saves the file to **Downloads/RoverPhoneML/** (open it with Files, or send
   it with LocalSend, Drive or email).

| CSV column | Meaning |
|---|---|
| `t` | time (UTC, ISO) |
| `lat`, `lon`, `acc` | filtered position, accuracy (m) |
| `speed`, `heading` | m/s, degrees from north (camera direction) |
| `pitch` | camera tilt down (°) |
| `action`, `cmdHeading`, `steer`, `throttle` | planner command (`steer` −1 left … +1 right, `throttle` 0…0.7) |
| `clear`, `ahead` | clear distance on the chosen heading / straight ahead (m) |
| `nearDist`, `nearAngle`, `obstacles` | nearest obstacle (m, °) and how many |
| `free` | fraction of the view that is free ground |
| `ttc`, `flowTurn` | optical-flow time to contact (s), turning rate |
| `pathSrc` | path detector used (opencv / colour / ai) |
| `goal`, `goalDist` | navigation target and distance (m) |
| `fps` | frames per second |

### Settings
| Setting | Choices |
|---|---|
| Obstacle model | **YOLO11n — best (GPU)** · Fast (SSDLite) · Accurate (not included in the APK; falls back to Fast) |
| Path detector | **OpenCV** (edges + flood fill, ~14 ms) · Colour · AI segmentation (DeepLab, ~1 s) |
| Grass counts as path | for the AI detector |
| Camera | auto = ultra-wide; any back lens |
| Lens field of view | set automatically for this phone's lenses |
| Reset calibration | back to defaults |

## 5. How it works

```
camera 240×320 ─┬─ YOLO11n (WebGPU, ~70 ms) ──── box obstacles ─┐
                ├─ OpenCV: YCrCb Canny edges + flood fill ──────┼─ free ground ─ edge obstacles ─┐
                └─ OpenCV: Lucas-Kanade optical flow ── time to contact ─────────────────────────┤
accelerometer ── camera tilt ── floor geometry (distance = height / tan(angle below horizon)) ────┤
GPS ── Kalman filter ── position, speed ── waypoint bearing ─────────────────────────────────────┤
compass/gyro ── camera heading ──────────────────────────────────────────────────────────────────┤
                                                                                                 ▼
                     planner: headings −35°…+35°, longest clear corridor (rover 0.4 m + margin),
                     prefers the goal direction → FORWARD / LEFT / RIGHT / STOP / NO PATH, steer, throttle
```

- **App shell** (`android/src/.../MainActivity.java`): a full-screen WebView. It serves the bundled
  files from `https://appassets.androidplatform.net`, because camera and GPS need a secure origin.
  It also grants the camera and location permissions, provides Drive mode, and saves exports to Downloads.
- **Web app** (`static/`), the same code as the browser version:
  - `js/yolo.js`: YOLO11n obstacles.
  - `js/cvision.js`: OpenCV ground, blobs and flow.
  - `js/path.js`: free-ground boundary.
  - `js/obstacles.js`: tracking, distances and the obstacle list.
  - `js/planner.js`: the direction planner.
  - `js/nav.js`, `js/map.js`: GPS and the map.
  - `js/recorder.js`: IndexedDB recordings.
  - `js/camera.js`: lens choice and geometry.
  - `js/app.js`: main loop and screen.
- **Models inside the APK:**

| Model | File | Size | Licence |
|---|---|---|---|
| YOLO11n (COCO) | `yolo11n.onnx` | 10.6 MB | AGPL-3.0 (Ultralytics) |
| SSDLite MobileNetV2 (COCO-SSD fallback) | TF.js | 19 MB | Apache-2.0 |
| DeepLab v3 ADE20K | TF.js | 2.3 MB | Apache-2.0 |
| OpenCV.js 4.9 | `opencv.js` | 9.8 MB | Apache-2.0 |
| onnxruntime-web 1.20.1 (WebGPU) | `vendor/ort/` | 22 MB | MIT |
| TensorFlow.js 4.22, Leaflet 1.9.4 | `vendor/` | — | Apache-2.0 / BSD-2 |

Map data © OpenStreetMap contributors (ODbL), with tiles from tile.openstreetmap.org. The
tile-usage policy allows normal viewing; the app caches only the tiles you look at.

## 6. Speed on this phone (measured)

| Part | Time per frame |
|---|---|
| YOLO11n on WebGPU | 70–120 ms (about 11 fps for the whole loop) |
| OpenCV free ground | 10–14 ms |
| OpenCV optical flow | 2–4 ms |
| COCO-SSD lite (fallback) | 130 ms |
| DeepLab AI path (optional) | ~1.1–1.6 s, run once a second |

Depth networks (Depth Anything V2) were tested and left out. On this phone's GPU they gave invalid
output or crashed the WebView, and on the CPU they took about 4 s per frame. See `README.md` → Models.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `ML: fast (YOLO unavailable: no WebGPU…)` | Update **Android System WebView** (F-Droid / Aurora: "Android System WebView" or "Bromite/Mulch WebView"). The app keeps working with COCO-SSD meanwhile. |
| Camera pill red | Close other camera apps, then reopen the app. Check Settings → Apps → Rover Phone ML → Permissions → Camera. |
| `IMU` grey, distances "—" | Hold the phone upright with the back camera facing forward. |
| `GPS: searching…` | Go outdoors. Indoors it may never lock. |
| Distances off by 10–30% | Check the camera height, then calibrate (§4). |
| `drive mode: pin-failed` | Turn on Settings → Security → **App pinning**. |
| `dnd-needs-permission` | Allow Do Not Disturb access for Rover Phone ML (the screen opens by itself once). |
| Phone gets hot | Normal under full load. Drive mode keeps the speed steady. Avoid direct sun on the phone. |
| Debugging | Phone on USB/Wi-Fi debugging, then on a computer open `chrome://inspect` → Rover Phone ML. |

## 8. Build the APK yourself (Mac)

Requirements: the Android SDK (build-tools and platform android-35) in `~/Library/Android/sdk`
and a JDK. Gradle is not needed.
```bash
cd ~/Desktop/"PH3042 Rob and Auto"/phone_ml_demo
./android/build.sh                          # -> android/out/RoverPhoneML.apk
adb install -r android/out/RoverPhoneML.apk
```
The script copies `static/` into the APK (leaving out benchmark, depth and Mac-only files),
compiles the Java shell, and signs it with `android/keystore/rover.jks` (password `roverpass`;
change it for a public release). After changing anything in `static/`, run the script again.

To re-export or retrain YOLO (Python on the Mac), see `README.md` → *Python tools*.

## 9. Connecting the rover (next step)

The app already computes `{action, steer, throttle}` about 10 times a second. A microcontroller
(ESP32) can take these over USB-serial (OTG) or Wi-Fi and drive the motor driver. It should have
a watchdog that stops the motors if commands stop for more than about 0.5 s.
