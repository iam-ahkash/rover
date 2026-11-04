#!/bin/bash
# Build the Android app (no Gradle needed; uses the Android SDK's own tools).
#   ./android/build.sh            -> android/out/RoverPhoneML.apk
set -euo pipefail
cd "$(dirname "$0")"
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
BT="$SDK/build-tools/$(ls "$SDK/build-tools" | sort -V | tail -1)"
PLATFORM="$SDK/platforms/android-35/android.jar"
OUT=out; rm -rf "$OUT/build"; mkdir -p "$OUT/build/assets/www" "$OUT/build/classes" "$OUT/build/res"

# 1. the web app + models into assets/www (only what the app uses; no benchmark/depth/Mac-only files)
W=../static
rsync -a --exclude bench.html --exclude dash.html --exclude sw.js \
  --exclude 'vendor/models/depth_anything_v2_small' --exclude 'vendor/models/ssd_mobilenet_v2' "$W/" "$OUT/build/assets/www/"
echo "assets: $(du -sh "$OUT/build/assets" | cut -f1)"

# 2. resources + manifest
"$BT/aapt2" compile --dir res -o "$OUT/build/res/res.zip"
"$BT/aapt2" link -o "$OUT/build/unsigned.apk" -I "$PLATFORM" --manifest AndroidManifest.xml \
  -A "$OUT/build/assets" --min-sdk-version 26 --target-sdk-version 35 \
  -0 onnx -0 wasm -0 bin "$OUT/build/res/res.zip"

# 3. Java -> dex
javac --release 17 -classpath "$PLATFORM" -d "$OUT/build/classes" $(find src -name '*.java')
"$BT/d8" --release --min-api 26 --lib "$PLATFORM" --output "$OUT/build" $(find "$OUT/build/classes" -name '*.class')
(cd "$OUT/build" && zip -q -j unsigned.apk classes.dex)

# 4. align + sign (a local key in android/keystore; keep it to install updates over the old app)
"$BT/zipalign" -f -p 4 "$OUT/build/unsigned.apk" "$OUT/build/aligned.apk"
[ -f keystore/rover.jks ] || { mkdir -p keystore; keytool -genkeypair -keystore keystore/rover.jks -alias rover \
  -keyalg RSA -keysize 2048 -validity 10000 -storepass roverpass -keypass roverpass \
  -dname "CN=Rover Phone ML, O=PH3042, C=LK" >/dev/null 2>&1; }
"$BT/apksigner" sign --ks keystore/rover.jks --ks-pass pass:roverpass --key-pass pass:roverpass \
  --out "$OUT/RoverPhoneML.apk" "$OUT/build/aligned.apk"
"$BT/apksigner" verify "$OUT/RoverPhoneML.apk"
rm -rf "$OUT/build"
echo "built $(pwd)/$OUT/RoverPhoneML.apk ($(du -h "$OUT/RoverPhoneML.apk" | cut -f1))"
