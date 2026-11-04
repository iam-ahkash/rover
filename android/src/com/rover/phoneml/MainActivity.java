package com.rover.phoneml;

import android.Manifest;
import android.app.Activity;
import android.app.NotificationManager;
import android.content.Intent;
import android.os.PowerManager;
import android.provider.Settings;
import android.content.ContentValues;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.GeolocationPermissions;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * Rover Phone ML: the whole web app (camera, YOLO11n, OpenCV, path planner, GPS, map, recorder)
 * is bundled in assets/www and served to a WebView from the secure origin
 * https://appassets.androidplatform.net (camera and GPS need a secure origin). Nothing is
 * downloaded at run time except OpenStreetMap tiles. The screen stays on while the app is open.
 */
public class MainActivity extends Activity {
    static final String HOST = "appassets.androidplatform.net";
    static final String TAG = "RoverPhoneML";
    static final int REQ_PERMS = 1;

    private WebView web;
    private PermissionRequest pendingCamera;
    private int savedFilter = -1;          // Do Not Disturb setting before Drive mode
    private boolean driving = false;
    private static final Map<String, String> MIME = new HashMap<>();
    static {
        MIME.put("html", "text/html"); MIME.put("js", "text/javascript"); MIME.put("mjs", "text/javascript");
        MIME.put("css", "text/css"); MIME.put("json", "application/json"); MIME.put("wasm", "application/wasm");
        MIME.put("svg", "image/svg+xml"); MIME.put("png", "image/png"); MIME.put("webmanifest", "application/manifest+json");
        MIME.put("onnx", "application/octet-stream"); MIME.put("bin", "application/octet-stream");
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);   // no locking mid-drive
        WebView.setWebContentsDebuggingEnabled(true);                           // chrome://inspect from a computer

