"""build/mesh.json -> dimensioned drawings (docs/img/*.svg) and build/analysis.json."""
import json
import math
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection, PolyCollection  # noqa: E402
from matplotlib.patches import Circle, Rectangle  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "docs", "img")
data = json.load(open(os.path.join(ROOT, "build", "mesh.json")))
L = data["layout"]
P = data["parts"]
for p in P:
    p["V"] = np.asarray(p["verts"], float)
    p["T"] = np.asarray(p["tris"], int)

plt.rcParams.update({"font.family": "Helvetica", "font.size": 7.5, "svg.fonttype": "none"})
DIM = "#c0392b"
INK = "#2b2b2b"

# view: (h axis, v axis, depth axis, depth sign: +1 = larger is nearer)
VIEWS = {
    "side": (0, 2, 1, +1),     # from the left: x right (front), z up
    "front": (1, 2, 0, +1),    # from the front: y right (rover's left), z up
    "top": (0, 1, 2, +1),      # from above: x right (front), y up (left)
    "under": (0, 1, 2, -1),    # what is under the deck, drawn in the same orientation as the top view
}


def draw(ax, view, skip=(), only=None, alpha_override=None, edge_lw=0.35):
    h, v, d, sgn = VIEWS[view]
    parts = [p for p in P if not any(p["name"].startswith(s) for s in skip) and (only is None or only(p))]
    parts.sort(key=lambda p: sgn * p["com"][d])
    for p in parts:
        V, T = p["V"], p["T"]
        polys = V[T][:, :, [h, v]]
        col = p["color"]
        a = 1.0 if alpha_override is None else alpha_override(p)
        ax.add_collection(PolyCollection(polys, facecolors=col, edgecolors=col, linewidths=0.15, alpha=a, zorder=2))
        segs = [np.asarray(e)[:, [h, v]] for e in p["edges"]]
        if segs:
            ax.add_collection(LineCollection(segs, colors=INK, linewidths=edge_lw, alpha=min(1, a + 0.2), zorder=2))


def dim(ax, a, b, off, text, vertical=False, side=1, fs=7, ext=True):
    """Dimension between points a and b (in drawing coords), offset 'off' perpendicular."""
    (x1, y1), (x2, y2) = a, b
    if not vertical:
        yy = off
        if ext:
            ax.plot([x1, x1], [y1, yy + 3 * np.sign(yy - y1 or 1)], color=DIM, lw=0.4, zorder=5)
            ax.plot([x2, x2], [y2, yy + 3 * np.sign(yy - y2 or 1)], color=DIM, lw=0.4, zorder=5)
        ax.annotate("", (x1, yy), (x2, yy), arrowprops=dict(arrowstyle="<|-|>", color=DIM, lw=0.6, shrinkA=0, shrinkB=0, mutation_scale=6), zorder=5)
        ax.text((x1 + x2) / 2, yy + side * 3.5, text, color=DIM, ha="center", va="bottom" if side > 0 else "top", fontsize=fs, zorder=6,
                bbox=dict(fc="white", ec="none", pad=0.4))
    else:
        xx = off
        if ext:
            ax.plot([x1, xx + 3 * np.sign(xx - x1 or 1)], [y1, y1], color=DIM, lw=0.4, zorder=5)
            ax.plot([x2, xx + 3 * np.sign(xx - x2 or 1)], [y2, y2], color=DIM, lw=0.4, zorder=5)
        ax.annotate("", (xx, y1), (xx, y2), arrowprops=dict(arrowstyle="<|-|>", color=DIM, lw=0.6, shrinkA=0, shrinkB=0, mutation_scale=6), zorder=5)
        ax.text(xx + side * 3.5, (y1 + y2) / 2, text, color=DIM, ha="left" if side > 0 else "right", va="center", fontsize=fs, rotation=90 if abs(y2 - y1) > 60 else 0,
                rotation_mode="anchor" if False else "default", zorder=6, bbox=dict(fc="white", ec="none", pad=0.4))



