# Rover Phone ML (Android, runs on the phone only)

The Android phone is the rover's brain. With **one camera at 320×240** it finds the free ground,
detects **obstacles** (anything blocking the ground, with no object names) with their distance and
direction, plans a direction (FORWARD / LEFT / RIGHT / STOP / NO PATH), and follows GPS waypoints.
It **records everything on the phone**. The Mac is only needed once, to load the app.

- **Android app:** [`android/out/RoverPhoneML.apk`](android/out/RoverPhoneML.apk) — install and use it with [`docs/ANDROID_APP.md`](docs/ANDROID_APP.md)
- **How the models work (PDF):** [`docs/How_Rover_Phone_ML_Works.pdf`](docs/How_Rover_Phone_ML_Works.pdf)

```
Android phone (all offline)
 camera 320×240 ─► free-ground detector ─► edge obstacles ─┐
                └► detector boxes (no names) ─────────────┼─► planner ─► FORWARD/LEFT/RIGHT/STOP
 accelerometer (tilt) · compass · GPS (Kalman) ───────────┘      │
                                                               on-phone recorder (IndexedDB)
Mac (optional): load / update the app · receive an uploaded recording · live dashboard
```

## First load (needs the Mac once)

1. Phone: Developer options → **Wireless debugging** on (or USB debugging plus a cable).
2. Mac:
   ```bash
   cd ~/Desktop/"PH3042 Rob and Auto"/phone_ml_demo
   python3 server.py
   ```
   ```bash
   adb reverse tcp:8080 tcp:8080
   ```
   If `adb devices` says *unauthorized*, run `adb kill-server`, then accept the prompt on the phone.
3. Phone browser: open **http://localhost:8080** (localhost counts as secure, so no certificate warning).
   Wait until the **offline ready** pill turns green. The app, TensorFlow.js, the fast obstacle model
   (19 MB) and the DeepLab path model (2.3 MB) are now stored on the phone.

## Use it anywhere (no Mac, no network)

Open **http://localhost:8080** in the same browser, even with the Mac switched off and no Wi-Fi.
The service worker (`static/sw.js`) serves everything from the phone. Tap **Start**, then allow
camera, motion and location.
(Tested: after the server was stopped and the page reloaded, the model loaded, the loop ran, and
recordings were still there.)

- When the Mac is reachable again, app updates download in the background and apply on the next reload.
- YOLO11n and its GPU runtime are stored offline. The *Accurate* COCO-SSD model (65 MB) is not stored
  until it has been used once while online.

## What it does

- **One camera, smallest resolution:** the ultra-wide lens (95.7°) at 320×240 and 15 fps. Change the
  lens in Settings. The lens field of view comes from the phone's factory calibration.
