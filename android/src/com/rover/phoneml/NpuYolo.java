package com.rover.phoneml;

import android.content.res.AssetFileDescriptor;
import android.content.res.AssetManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Rect;
import android.util.Base64;

import org.tensorflow.lite.Delegate;
import org.tensorflow.lite.Interpreter;
import org.tensorflow.lite.nnapi.NnApiDelegate;

import java.io.FileInputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * YOLO11n on the phone's NPU. The Redmi K50 Pro (MediaTek Dimensity 9000) exposes its AI
 * processor (APU 590: MDLA = deep-learning accelerator, plus VPU/DSP) through Android's
 * Neural Networks API. TensorFlow Lite's NNAPI delegate hands the whole network to it.
 *
 * accel: "npu" = mtk-mdla_shim, "neuron" = mtk-neuron_shim (MediaTek picks MDLA/VPU),
 *        "dsp" = mtk-dsp_shim, "nnapi-gpu" = mtk-gpu_shim, "cpu" = TFLite on 4 CPU cores.
 * The model is YOLO11n exported by Ultralytics to TFLite (LiteRT), 320x320, input [1, 3, 320, 320] 0..1,
 * output [1, 84, 2100] (box cx, cy, w, h scaled 0..1 + 80 class scores per candidate).
 */
class NpuYolo {
    static final int S = 320, N = 2100, C = 80;
    static final String[] ACCEL = { "npu", "neuron", "dsp", "nnapi-gpu", "cpu" };
    static String deviceName(String accel) {
        switch (accel) {
            case "npu": return "mtk-mdla_shim";
            case "neuron": return "mtk-neuron_shim";
            case "dsp": return "mtk-dsp_shim";
            case "nnapi-gpu": return "mtk-gpu_shim";
            default: return null;
        }
    }

    final String accel;
    final long initMs;
    private final Interpreter interp;
    private final Delegate delegate;
    private final ByteBuffer input = ByteBuffer.allocateDirect(4 * S * S * 3).order(ByteOrder.nativeOrder());
    private final float[][][] out = new float[1][4 + C][N];
    private final int[] px = new int[S * S];
    private final Bitmap square = Bitmap.createBitmap(S, S, Bitmap.Config.ARGB_8888);
    private final Canvas canvas = new Canvas(square);
    private final Paint paint = new Paint(Paint.FILTER_BITMAP_FLAG);

    NpuYolo(AssetManager assets, String modelPath, String accel) throws Exception {
        this.accel = accel;
        long t0 = System.nanoTime();
        MappedByteBuffer model;
        try (AssetFileDescriptor fd = assets.openFd(modelPath);
             FileInputStream in = new FileInputStream(fd.getFileDescriptor())) {
            model = in.getChannel().map(FileChannel.MapMode.READ_ONLY, fd.getStartOffset(), fd.getDeclaredLength());
        }
        Interpreter.Options o = new Interpreter.Options();
        String dev = deviceName(accel);
        if (dev != null) {
            NnApiDelegate.Options n = new NnApiDelegate.Options();
            n.setAcceleratorName(dev);
            n.setAllowFp16(true);                       // the NPU works in fp16 / int8
            n.setUseNnapiCpu(false);                    // fail instead of silently using the CPU
            n.setExecutionPreference(NnApiDelegate.Options.EXECUTION_PREFERENCE_SUSTAINED_SPEED);
            delegate = new NnApiDelegate(n);
            o.addDelegate(delegate);
        } else {
            delegate = null;
            o.setNumThreads(4);
            o.setUseXNNPACK(true);
        }
        interp = new Interpreter(model, o);
        int[] shp = interp.getOutputTensor(0).shape();
        if (shp.length != 3 || shp[1] != 4 + C || shp[2] != N)
            throw new IllegalStateException("unexpected output " + Arrays.toString(shp));
        runOnce();                                      // first run compiles for the accelerator
        initMs = (System.nanoTime() - t0) / 1_000_000;
    }

    void close() { interp.close(); if (delegate instanceof NnApiDelegate) ((NnApiDelegate) delegate).close(); }

    private void runOnce() { input.rewind(); interp.run(input, out); }

    /** Median time of n runs on the current input (ms). */
    double bench(int n) {
        double[] t = new double[n];
        for (int i = 0; i < n; i++) { long a = System.nanoTime(); runOnce(); t[i] = (System.nanoTime() - a) / 1e6; }
        Arrays.sort(t);
        return t[n / 2];
    }

