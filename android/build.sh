#!/bin/bash
# Build the Android app (no Gradle needed; uses the Android SDK's own tools).
#   ./android/build.sh            -> android/out/RoverPhoneML.apk
set -euo pipefail
cd "$(dirname "$0")"
SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
BT="$SDK/build-tools/$(ls "$SDK/build-tools" | sort -V | tail -1)"
PLATFORM="$SDK/platforms/android-35/android.jar"
OUT=out; rm -rf "$OUT/build"; mkdir -p "$OUT/build/assets/www" "$OUT/build/classes" "$OUT/build/res" "$OUT/build/lib/arm64-v8a"

# TensorFlow Lite runtime (runs YOLO on the NPU through NNAPI), from Maven Central:
#   org.tensorflow:tensorflow-lite:2.16.1 and tensorflow-lite-api:2.16.1 (Apache-2.0)
TFL=2.16.1; M=https://repo1.maven.org/maven2/org/tensorflow
for a in tensorflow-lite tensorflow-lite-api; do
  [ -f "libs/$a-$TFL/classes.jar" ] && continue
  mkdir -p "libs/$a-$TFL"; curl -sSfL -o "libs/$a-$TFL.aar" "$M/$a/$TFL/$a-$TFL.aar"
  (cd "libs/$a-$TFL" && unzip -q -o "../$a-$TFL.aar")
done
JARS="libs/tensorflow-lite-$TFL/classes.jar:libs/tensorflow-lite-api-$TFL/classes.jar"
cp "libs/tensorflow-lite-$TFL/jni/arm64-v8a/libtensorflowlite_jni.so" "$OUT/build/lib/arm64-v8a/"

# 1. the web app + models into assets/www (only what the app uses; no benchmark/depth/Mac-only files)
W=../static
rsync -a --exclude bench.html --exclude dash.html --exclude sw.js \
  --exclude 'vendor/models/depth_anything_v2_small' --exclude 'vendor/models/ssd_mobilenet_v2' "$W/" "$OUT/build/assets/www/"
echo "assets: $(du -sh "$OUT/build/assets" | cut -f1)"

# 2. resources + manifest
"$BT/aapt2" compile --dir res -o "$OUT/build/res/res.zip"
"$BT/aapt2" link -o "$OUT/build/unsigned.apk" -I "$PLATFORM" --manifest AndroidManifest.xml \
  -A "$OUT/build/assets" --min-sdk-version 26 --target-sdk-version 35 \
  -0 onnx -0 wasm -0 bin -0 tflite "$OUT/build/res/res.zip"

# 3. Java -> dex
javac --release 17 -classpath "$PLATFORM:$JARS" -d "$OUT/build/classes" $(find src -name '*.java')
"$BT/d8" --release --min-api 26 --lib "$PLATFORM" --output "$OUT/build" $(find "$OUT/build/classes" -name '*.class') ${JARS//:/ }
(cd "$OUT/build" && zip -q -j unsigned.apk classes.dex && zip -q -r unsigned.apk lib)

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