def front_arrow(ax, x, y, length, fs=7):
    ax.annotate("", (x + length, y), (x, y), arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.8))
    ax.text(x + length * 1.1, y, "FRONT", ha="left", va="center", fontsize=fs, color=INK)


def finish(fig, ax, name, xlim, ylim, title=None):
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect("equal"); ax.axis("off")
    if title:
        ax.set_title(title, fontsize=9, loc="left", color=INK, fontweight="bold")
    fig.savefig(os.path.join(IMG, name + ".svg"), bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


def bb(prefix):
    b = [p["bbox"] for p in P if p["name"].startswith(prefix)]
    a = np.array(b)
    return [a[:, 0].min(), a[:, 1].max(), a[:, 2].min(), a[:, 3].max(), a[:, 4].min(), a[:, 5].max()]


ALL = bb("")
ROVER = np.array([p["bbox"] for p in P if not p["name"].startswith("Payload")])
XMIN, XMAX = ROVER[:, 0].min(), ROVER[:, 1].max()
YMIN, YMAX = ROVER[:, 2].min(), ROVER[:, 3].max()
ZMAX = ROVER[:, 5].max()
deck = L["deck"]
DT = L["deck_top"]
box = L["box"]
lid_top = box["z0"] + box["h"] + box["lid"]
caster_wheel_x = L["caster_x"] - L["caster_trail"]
DW, DH = deck["x1"] - deck["x0"], 2 * deck["y"]
IW = L["inner_w"]
WH = L["wire_hole"]

# ------------------------------------------------------------------ side view
fig, ax = plt.subplots(figsize=(7.4, 4.6))
draw(ax, "side", skip=("Payload",))
ax.plot([XMIN - 30, XMAX + 30], [0, 0], color=INK, lw=0.8)
for xg in np.arange(XMIN - 30, XMAX + 30, 12):
    ax.plot([xg, xg - 8], [0, -8], color=INK, lw=0.3)
dim(ax, (XMIN, 0), (XMAX, 0), -38, f"overall length {XMAX - XMIN:.0f}", side=-1)
dim(ax, (L["axle_x"], 0), (L["caster_x"], 0), -18, f"wheelbase {L['caster_x'] - L['axle_x']:.0f} (to caster swivel)", side=-1)
dim(ax, (deck["x0"], DT), (L["axle_x"], DT), lid_top + 22, f"{L['axle_x'] - deck['x0']:.0f}", side=1)
dim(ax, (deck["x0"], DT), (deck["x1"], DT), lid_top + 46, f"deck {deck['x1'] - deck['x0']:.0f}", side=1)
dim(ax, (XMIN, 0), (XMIN, lid_top), XMIN - 30, f"height {lid_top:.0f}", vertical=True, side=-1)
dim(ax, (XMAX, 0), (XMAX, DT), XMAX + 16, f"deck top {DT:.0f}", vertical=True, side=1)
dim(ax, (XMAX, 0), (XMAX, L["deck"]["z0"]), XMAX + 50, f"{L['deck']['z0']:.0f}", vertical=True, side=1)
dim(ax, (XMAX, 0), (XMAX, L["strip_z0"]), XMAX + 76, f"{L['strip_z0']:.0f}", vertical=True, side=1)
cam_z = L["cam_pivot"][2]
dim(ax, (box["x1"] + 40, 0), (box["x1"] + 40, cam_z), box["x1"] + 112, f"camera {cam_z:.0f}", vertical=True, side=1)
ax.plot([box["x1"] + 40, box["x1"] + 112], [cam_z, cam_z], color=DIM, lw=0.4, ls=":")
ax.add_patch(Circle((L["axle_x"], L["axle_z"]), 2.5, color=DIM, zorder=7))
ax.text(L["axle_x"] + 4, L["axle_z"] - 30, f"Ø{L['wheel_d']} wheel\naxle at {L['axle_z']:.0f}", color=DIM, fontsize=6.5, zorder=7, ha="left",
        bbox=dict(fc="white", ec="none", pad=0.4, alpha=0.8))
ax.text(L["caster_x"] - 2, -60, "", fontsize=1)
# camera view ray (lower edge of the picture)
cx, cz = box["x1"] + 33, cam_z
lower = math.radians(L["cam_tilt"] + 24.5)
gx = cx + cz / math.tan(lower)
ax.plot([cx, gx], [cz, 0], color="#2b6cb0", lw=0.6, ls="--", zorder=6)
ax.text(gx + 4, 6, f"camera sees the ground\nfrom {gx - XMAX:.0f} mm ahead", color="#2b6cb0", fontsize=6.5, va="bottom")
finish(fig, ax, "dwg_side", (XMIN - 70, gx + 150), (-62, lid_top + 70), "Side view (from the left)  ·  mm")

# ------------------------------------------------------------------ front view
fig, ax = plt.subplots(figsize=(6.4, 4.6))
draw(ax, "front", skip=("Payload",))
ax.plot([YMIN - 30, YMAX + 30], [0, 0], color=INK, lw=0.8)
dim(ax, (YMIN, 0), (YMAX, 0), -38, f"overall width {YMAX - YMIN:.0f}", side=-1)
dim(ax, (-L["wheel_yc"], 0), (L["wheel_yc"], 0), -18, f"track {2 * L['wheel_yc']:.0f} (wheel centres)", side=-1)
dim(ax, (-deck["y"], DT), (deck["y"], DT), lid_top + 22, f"deck {2 * deck['y']}", side=1)
dim(ax, (-L["caster_y"], 30), (L["caster_y"], 30), lid_top + 46, f"casters {2 * L['caster_y']} apart", side=1)
dim(ax, (YMAX, 0), (YMAX, lid_top), YMAX + 18, f"{lid_top:.0f}", vertical=True, side=1)
dim(ax, (-L["wheel_yc"] - 30, 0), (-L["wheel_yc"] - 30, L["wheel_d"]), YMIN - 18, f"Ø{L['wheel_d']}", vertical=True, side=-1)
for yc in (-L["front_y"], 0, L["front_y"]):
    ax.text(yc, L["front_z"] + 12, "HC-SR04", color="#1e4fa0", ha="center", va="bottom", fontsize=5.5)
finish(fig, ax, "dwg_front", (YMIN - 60, YMAX + 60), (-62, lid_top + 70), "Front view  ·  mm")

# ------------------------------------------------------------------ top view
fig, ax = plt.subplots(figsize=(7.4, 5.6))
draw(ax, "top", skip=("Payload",), alpha_override=lambda p: 0.55 if p["name"].startswith("Bay_cover") else 1)
dim(ax, (XMIN, YMIN), (XMAX, YMIN), YMIN - 30, f"overall length {XMAX - XMIN:.0f}", side=-1)
dim(ax, (XMAX, YMIN), (XMAX, YMAX), XMAX + 30, f"overall width {YMAX - YMIN:.0f}", vertical=True, side=1)
dim(ax, (box["x0"], box["y"]), (box["x1"], box["y"]), YMAX + 20, f"cargo box {box['x1'] - box['x0']:.0f} × {2 * box['y']} (= deck)", side=1)
ax.text((box["x0"] + box["x1"]) / 2, 0, f"CARGO BOX LID\n{DW + 6} × {DH + 6}", ha="center", va="center", color="white", fontsize=8, fontweight="bold")
front_arrow(ax, XMAX + 42, YMIN + 25, 22)
finish(fig, ax, "dwg_top", (XMIN - 30, XMAX + 110), (YMIN - 55, YMAX + 45), "Top view  ·  mm")

# ------------------------------------------------------------------ electronics compartment layout
bay_only = lambda p: (p["bbox"][4] >= DT - 0.1 and p["bbox"][5] <= box["z0"] + 0.1) or p["name"].startswith(("Wall_", "Rocker"))
fig, ax = plt.subplots(figsize=(7.4, 6.4))
ax.add_patch(Rectangle((deck["x0"], -deck["y"]), DW, DH, fc="#ecd5b0", ec=INK, lw=0.5, zorder=1))
draw(ax, "top", only=bay_only)
for s in (1, -1):
    ax.add_patch(Circle((WH[0], s * WH[1]), 8, fc="white", ec=INK, lw=0.5, zorder=4))
labels = [  # text, anchor, text position, alignment
    ("BTS7960 #1 (left motor)", "BTS7960_board_L", (-95, 185), "center"),
    ("BTS7960 #2 (right motor)", "BTS7960_board_R", (-95, -190), "center"),
    ("3S2P battery 65×56×37", "Battery_3S2P", (-235, 0), "right"),
    ("BMS 3S 40A", "Battery_BMS", (-235, 45), "right"),
    ("Fuse 10 A + XT60", "Fuse_holder", (-235, 80), "right"),
    ("Main switch (rear wall)", "Rocker_switch_body_15A", (-235, 150), "right"),
    ("HC-SR04 rear L", "HC-SR04_Rear_L", (-235, 115), "right"),
    ("HC-SR04 rear R", "HC-SR04_Rear_R", (-235, -70), "right"),
    ("XL4015 to 5 V", "XL4015", (235, -110), "left"),
    ("ESP32 DevKit", "ESP32_DevKit", (15, 45), "left"),
    ("Phone 163×76 on 10 mm foam", "Phone_Redmi", (235, 0), "left"),
    ("HC-SR04 side L (in wall)", "HC-SR04_Side_L", (70, 185), "left"),
    ("HC-SR04 side R (in wall)", "HC-SR04_Side_R", (70, -190), "left"),
]
for text, prefix, (tx, ty), ha in labels:
    b = bb(prefix)
    cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
    ax.annotate(text, (cx, cy), (tx, ty), fontsize=6.5, ha=ha, va="center", zorder=9,
                arrowprops=dict(arrowstyle="-", lw=0.4, color=INK))
ax.annotate("Ø16 wire holes (motor +\nencoder cables from below)", (WH[0], -WH[1]), (-235, -140), fontsize=6.5, ha="right", va="center",
            arrowprops=dict(arrowstyle="-", lw=0.4, color=INK))
ax.text(-85, 155, "vent slots 40 × 15 in both side walls", fontsize=6, ha="center", va="bottom")
dim(ax, (deck["x0"] + 12, -deck["y"]), (deck["x1"] - 12, -deck["y"]), -deck["y"] - 60, f"inside {DW - 24} × {DH - 24} × {L['wall_h']} high (box floor is the roof)", side=-1)
front_arrow(ax, 245, -150, 35)
finish(fig, ax, "dwg_bay", (-400, 400), (-235, 215), "Electronics compartment under the box (top view, box removed)  ·  mm")

# ------------------------------------------------------------------ ultrasonic coverage (top view)
fig, ax = plt.subplots(figsize=(7.4, 6.4))
draw(ax, "top", skip=("Payload",), alpha_override=lambda p: 0.35 if p["name"].startswith(("Cargo", "Webcam", "Servo")) else 1)
from matplotlib.patches import Wedge  # noqa: E402
RANGE, HALF = 1000, 15   # drawn to 1.0 m; HC-SR04 beam about 30 degrees wide
FX = deck["x1"] + 12
sensors = [((FX + 6, L["front_y"] + 3), 30, "F-L"), ((FX + 13.6, 0), 0, "F-C"), ((FX + 6, -L["front_y"] - 3), -30, "F-R"),
           ((L["side_sonar_x"], deck["y"]), 90, "S-L"), ((L["side_sonar_x"], -deck["y"]), -90, "S-R"),
           ((deck["x0"], L["rear_sonar_y"]), 180, "B-L"), ((deck["x0"], -L["rear_sonar_y"]), 180, "B-R")]
for (sx, sy), ang, lab in sensors:
    ax.add_patch(Wedge((sx, sy), RANGE, ang - HALF, ang + HALF, fc="#2b6cb0", ec="#2b6cb0", alpha=0.10, lw=0.5, zorder=1))
    tx, ty = sx + 1.08 * RANGE * math.cos(math.radians(ang)), sy + 1.08 * RANGE * math.sin(math.radians(ang))
    ax.text(tx, ty, lab, ha="center", va="center", fontsize=7, color="#2b6cb0", fontweight="bold")
ax.add_patch(Circle((0, 0), 1000, fc="none", ec="#999", lw=0.4, ls=":"))
ax.text(0, -1015, "1 m", ha="center", va="top", fontsize=6, color="#777")
front_arrow(ax, 950, -1000, 150)
for a in (60, 135, -60, -135):
    r = 700
    ax.text(r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), "blind\nwedge", ha="center", va="center", fontsize=6.5, color="#c0392b")
