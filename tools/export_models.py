"""Prepare the candidate models for the phone, on the Mac (Python is only the workshop here).

    tools/.venv/bin/python tools/export_models.py

1. YOLO11n (Ultralytics, COCO) -> ONNX at 320x320 -> static/vendor/models/yolo11n/yolo11n.onnx
2. Depth Anything V2 Small ONNX (downloaded from onnx-community, Apache-2.0) -> check it runs
Both are checked with onnxruntime on a test frame and timed on the Mac CPU for reference.
The phone runs the same .onnx files with onnxruntime-web (see static/bench.html).
"""
import shutil
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "static" / "vendor" / "models"
TEST = ROOT / "tools" / "test_path.jpg"


def timeit(sess, feed, n=20):
    sess.run(None, feed)
    t = time.perf_counter()
    for _ in range(n):
        out = sess.run(None, feed)
    return (time.perf_counter() - t) / n * 1000, out


def export_yolo():
    from ultralytics import YOLO
    out_dir = MODELS / "yolo11n"
    out_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(ROOT / "tools" / "yolo11n.pt"))   # downloads the official weights the first time
    onnx_path = Path(model.export(format="onnx", imgsz=320, simplify=True, opset=17, dynamic=False))
    dst = out_dir / "yolo11n.onnx"
    shutil.move(str(onnx_path), dst)
    # check: same frame through onnxruntime, decode like the phone does
    img = Image.open(TEST).convert("RGB")
    w, h = img.size
    s = 320 / max(w, h)
    canvas = Image.new("RGB", (320, 320), (114, 114, 114))
    canvas.paste(img.resize((round(w * s), round(h * s))), (0, 0))
    x = (np.asarray(canvas, dtype=np.float32) / 255).transpose(2, 0, 1)[None]
    sess = ort.InferenceSession(str(dst), providers=["CPUExecutionProvider"])
    ms, (pred,) = timeit(sess, {sess.get_inputs()[0].name: x})
    p = pred[0].T                         # (2100, 84): cx, cy, w, h, 80 class scores
    scores = p[:, 4:].max(1)
    keep = scores > 0.3
    print(f"YOLO11n  {dst.stat().st_size / 1e6:.1f} MB  in {sess.get_inputs()[0].shape} out {pred.shape}"
          f"  Mac CPU {ms:.1f} ms  boxes>0.3 (before NMS): {int(keep.sum())}")
    return ms


def check_depth():
    for name in ["model_q4f16.onnx", "model_fp16.onnx"]:
        path = MODELS / "depth_anything_v2_small" / name
        sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        inp = sess.get_inputs()[0]
        img = Image.open(TEST).convert("RGB").resize((196, 252))   # multiples of 14 (ViT patches)
        x = (np.asarray(img, dtype=np.float32) / 255 - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
        x = x.transpose(2, 0, 1)[None].astype(np.float16 if "float16" in inp.type else np.float32)
        ms, (depth,) = timeit(sess, {inp.name: x}, n=5)
        d = depth.squeeze().astype(np.float32)
        print(f"Depth {name}  {path.stat().st_size / 1e6:.1f} MB  in {inp.name} {inp.type} out {depth.shape}"
              f"  Mac CPU {ms:.0f} ms  range {d.min():.2f}..{d.max():.2f}")


if __name__ == "__main__":
    export_yolo()
    check_depth()