        web = new WebView(this);
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setGeolocationEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        web.setLayerType(View.LAYER_TYPE_HARDWARE, null);
        web.addJavascriptInterface(new Bridge(), "AndroidBridge");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if (!HOST.equals(u.getHost())) return null;           // e.g. map tiles: normal network
                return asset(u.getPath());
            }
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                return !HOST.equals(req.getUrl().getHost());          // stay inside the app
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(() -> {
                    if (has(Manifest.permission.CAMERA)) request.grant(request.getResources());
                    else { pendingCamera = request; askPermissions(); }
                });
            }
            @Override
            public void onGeolocationPermissionsShowPrompt(String origin, GeolocationPermissions.Callback cb) {
                cb.invoke(origin, has(Manifest.permission.ACCESS_FINE_LOCATION)
                                  || has(Manifest.permission.ACCESS_COARSE_LOCATION), false);
            }
            @Override
            public boolean onConsoleMessage(ConsoleMessage m) {
                Log.i(TAG, m.message() + " (" + m.sourceId() + ":" + m.lineNumber() + ")");
                return true;
            }
        });

        restoreDnd();                     // left over from a run that was killed while driving
        askPermissions();
        if (state != null) web.restoreState(state);
        else web.loadUrl("https://" + HOST + "/");
    }

    /** Serve a file from assets/www ("/" is the app page). */
    private WebResourceResponse asset(String path) {
        if (path == null || path.equals("/") || path.isEmpty()) path = "/phone.html";
        if (path.contains("..")) return notFound();
        String ext = path.substring(path.lastIndexOf('.') + 1).toLowerCase();
        String mime = MIME.containsKey(ext) ? MIME.get(ext) : "application/octet-stream";
        try {
            InputStream in = getAssets().open("www" + path);
            Map<String, String> h = new HashMap<>();
            h.put("Access-Control-Allow-Origin", "*");
            h.put("Cache-Control", "no-cache");
            boolean text = mime.startsWith("text/") || mime.contains("json") || mime.contains("svg");
            return new WebResourceResponse(mime, text ? "utf-8" : null, 200, "OK", h, in);
        } catch (IOException e) {
            return notFound();
        }
    }
    private WebResourceResponse notFound() {
        return new WebResourceResponse("text/plain", "utf-8", 404, "Not Found", new HashMap<>(),
                new java.io.ByteArrayInputStream("not found".getBytes(StandardCharsets.UTF_8)));
    }

    private boolean has(String p) { return checkSelfPermission(p) == PackageManager.PERMISSION_GRANTED; }

    private void askPermissions() {
        if (!has(Manifest.permission.CAMERA) || !has(Manifest.permission.ACCESS_FINE_LOCATION))
            requestPermissions(new String[]{ Manifest.permission.CAMERA,
                    Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION }, REQ_PERMS);
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        if (pendingCamera != null) {
            if (has(Manifest.permission.CAMERA)) pendingCamera.grant(pendingCamera.getResources());
            else pendingCamera.deny();
            pendingCamera = null;
        }
    }

    /** JavaScript side: window.AndroidBridge (used by js/recorder.js for exports). */
    class Bridge {
        @JavascriptInterface
        public String saveFile(String name, String mime, String text) {
            name = name.replaceAll("[^A-Za-z0-9._-]", "_");
            byte[] data = text.getBytes(StandardCharsets.UTF_8);
            try {
                if (Build.VERSION.SDK_INT >= 29) {                    // public Downloads/RoverPhoneML
                    ContentValues v = new ContentValues();
                    v.put(MediaStore.Downloads.DISPLAY_NAME, name);
                    v.put(MediaStore.Downloads.MIME_TYPE, mime);
                    v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/RoverPhoneML");
                    Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                    if (uri == null) throw new IOException("could not create the file");
                    try (OutputStream o = getContentResolver().openOutputStream(uri)) { o.write(data); }
                    return "Downloads/RoverPhoneML/" + name;
                } else {
                    File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "RoverPhoneML");
                    dir.mkdirs();
                    File f = new File(dir, name);
                    try (FileOutputStream o = new FileOutputStream(f)) { o.write(data); }
                    return f.getAbsolutePath();
                }
            } catch (Exception e) {
                return "ERROR " + e.getMessage();
            }
        }
        @JavascriptInterface
        public String version() { return "1.0"; }

        /** Drive mode: give the rover app the phone. on=true pins the app (other apps can't come to
         *  the front), holds back notifications (Do Not Disturb), asks for steady CPU/GPU speed and
         *  goes full screen. Returns what was switched on. */
        @JavascriptInterface
        public String driveMode(final boolean on) {
            final StringBuilder out = new StringBuilder();
            final Object lock = new Object();
            runOnUiThread(() -> {
                synchronized (lock) { out.append(setDriveMode(on)); lock.notify(); }
            });
            synchronized (lock) { try { if (out.length() == 0) lock.wait(2000); } catch (InterruptedException ignored) {} }
            return out.toString();
        }
    }

    private String setDriveMode(boolean on) {
        StringBuilder r = new StringBuilder();
        driving = on;
        // 1. steady performance (no thermal up/down swings) where the phone supports it
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        if (Build.VERSION.SDK_INT >= 24 && pm != null && pm.isSustainedPerformanceModeSupported()) {
            getWindow().setSustainedPerformanceMode(on); r.append(on ? "steady-speed " : "");
        }
        // 2. full screen
        immersive(on);
        // 3. Do Not Disturb (needs a one-time grant: Settings > Do Not Disturb access)
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) {
            if (nm.isNotificationPolicyAccessGranted()) {
                // The user's own setting is kept in prefs, so a crash or kill mid-drive never loses it
                // (it is put back the next time the app starts, see restoreDnd()).
                if (on) {
                    if (!prefs().contains("dndFilter")) prefs().edit().putInt("dndFilter", nm.getCurrentInterruptionFilter()).apply();
                    nm.setInterruptionFilter(NotificationManager.INTERRUPTION_FILTER_ALARMS); r.append("do-not-disturb ");
                } else restoreDnd();
            } else if (on) {
                r.append("dnd-needs-permission ");
                try { startActivity(new Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)); } catch (Exception ignored) {}
            }
        }
        // 4. pin the app so nothing else comes to the front (unpin: hold Back + Overview)
        try { if (on) { startLockTask(); r.append("pinned"); } else stopLockTask(); }
        catch (Exception e) { r.append(on ? "pin-failed" : ""); }
        return r.toString().trim();
    }

    private android.content.SharedPreferences prefs() { return getSharedPreferences("drive", MODE_PRIVATE); }

    /** Put the user's Do Not Disturb setting back (after Drive mode, or after a crash mid-drive). */
    private void restoreDnd() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm == null || !prefs().contains("dndFilter")) return;
        int f = prefs().getInt("dndFilter", NotificationManager.INTERRUPTION_FILTER_ALL);
        if (nm.isNotificationPolicyAccessGranted() && f > 0) nm.setInterruptionFilter(f);
        prefs().edit().remove("dndFilter").apply();
    }

    private void immersive(boolean on) {
        getWindow().getDecorView().setSystemUiVisibility(on
            ? View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
              | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
            : View.SYSTEM_UI_FLAG_VISIBLE);
    }

    @Override
    public void onWindowFocusChanged(boolean focus) { super.onWindowFocusChanged(focus); if (focus && driving) immersive(true); }

    @Override
    protected void onDestroy() { if (driving) setDriveMode(false); super.onDestroy(); }

    @Override
    public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
    @Override
    protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); web.saveState(out); }
    @Override
    protected void onPause() { super.onPause(); web.onPause(); }
    @Override
    protected void onResume() { super.onResume(); web.onResume(); }
}
