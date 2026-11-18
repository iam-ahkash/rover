"""build/mesh.json -> model/delivery_rover.glb (coloured, metres, Y-up) and docs/rover_viewer.html."""
import base64
import json
import os
import struct

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = json.load(open(os.path.join(ROOT, "build", "mesh.json")))

def to_gltf(v):
    """Rover axes (x fwd, y left, z up, mm) -> glTF (Y up, metres): gx = -y, gy = z, gz = -x (a proper rotation)."""
    v = np.asarray(v, dtype=float) / 1000.0
    return np.stack([-v[:, 1], v[:, 2], -v[:, 0]], axis=1)


def hex_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]


def srgb_to_linear(c):
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


bin_chunks = []
offset = 0
buffer_views, accessors, meshes, nodes, materials = [], [], [], [], []
mat_index = {}

for p in data["parts"]:
    V = to_gltf(p["verts"])
    T = np.asarray(p["tris"], dtype=np.int64)
    tri = V[T]                                   # (n,3,3) unshared -> flat normals
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    keep = ln[:, 0] > 1e-14
    tri, n, ln = tri[keep], n[keep], ln[keep]
    n = n / ln
    pos = tri.reshape(-1, 3).astype(np.float32)
    nor = np.repeat(n, 3, axis=0).astype(np.float32)

    key = (p["color"], p["alpha"])
    if key not in mat_index:
        rgb = srgb_to_linear(hex_rgb(p["color"]))
        m = {"name": f"mat_{len(materials)}", "pbrMetallicRoughness": {
            "baseColorFactor": rgb + [p["alpha"]], "metallicFactor": 0.0, "roughnessFactor": 0.65},
            "doubleSided": True}
        if p["alpha"] < 1:
            m["alphaMode"] = "BLEND"
        mat_index[key] = len(materials)
        materials.append(m)

    attrs = {}
    for arr, name in ((pos, "POSITION"), (nor, "NORMAL")):
        b = arr.tobytes()
        bin_chunks.append(b)
        buffer_views.append({"buffer": 0, "byteOffset": offset, "byteLength": len(b), "target": 34962})
        offset += len(b)
        acc = {"bufferView": len(buffer_views) - 1, "componentType": 5126, "count": len(arr), "type": "VEC3"}
        if name == "POSITION":
            acc["min"] = arr.min(axis=0).tolist()
            acc["max"] = arr.max(axis=0).tolist()
        accessors.append(acc)
        attrs[name] = len(accessors) - 1
    meshes.append({"name": p["name"], "primitives": [{"attributes": attrs, "material": mat_index[key]}]})
    nodes.append({"name": p["name"], "mesh": len(meshes) - 1, "extras": {"group": p["group"], "mass_kg": p["mass"]}})

binary = b"".join(bin_chunks)
binary += b"\x00" * ((4 - len(binary) % 4) % 4)
gltf = {
    "asset": {"version": "2.0", "generator": "delivery_rover make_glb.py"},
    "scene": 0,
    "scenes": [{"name": "DeliveryRover", "nodes": [len(nodes)]}],
    "nodes": nodes + [{"name": "DeliveryRover", "children": list(range(len(nodes)))}],
    "meshes": meshes, "materials": materials, "accessors": accessors,
    "bufferViews": buffer_views, "buffers": [{"byteLength": len(binary)}],
}
js = json.dumps(gltf, separators=(",", ":")).encode()
js += b" " * ((4 - len(js) % 4) % 4)
glb = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binary))
glb += struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(binary), 0x004E4942) + binary
out = os.path.join(ROOT, "model", "delivery_rover.glb")
open(out, "wb").write(glb)
print("glb", len(glb) // 1024, "KB", len(nodes), "nodes")

# ------------------------------------------------------------------ viewer (GLB embedded, works offline except three.js from the CDN)
b64 = base64.b64encode(glb).decode()
html = open(os.path.join(ROOT, "src", "viewer_template.html")).read().replace("__GLB_BASE64__", b64).replace("__DIMS__", "549 × 530 × 415")
open(os.path.join(ROOT, "docs", "rover_viewer.html"), "w").write(html)
print("viewer written")