- **Free ground** (`js/path.js`, `js/cvision.js`):
  - *OpenCV* (default): OpenCV.js (stored on the phone). The frame is blurred and converted to YCrCb.
    Canny edges (strong brightness edges or weak colour edges, so shadows don't count) act as walls.
    A flood fill then runs from several seeds just in front of the camera, followed by a morphological
    close and open. It takes about 2 ms.
  - *Colour*: learns the ground just in front and is fast.
  - *AI*: DeepLab ADE20K labels floor, road, sidewalk, path, earth and grass. It takes about 1 s per run and runs once a second.
- **Obstacles, without names** (`js/obstacles.js`):
  - *Edge obstacles*: where the free ground ends within 4 m (walls, kerbs, poles, bushes, steps,
    people's feet). Neighbouring columns at a similar distance are grouped into one obstacle.
  - *Box obstacles*: the **YOLO11n** detector (`js/yolo.js`) on the phone's GPU (WebGPU, ~70–120 ms),
    used only as "something is there" and tracked over frames. If WebGPU can't start, the app falls
    back to COCO-SSD automatically (the ML pill says so). Pick the model in Settings.
  - Each obstacle is listed as **obstacle · distance · angle · width** and drawn red (under 1 m),
    orange (under 2 m) or yellow.
- **Optical flow (OpenCV):** Lucas-Kanade tracking of Shi-Tomasi corners between frames. It shows
  whether you are moving or still, and turning left or right. It also detects **looming**: something
  in the middle of the view growing quickly. That gives a *time to contact* for any obstacle, with no
  distance or name needed. Under 1 s means **STOP**. The flow vectors are drawn in light blue.
- **OpenCV obstacle blobs:** holes in the free ground (found with the contour hierarchy) are objects
  with ground all around them. They are drawn as dashed pink boxes.
- **Distance:** floor geometry. It uses the camera height, the tilt from the accelerometer, and the
  image row where the obstacle meets the ground.
- **Planner** (`js/planner.js`): tests headings from −35° to +35° for the longest clear corridor as
  wide as the rover (0.2 m half-width + 0.15 m margin). It prefers the GPS goal direction.
  - **STOP** under 0.6 m.
  - **NO PATH** if almost no ground is visible.
- **GPS** (`js/nav.js`):
  - A Kalman-filtered position, camera heading, trail and walked distance.
  - **📍 Save here** saves the current spot. **Go to** picks a saved spot, then shows its distance and the turn to make.
  - **OpenStreetMap map** (Leaflet, stored on the phone): shows your position, the accuracy circle,
    a heading arrow, the walked trail, saved spots and a dashed line to the goal.
    - **Tap the map** to add a destination anywhere.
    - **⌖** follows you again after you pan, and **⤢** shows everything.
    - Map tiles need Wi-Fi the first time. Every tile you've seen is kept on the phone (up to 4000),
      so those areas still show offline. Without tiles, the trail and points still draw.

## Models (benchmarked on this phone, Nov 2026)

Measured with `http://localhost:8080/bench` on the phone's own camera (`?only=depth` or `?only=yolo`
runs one part). Results are saved on the Mac as `logs/bench_*.json`.

| Model | Engine | Size | Per frame | Verdict |
|---|---|---|---|---|
| **YOLO11n 320** | WebGPU | 10.6 MB | 120 ms in the benchmark, 71 ms in the app | ✅ **used**: finds far more than COCO-SSD (about twice its accuracy on the standard COCO benchmark) |
| YOLO11n 320 | WASM (CPU) | 10.6 MB | 462 ms | too slow |
| COCO-SSD lite | TF.js WebGL | 19 MB | 130 ms | fallback |
| Depth Anything V2 S, 4-bit | WebGPU | 19 MB | 80 ms | ❌ invalid (blank) output on this phone's GPU |
| Depth Anything V2 S, 4-bit / fp16 | WASM (CPU) | 19 / 50 MB | about 4.2 s | ❌ far too slow |
| Depth Anything V2 S, fp16 | WebGPU | 50 MB | — | ❌ the browser crashed |

So depth comes from floor geometry, the free-ground edge, and optical-flow time to contact, not from
a depth network. Re-run `/bench?only=depth` after a browser update; the models are kept for that.

### Python tools (`tools/`, on the Mac)

```bash
/opt/homebrew/bin/python3.12 -m venv tools/.venv
tools/.venv/bin/pip install ultralytics onnx onnxslim onnxruntime
tools/.venv/bin/python tools/export_models.py     # YOLO11n -> static/vendor/models/yolo11n/yolo11n.onnx
```

To make YOLO better at *your* campus, label a few hundred photos (bollards, kerbs, bins, bikes,
steps). Then train with `yolo detect train model=yolo11n.pt data=campus.yaml imgsz=320`, and export
again with the script. The app needs no changes.

## Recording (saved on the phone)

Tap **● Start recording**. Two samples per second are saved in the phone's IndexedDB (`js/recorder.js`).
Each sample holds time, filtered lat/lon, accuracy, speed, heading, tilt, action, commanded heading,
steer, throttle, clear distance, nearest obstacle distance and angle, obstacle count, free-ground
fraction, goal and fps. Recordings survive reloads and work offline. For each recording:

- **CSV / JSON**: opens the Android share sheet (Drive, email, Files…) or downloads to *Downloads*.
- **To Mac**: when the server is reachable, saves it as `logs/phone_session_<id>.json`.
- **Delete**: removes it from the phone.

## Calibrate once

1. Tap **🚶 Handheld (1.3 m)** or **🚗 Rover (0.2 m)**, or type the camera height.
2. Put something on the floor at a measured distance (for example 2.00 m) and enter that distance.
3. **Tap the picture exactly where it touches the floor.** This fits the tilt correction, and the
   settings are kept on the phone.

## Optional: live dashboard on the Mac

Settings → **Stream to the Mac dashboard** (off by default). Then open
**http://localhost:8080/dash** on the Mac to see the map, path radar and video. Streaming only
works while `adb reverse` or the same Wi-Fi connects the phone to the Mac.

## Troubleshooting

- **offline pill red**: the browser blocks service workers. Use the stock browser or Firefox over
  `http://localhost:8080` (not an IP address over plain http).
- **Distances wrong**: check the camera height, then calibrate. Hold the phone steady and upright.
- **GPS searching**: go outdoors. Indoors it may never lock.
- **No compass**: wave the phone in a figure-8.

## Next step (rover)

The phone already computes `{steer, throttle}`. An ESP32 can receive it over Wi-Fi or USB-serial
and drive the motor driver, with a watchdog that stops the rover if commands stop arriving.