finish(fig, ax, "dwg_sonar", (-1350, 1400), (-1250, 1320), "Ultrasonic coverage: 7 × HC-SR04, 30° beams, drawn to 1 m")

# ------------------------------------------------------------------ underside
under_only = lambda p: p["bbox"][5] <= deck["z0"] + 0.1 or p["name"].startswith(("Wheel", "Sonar"))
fig, ax = plt.subplots(figsize=(7.4, 5.2))
ax.add_patch(Rectangle((deck["x0"], -deck["y"]), DW, DH, fc="#f3e6cf", ec=INK, lw=0.6, ls="--", zorder=1))
draw(ax, "top", only=under_only)
dim(ax, (deck["x0"], -deck["y"]), (L["axle_x"], -deck["y"]), -deck["y"] - 70, f"{L['axle_x'] - deck['x0']:.0f}", side=-1)
dim(ax, (deck["x0"], -deck["y"]), (L["caster_x"], -deck["y"]), -deck["y"] - 100, f"{L['caster_x'] - deck['x0']:.0f} (caster centre)", side=-1)
dim(ax, (L["caster_x"], -L["caster_y"]), (L["caster_x"], L["caster_y"]), deck["x1"] + 50, f"{2 * L['caster_y']}", vertical=True, side=1)
dim(ax, (L["axle_x"], -L["wheel_yc"]), (L["axle_x"], L["wheel_yc"]), deck["x0"] - 50, f"track {2 * L['wheel_yc']}", vertical=True, side=-1)
ax.text(L["axle_x"], 0, "JGB37-520 + Hall encoder\n(gearbox Ø37, can Ø35.5,\nmotor 74 long)", ha="center", va="center", fontsize=6.5)
ax.text(L["caster_x"], 0, "3\" casters on\n5 mm shims;\nbrackets on\n12 mm spacers", ha="center", va="center", fontsize=6.5)
ax.text(deck["x1"] + 6, 0, "sonar strip", rotation=90, ha="center", va="center", fontsize=6)
finish(fig, ax, "dwg_under", (deck["x0"] - 90, deck["x1"] + 90), (-deck["y"] - 125, deck["y"] + 95), "Underside: parts below the deck, seen through it from above  ·  mm")

