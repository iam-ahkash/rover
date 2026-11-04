"""Phone ML demo server.

Serves the phone app (camera + sensors + on-phone ML). After the first load the phone runs it
offline from its own cache and keeps its recordings itself; this server is then only needed to
update the app, receive an uploaded recording, or relay the optional live stream to the dashboard.

    python3 server.py            -> https://<mac-ip>:8443        (open on the phone)
                                    http://localhost:8080/dash   (open on the Mac)
"""
import asyncio
import json
import socket
import ssl
import subprocess
import time
from pathlib import Path

from aiohttp import web, WSMsgType

ROOT = Path(__file__).parent
STATIC = ROOT / "static"
CERT = ROOT / "certs" / "cert.pem"
KEY = ROOT / "certs" / "key.pem"
LOG_DIR = ROOT / "logs"
PORT = 8443
DASH_PORT = 8080


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def ensure_cert(ip):
    """Phones only allow camera/motion/GPS on HTTPS, so make a self-signed cert."""
    stamp = CERT.parent / "ip.txt"
    if CERT.exists() and KEY.exists() and stamp.exists() and stamp.read_text() == ip:
        return
    CERT.parent.mkdir(exist_ok=True)
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", str(KEY), "-out", str(CERT), "-days", "365",
         "-subj", "/CN=rover-demo",
         "-addext", f"subjectAltName=IP:{ip},IP:127.0.0.1,DNS:localhost"],
        check=True, capture_output=True,
    )
    stamp.write_text(ip)


class Hub:
    """Relays everything the phone sends to every open dashboard."""

    def __init__(self):
        self.dashboards = set()
        self.last_state = None
        self.phone_count = 0
        self.log = None

    async def broadcast(self, data):
        dead = []
        for ws in self.dashboards:
            try:
                if isinstance(data, bytes):
                    await ws.send_bytes(data)
                else:
                    await ws.send_str(data)
            except ConnectionResetError:
                dead.append(ws)
        for ws in dead:
            self.dashboards.discard(ws)

    def record(self, text):
        if self.log is None:
            LOG_DIR.mkdir(exist_ok=True)
            self.log = open(LOG_DIR / time.strftime("session_%Y%m%d_%H%M%S.jsonl"), "a")
        self.log.write(text + "\n")
        self.log.flush()


hub = Hub()


async def phone_ws(request):
    ws = web.WebSocketResponse(max_msg_size=4 * 1024 * 1024)
    await ws.prepare(request)
    hub.phone_count += 1
    print(f"[phone] connected from {request.remote}")
    await hub.broadcast(json.dumps({"type": "status", "phones": hub.phone_count}))
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                hub.last_state = msg.data
                hub.record(msg.data)
                await hub.broadcast(msg.data)
            elif msg.type == WSMsgType.BINARY:  # JPEG camera frame
                await hub.broadcast(msg.data)
    finally:
        hub.phone_count -= 1
        print("[phone] disconnected")
        await hub.broadcast(json.dumps({"type": "status", "phones": hub.phone_count}))
    return ws


async def dash_ws(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    hub.dashboards.add(ws)
    await ws.send_str(json.dumps({"type": "status", "phones": hub.phone_count}))
    if hub.last_state:
        await ws.send_str(hub.last_state)
    try:
        async for _ in ws:
            pass
    finally:
        hub.dashboards.discard(ws)
    return ws


def page(name):
    async def handler(_):
        return web.FileResponse(STATIC / name, headers={"Cache-Control": "no-store"})
    return handler


async def upload(request):
    """A recorded session sent from the phone (optional; the phone keeps its own copy)."""
    data = await request.json()
    sid = "".join(c for c in str((data.get("session") or {}).get("id", "")) if c.isalnum() or c in "T-_")
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"phone_session_{sid or int(time.time())}.json"
    path.write_text(json.dumps(data))
    print(f"saved {path.name}: {len(data.get('samples', []))} samples")
    return web.json_response({"file": str(path.relative_to(ROOT))})


async def bench_page(_):
    # cross-origin isolation lets onnxruntime-web use several CPU threads (SharedArrayBuffer)
    return web.FileResponse(STATIC / "bench.html", headers={
        "Cache-Control": "no-store", "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp"})


async def bench_result(request):
    data = await request.json()
    LOG_DIR.mkdir(exist_ok=True)
    path = LOG_DIR / f"bench_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(data, indent=1))
    print(f"benchmark saved: {path.name}")
    for r in data.get("results", []):
        print(f"  {r['model']:<28} {r['engine']:<14} " +
              (f"ERROR {r['error'][:60]}" if r.get("error") else f"median {r['median']:.0f} ms  load {r['loadMs'] / 1000:.1f} s"))
    return web.json_response({"file": str(path.relative_to(ROOT))})


async def isolation_headers(request, response):
    # the benchmark page is cross-origin isolated (multi-threaded WASM); the workers and files it
    # loads must say they may be embedded there. Harmless for the normal phone app.
    if request.path.startswith(("/vendor/", "/js/", "/bench")):
        response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"


def make_app():
    app = web.Application()
    app.on_response_prepare.append(isolation_headers)
    app.router.add_get("/", page("phone.html"))
    app.router.add_get("/dash", page("dash.html"))
    app.router.add_get("/ws/phone", phone_ws)
    app.router.add_get("/ws/dash", dash_ws)
    # ML libraries + model weights, served locally so the phone needs no internet
    app.router.add_static("/vendor", STATIC / "vendor")
    app.router.add_static("/js", STATIC / "js")
    # offline app: service worker must be served from the root so it controls the whole page
    app.router.add_get("/sw.js", page("sw.js"))
    app.router.add_get("/manifest.webmanifest", page("manifest.webmanifest"))
    app.router.add_get("/icon.svg", page("icon.svg"))
    app.router.add_post("/api/upload", upload)
    app.router.add_get("/bench", bench_page)
    app.router.add_post("/api/bench", bench_result)
    return app


async def serve():
    ip = local_ip()
    ensure_cert(ip)
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(CERT, KEY)
    runner = web.AppRunner(make_app())
    await runner.setup()
    # HTTPS for the phone (browsers block camera/sensors without it),
    # plain HTTP on localhost for the Mac dashboard (localhost counts as secure).
    await web.TCPSite(runner, "0.0.0.0", PORT, ssl_context=ctx).start()
    await web.TCPSite(runner, "127.0.0.1", DASH_PORT).start()
    print("\n  Phone ML demo", flush=True)
    print(f"  On the PHONE open : https://{ip}:{PORT}   (tap Advanced -> Proceed once)")
    print(f"  On the MAC open   : http://localhost:{DASH_PORT}/dash\n", flush=True)
    await asyncio.Event().wait()


def main():
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
    except OSError as e:
        if e.errno != 48:  # 48 = address already in use (macOS)
            raise
        print(f"\n  The demo server is already running (port {PORT} is in use).")
        print(f"  Just open https://{local_ip()}:{PORT} on the phone and "
              f"http://localhost:{DASH_PORT}/dash on the Mac.")
        print(f"  To restart it, stop the old one first:  lsof -ti tcp:{PORT} | xargs kill\n")


if __name__ == "__main__":
    main()