    /**
     * Detect objects in a JPEG frame (data URL or base64). Returns JSON:
     * {"ms": inference ms, "pre": preprocessing ms, "boxes": [[x, y, w, h, score, class], ...]} in frame pixels.
     */
    String detect(String jpeg, float minScore, int maxBoxes) {
        long t0 = System.nanoTime();
        int comma = jpeg.indexOf(',');
        byte[] bytes = Base64.decode(comma >= 0 ? jpeg.substring(comma + 1) : jpeg, Base64.DEFAULT);
        Bitmap frame = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        if (frame == null) return "{\"error\":\"bad frame\"}";
        int fw = frame.getWidth(), fh = frame.getHeight();
        // letterbox into 320x320 (grey border), same as Ultralytics
        float scale = Math.min((float) S / fw, (float) S / fh);
        int nw = Math.round(fw * scale), nh = Math.round(fh * scale), dx = (S - nw) / 2, dy = (S - nh) / 2;
        canvas.drawColor(Color.rgb(114, 114, 114));
        canvas.drawBitmap(frame, null, new Rect(dx, dy, dx + nw, dy + nh), paint);
        frame.recycle();
        square.getPixels(px, 0, S, 0, 0, S, S);
        input.rewind();
        FloatBuffer fb = input.asFloatBuffer();          // channels first: all R, then all G, then all B
        final int n = S * S;
        for (int i = 0; i < n; i++) {
            int p = px[i];
            fb.put(i, ((p >> 16) & 255) / 255f); fb.put(n + i, ((p >> 8) & 255) / 255f); fb.put(2 * n + i, (p & 255) / 255f);
        }
        long t1 = System.nanoTime();
        runOnce();
        long t2 = System.nanoTime();

        // decode + class-agnostic non-maximum suppression (IoU 0.45)
        float[][] o = out[0];
        boolean normalised = false;
        for (int i = 0; i < N && !normalised; i += 97) normalised = o[2][i] > 0 && o[2][i] < 1.5f && o[3][i] < 1.5f;
        float k = normalised ? S : 1;
        List<float[]> cand = new ArrayList<>();
        for (int i = 0; i < N; i++) {
            int best = 0; float bs = o[4][i];
            for (int c = 1; c < C; c++) if (o[4 + c][i] > bs) { bs = o[4 + c][i]; best = c; }
            if (bs < minScore) continue;
            float cx = o[0][i] * k, cy = o[1][i] * k, w = o[2][i] * k, h = o[3][i] * k;
            cand.add(new float[]{ (cx - w / 2 - dx) / scale, (cy - h / 2 - dy) / scale, w / scale, h / scale, bs, best });
        }
        cand.sort((a, b) -> Float.compare(b[4], a[4]));
        List<float[]> keep = new ArrayList<>();
        for (float[] a : cand) {
            boolean ok = true;
            for (float[] b : keep) if (iou(a, b) > 0.45f) { ok = false; break; }
            if (ok) { keep.add(a); if (keep.size() >= maxBoxes) break; }
        }
        StringBuilder sb = new StringBuilder();
        sb.append("{\"ms\":").append(String.format("%.1f", (t2 - t1) / 1e6))
          .append(",\"pre\":").append(String.format("%.1f", (t1 - t0) / 1e6)).append(",\"boxes\":[");
        for (int i = 0; i < keep.size(); i++) {
            float[] b = keep.get(i);
            float x = Math.max(0, b[0]), y = Math.max(0, b[1]);
            float w = Math.min(fw - x, b[2] + Math.min(0, b[0])), h = Math.min(fh - y, b[3] + Math.min(0, b[1]));
            if (i > 0) sb.append(',');
            sb.append(String.format("[%.1f,%.1f,%.1f,%.1f,%.3f,%d]", x, y, w, h, b[4], (int) b[5]));
        }
        return sb.append("]}").toString();
    }

    private static float iou(float[] a, float[] b) {
        float x1 = Math.max(a[0], b[0]), y1 = Math.max(a[1], b[1]);
        float x2 = Math.min(a[0] + a[2], b[0] + b[2]), y2 = Math.min(a[1] + a[3], b[1] + b[3]);
        float inter = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
        return inter / (a[2] * a[3] + b[2] * b[3] - inter + 1e-6f);
    }
}