# ------------------------------------------------------------------ deck drilling template (from the rear-left corner)
fig, ax = plt.subplots(figsize=(7.4, 6.0))
ox, oy = deck["x0"], deck["y"]           # origin: rear-left corner of the deck
def D(x, y):
    return x - ox, oy - y                 # mm from rear edge, mm from left edge
ax.add_patch(Rectangle((0, 0), DW, DH, fc="#f3e6cf", ec=INK, lw=0.8))
for (x0, x1, y0, y1) in ((0, DW, 0, 12), (0, DW, DH - 12, DH), (0, 12, 12, DH - 12), (DW - 12, DW, 12, DH - 12)):
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="#c9a26d", ec=INK, lw=0.4, alpha=0.7))
ax.text(DW / 2, 48, "walls 12 × 45 (screwed up through the deck)", ha="center", va="center", fontsize=5.5)
holes = []
for s in (1, -1):
    x0, y0 = D(L["axle_x"] - 22, s * (deck["y"] - 5)); x1, y1 = D(L["axle_x"] + 22, s * (deck["y"] - 35))
    ax.add_patch(Rectangle((x0, min(y0, y1)), x1 - x0, abs(y1 - y0), fc="#9aa3ad", ec=INK, lw=0.5, ls="--", alpha=0.5))
    ax.text((x0 + x1) / 2, (y0 + y1) / 2, "bracket +\nspacer\n(underside)", ha="center", va="center", fontsize=5)
    rx0, ry0 = D(L["caster_x"] - 32.5, s * L["caster_y"] + 25)
    ax.add_patch(Rectangle((rx0, ry0), 65, 50, fc="#d8b483", ec=INK, lw=0.5, ls="--"))
    ax.text(rx0 + 32.5, ry0 + 25, "caster +\nshim\n(underside)", ha="center", va="center", fontsize=5)
    holes.append(("Wire hole (motor + encoder cables)", "Ø16", *D(WH[0], s * WH[1])))
for x in (-160, -40, 80, 170):
    for s in (1, -1):
        holes.append(("Wall screw, 4 × 40 wood screw from below", "Ø4.5, countersunk", *D(x, s * (deck["y"] - 6))))
for x in (deck["x0"] + 6, deck["x1"] - 6):
    for y in (-95, 0, 95):
        holes.append(("Wall screw, 4 × 40 wood screw from below", "Ø4.5, countersunk", *D(x, y)))
ax.add_patch(Rectangle((DW, 0), 12, DH, fc="#d8b483", ec=INK, lw=0.5))
ax.text(DW + 6, DH / 2, "sonar strip (screws into the front edge)", rotation=90, ha="center", va="center", fontsize=5.5)
for name, size, hx, hy in holes:
    r = 8 if size.startswith("Ø16") else 2.25
    ax.add_patch(Circle((hx, hy), max(r, 2.6), fc="white", ec=DIM, lw=0.7, zorder=5))
ax.invert_yaxis()
dim(ax, (0, DH), (DW, DH), DH + 32, f"{DW}", side=1)
dim(ax, (0, 0), (0, DH), -26, f"{DH}", vertical=True, side=-1)
front_arrow(ax, DW + 22, DH / 2, 30)
ax.text(0, -8, "origin: rear-left corner (seen from above)", fontsize=6, va="bottom")
for i, (name, size, hx, hy) in enumerate(holes):
    right = hx > DW - 50
    ax.text(hx + (-5 if right else 5), hy + (12 if hy < DH / 2 else -6), str(i + 1), fontsize=5.5, color=DIM, zorder=7, ha="right" if right else "left")
ax.set_xlim(-60, DW + 100); ax.set_ylim(DH + 60, -30); ax.set_aspect("equal"); ax.axis("off")
ax.set_title("Deck drilling template (12 mm plywood, top face)  ·  mm", fontsize=9, loc="left", color=INK, fontweight="bold")
fig.savefig(os.path.join(IMG, "dwg_drill.svg"), bbox_inches="tight", pad_inches=0.04)
plt.close(fig)
hole_table = [dict(n=i + 1, name=n, size=s, from_rear=round(hx), from_left=round(hy)) for i, (n, s, hx, hy) in enumerate(holes)]

# ------------------------------------------------------------------ plywood cut plan (one 2' x 2' sheet, 610 x 610 x 12)
fig, ax = plt.subplots(figsize=(5.2, 5.2))
ax.add_patch(Rectangle((0, 0), 610, 610, fc="#f6ead6", ec=INK, lw=0.8))
cuts = [("Deck 400 × 300", 0, 0, 400, 300, "#d8b483"),
        ("Side wall L 400 × 45", 0, 303, 400, 45, "#c9a26d"), ("Side wall R 400 × 45", 0, 351, 400, 45, "#c9a26d"),
        ("Front wall 276 × 45", 0, 399, 276, 45, "#c9a26d"), ("Rear wall 276 × 45", 0, 447, 276, 45, "#c9a26d"),
        ("Sonar strip 300 × 50", 0, 495, 300, 50, "#d8b483"),
        ("Spacer\n44×30", 403, 0, 44, 30, "#e3c79a"), ("Spacer\n44×30", 450, 0, 44, 30, "#e3c79a")]
for t, x, y, w, h, c in cuts:
    ax.add_patch(Rectangle((x, y), w, h, fc=c, ec=INK, lw=0.6))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=6.5 if w > 60 else 5, rotation=90 if (h > 2.5 * w and w < 60) else 0)
ax.text(305, 615, "12 mm plywood, 2 ft × 2 ft (610 × 610) · 3 mm saw cuts allowed", ha="center", va="bottom", fontsize=6.5)
ax.text(505, 200, "Spacers go between each\nmotor bracket and the deck.\nThe rest is spare (wedges\nfor the front sensors).", ha="center", va="center", fontsize=6)
ax.text(455, 470, "Caster shims: 5 mm\n(hardboard or washers),\n105 − caster height", ha="center", va="center", fontsize=6)
ax.set_xlim(-10, 620); ax.set_ylim(-10, 640); ax.set_aspect("equal"); ax.axis("off")
ax.set_title("Plywood cut plan  ·  mm", fontsize=9, loc="left", color=INK, fontweight="bold")
fig.savefig(os.path.join(IMG, "dwg_cut.svg"), bbox_inches="tight", pad_inches=0.04)
plt.close(fig)

# ------------------------------------------------------------------ mass, balance, stability
EXTRA = [("Wires, bolts, screws, cable ties", 0.35, [150, 0, 120])]
rover = [(p["name"], p["mass"], p["com"]) for p in P if not p["name"].startswith("Payload")] + EXTRA
pay = [(p["name"], p["mass"], p["com"]) for p in P if p["name"].startswith("Payload")]


def cg(items):
    m = sum(i[1] for i in items)
    c = np.sum([np.array(i[2]) * i[1] for i in items], axis=0) / m
    return m, c


m_r, c_r = cg(rover)
m_t, c_t = cg(rover + pay)
cx_contact = caster_wheel_x  # caster wheels trail behind the swivel when driving forward
wb = cx_contact - L["axle_x"]
drive_share = (cx_contact - c_t[0]) / wb
g = 9.81
F = m_t * g * 0.03 + m_t * g * math.sin(math.atan(0.08)) + m_t * 0.3
torque = F * (L["wheel_d"] / 2000) / 2
grip = 0.7 * drive_share * m_t * g

# static tip angles (CG height h above ground)
h = c_t[2]
fwd = math.degrees(math.atan((cx_contact - c_t[0]) / h))
back = math.degrees(math.atan((c_t[0] - L["axle_x"]) / h))
# sideways: line from rear wheel contact (-110, 235) to caster contact (175, 140)
p1, p2 = np.array([L["axle_x"], L["wheel_yc"]]), np.array([cx_contact, L["caster_y"]])
t = p2 - p1
n = np.array([t[1], -t[0]]) / np.linalg.norm(t)
side_dist = abs(np.dot(np.array([c_t[0], c_t[1]]) - p1, n))
side = math.degrees(math.atan(side_dist / h))

# turning on the spot about the axle centre
spin_pts = [(XMAX, YMAX), (XMIN, YMAX), (L["axle_x"] + 65, YMAX)]
spin_r = max(math.hypot(x - L["axle_x"], y) for x, y in spin_pts)

comp = sorted(rover + pay, key=lambda i: -i[1])
analysis = dict(
    overall=dict(length=round(XMAX - XMIN), width=round(YMAX - YMIN), height=round(lid_top),
                 wheelbase=L["caster_x"] - L["axle_x"], track=2 * L["wheel_yc"], deck_top=DT,
                 ground_clearance=round(L["gb_z"] - 18.5, 1), camera_height=L["cam_pivot"][2]),
    mass_rover=round(m_r, 2), mass_total=round(m_t, 2), cg_rover=[round(v) for v in c_r], cg_total=[round(v) for v in c_t],
    drive_share=round(drive_share * 100), force_N=round(F, 1), torque_kgcm=round(torque / 0.0981, 2),
    grip_N=round(grip), tip_fwd=round(fwd), tip_back=round(back), tip_side=round(side),
    spin_diameter=round(2 * spin_r), cam_ground_ahead=round(gx - XMAX),
    speed=round(60 / 60 * math.pi * L["wheel_d"] / 1000, 3), holes=hole_table,
    masses=[dict(name=n_, kg=m) for n_, m, _ in comp],
)
json.dump(analysis, open(os.path.join(ROOT, "build", "analysis.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in analysis.items() if k not in ("holes", "masses")}, indent=1))
