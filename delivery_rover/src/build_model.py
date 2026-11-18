"""Delivery rover 3D model (all sizes in mm).

Run with FreeCAD's headless Python:
  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd src/build_model.py

Axes: x forward, y to the rover's left, z up. Origin: on the ground, under the
centre of the deck. Writes model/*.step, *.stl, *.FCStd and build/mesh.json.
"""
import json
import os

import FreeCAD as App
import Part

V = App.Vector
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MODEL = os.path.join(ROOT, "model")
OUT_BUILD = os.path.join(ROOT, "build")

# ---------------------------------------------------------------- key sizes
DECK = dict(x0=-250, x1=250, y=200, z0=93, t=12)          # 500 x 400 x 12 plywood
DECK_TOP = DECK["z0"] + DECK["t"]                          # 105
WHEEL_D, WHEEL_W = 130, 60
AXLE_X, AXLE_Z = -110, WHEEL_D / 2                         # drive axle 140 mm from the rear edge
SHAFT_OFFSET = 7                                           # JGB37 output shaft sits 7 mm off the gearbox centre
GB_Z = AXLE_Z + SHAFT_OFFSET                               # gearbox centre (shaft turned to the bottom)
WHEEL_YC = 235                                             # wheel centre line, each side
CASTER_X, CASTER_Y, CASTER_H = 195, 140, 70                # swivel axis; 2" caster overall height
RISER = DECK["z0"] - CASTER_H                              # 23 mm block under each caster
SONAR_Z, SIDE_SONAR_X, REAR_SONAR_Y = 127.5, 100, 110   # wall-mounted HC-SR04 centres
WALL_H = 45                                                # electronics compartment walls (deck top -> box floor)
BOX_Z0 = DECK_TOP + WALL_H                                 # 150: the cargo box sits on the walls
BOX = dict(x0=-250, x1=250, y=200, z0=BOX_Z0, h=250, lid=15)    # 500 x 400 x 265, about 48 L: the whole body
CAM_TILT = 12                                              # degrees down

parts = []


def B(x0, x1, y0, y1, z0, z1):
    x0, x1 = sorted((x0, x1)); y0, y1 = sorted((y0, y1)); z0, z1 = sorted((z0, z1))
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def C(r, p, axis, length):
    d = {"x": V(1, 0, 0), "y": V(0, 1, 0), "z": V(0, 0, 1)}[axis]
    if length < 0:
        d, length = d * -1, -length
    return Part.makeCylinder(r, length, V(*p), d)


def Y(a, b, s):
    return s * a, s * b


def fuse(*shapes):
    out = shapes[0]
    for s in shapes[1:]:
        out = out.fuse(s)
    return out.removeSplitter()


def add(name, group, shape, color, mass, alpha=1.0):
    parts.append(dict(name=name, group=group, shape=shape, color=color, mass=mass, alpha=alpha))


PLY, STEEL, ALU, BLACK = "#d8b483", "#9aa3ad", "#c9ced6", "#1c1c1c"

# ---------------------------------------------------------------- chassis
deck = B(DECK["x0"], DECK["x1"], -DECK["y"], DECK["y"], DECK["z0"], DECK_TOP)
for s in (1, -1):  # wire holes (motor + encoder cables come up into the bay)
    deck = deck.cut(C(8, (-150, s * 160, DECK["z0"] - 1), "z", DECK["t"] + 2))
add("Deck_plywood_500x400x12", "Chassis", deck, PLY, 1.44)

# electronics compartment: 12 mm plywood walls, 45 mm high, round the deck edge; the box floor is its roof
WT, WZ1 = 12, DECK_TOP + WALL_H
for s, side in ((1, "L"), (-1, "R")):
    w = B(-250, 250, *Y(188, 200, s), DECK_TOP, WZ1)
    for vx in (-110, -40, 150):  # vent slots
        w = w.cut(B(vx, vx + 40, *Y(186, 202, s), DECK_TOP + 15, DECK_TOP + 30))
    for tx in (SIDE_SONAR_X - 13, SIDE_SONAR_X + 13):  # side HC-SR04 transducer holes
        w = w.cut(C(8.25, (tx, s * 186, SONAR_Z), "y", s * 16))
    add(f"Wall_side_{side}_500x45x12", "Chassis", w, "#c9a26d", 0.15)
add("Wall_front_376x45x12", "Chassis", B(238, 250, -188, 188, DECK_TOP, WZ1), "#c9a26d", 0.11)
rear = B(-250, -238, -188, 188, DECK_TOP, WZ1).cut(B(-251, -237, 141, 159, 121, 134))
for yc in (REAR_SONAR_Y, -REAR_SONAR_Y):  # rear HC-SR04 transducer holes
    for ty in (yc - 13, yc + 13):
        rear = rear.cut(C(8.25, (-236, ty, SONAR_Z), "x", -16))
add("Wall_rear_376x45x12", "Chassis", rear, "#c9a26d", 0.11)

add("Sonar_strip_plywood_400x50x12", "Chassis", B(250, 262, -200, 200, 55, 105), PLY, 0.14)

# ---------------------------------------------------------------- drive (each side)
for s, side in ((1, "L"), (-1, "R")):
    plate = B(AXLE_X - 22, AXLE_X + 22, *Y(192.5, 195, s), 47, DECK["z0"])
    plate = plate.cut(C(6.5, (AXLE_X, s * 190, AXLE_Z), "y", s * 10))
    flange = B(AXLE_X - 22, AXLE_X + 22, *Y(165, 195, s), DECK["z0"] - 2, DECK["z0"])
    add(f"Motor_bracket_37mm_{side}", "Drive", fuse(plate, flange), STEEL, 0.05)

    add(f"Motor_gearbox_JGB37_{side}", "Drive", C(18.5, (AXLE_X, s * 192.5, GB_Z), "y", -s * 26.5), "#b9b9b9", 0.09)
    add(f"Motor_can_520_{side}", "Drive", C(17.75, (AXLE_X, s * 166, GB_Z), "y", -s * 30.5), "#7d838b", 0.08)
    enc = fuse(C(17, (AXLE_X, s * 135.5, GB_Z), "y", -s * 17),
               B(AXLE_X - 27, AXLE_X - 17, *Y(121, 131, s), GB_Z - 6, GB_Z + 6))
    add(f"Motor_Hall_encoder_{side}", "Drive", enc, BLACK, 0.03)
    add(f"Motor_shaft_6mm_{side}", "Drive", C(3, (AXLE_X, s * 192.5, AXLE_Z), "y", s * 17), "#d0d0d0", 0.005)

    tyre = C(WHEEL_D / 2, (AXLE_X, s * 205, AXLE_Z), "y", s * WHEEL_W).cut(
        C(42, (AXLE_X, s * 204, AXLE_Z), "y", s * (WHEEL_W + 2)))
    add(f"Wheel_tyre_130x60_{side}", "Drive", tyre, "#222222", 0.12)
    rim = C(42, (AXLE_X, s * 208, AXLE_Z), "y", s * 54).cut(C(34, (AXLE_X, s * 256, AXLE_Z), "y", s * 8))
    rim = fuse(rim, C(11, (AXLE_X, s * 196, AXLE_Z), "y", s * 12))
    add(f"Wheel_hub_6mm_coupling_{side}", "Drive", rim, "#2563eb", 0.08)

# ---------------------------------------------------------------- casters (front)
for s, side in ((1, "L"), (-1, "R")):
    cy = s * CASTER_Y
    add(f"Caster_riser_block_{side}", "Chassis", B(CASTER_X - 30, CASTER_X + 30, cy - 30, cy + 30, CASTER_H, DECK["z0"]), PLY, 0.05)
    wx = CASTER_X - 20  # wheel trails 20 mm behind the swivel axis
    frame = fuse(
        B(CASTER_X - 25, CASTER_X + 25, cy - 25, cy + 25, CASTER_H - 3, CASTER_H),
        C(15, (CASTER_X, cy, CASTER_H - 10), "z", 7),
        B(wx - 8, CASTER_X + 8, cy - 12.5, cy + 12.5, CASTER_H - 12, CASTER_H - 9),
        B(wx - 8, CASTER_X + 8, cy + 10, cy + 12.5, 18, CASTER_H - 9),
        B(wx - 8, CASTER_X + 8, cy - 12.5, cy - 10, 18, CASTER_H - 9),
        C(4, (wx, cy - 14, 25), "y", 28),
    )
    add(f"Caster_2in_swivel_frame_{side}", "Chassis", frame, STEEL, 0.04)
    add(f"Caster_2in_wheel_{side}", "Chassis", C(25, (wx, cy - 9, 25), "y", 18), "#3d3d3d", 0.03)

# ---------------------------------------------------------------- electronics bay (deck top z = 105)
Z = DECK_TOP
BTS_X = -125
for name, y0 in (("L", 135), ("R", -185)):
    x0 = BTS_X
    board = B(x0, x0 + 50, y0, y0 + 50, Z + 5, Z + 6.6)
    for (sx, sy) in ((x0 + 4, y0 + 4), (x0 + 46, y0 + 4), (x0 + 4, y0 + 46), (x0 + 46, y0 + 46)):
        board = board.fuse(C(2.5, (sx, sy, Z), "z", 5))
    add(f"BTS7960_board_{name}", "Electronics", board.removeSplitter(), "#b23a3a", 0.03)
    hs = B(x0 + 10, x0 + 48, y0 + 6, y0 + 44, Z + 6.6, Z + 36.6)
    for i in range(6):
        hs = hs.cut(B(x0 + 9, x0 + 49, y0 + 8.5 + i * 6, y0 + 11.5 + i * 6, Z + 14, Z + 37))
    add(f"BTS7960_heatsink_{name}", "Electronics", hs.removeSplitter(), ALU, 0.035)
    add(f"BTS7960_terminals_{name}", "Electronics", B(x0, x0 + 9, y0 + 3, y0 + 25, Z + 6.6, Z + 17), "#1e5aa8", 0.005)

# battery at the back, over the drive wheels (more grip)
cells = [C(9.2, (-230, iy * 18.6, Z + 9.3 + iz * 18.6), "x", 65) for iy in (-1, 0, 1) for iz in (0, 1)]
add("Battery_3S2P_18650_pack", "Power", fuse(*cells), "#2f6db5", 0.30)
add("Battery_BMS_3S_25A", "Power", B(-230, -170, 40, 85, Z, Z + 4), "#1b5e20", 0.02)
add("Fuse_holder_5x20", "Power", B(-158, -125, 45, 55, Z, Z + 10), BLACK, 0.01)
add("XT60_plug_pair", "Power", B(-158, -128, 65, 75, Z, Z + 8), "#e8c21a", 0.01)

xl = fuse(B(-60, -6, -100, -77, Z + 4, Z + 5.6), C(6, (-42, -88.5, Z + 5.6), "z", 8),
          C(4, (-24, -88.5, Z + 5.6), "z", 10), B(-17, -9, -99, -94, Z + 5.6, Z + 14))
add("XL4015_buck_5V", "Power", xl, "#1565c0", 0.03)

esp = fuse(B(-40, -12, -26, 26, Z + 8, Z + 9.6), B(-40, -37.5, -25, 25, Z, Z + 8), B(-14.5, -12, -25, 25, Z, Z + 8))
add("ESP32_DevKit_30pin", "Electronics", esp, "#202020", 0.01)
add("ESP32_WROOM_module", "Electronics", B(-36, -18, -26, -0.5, Z + 9.6, Z + 12.8), "#c0c0c0", 0.002)

# phone at the front, away from the motors and battery wires
add("Phone_foam_pad", "Electronics", B(160, 236, -82, 82, Z, Z + 10), "#5c5c5c", 0.01)
add("Phone_Redmi_K50_Pro_163x76x8.5", "Electronics", B(160.4, 236.4, -81.55, 81.55, Z + 10, Z + 18.5), "#15171c", 0.23)

# main switch (kill switch) in the rear wall
add("Rocker_switch_KCD1_body", "Power", fuse(B(-253, -250, 139.5, 160.5, 120, 135), B(-250, -230, 141, 159, 121, 134)), BLACK, 0.008)
add("Rocker_switch_KCD1_rocker", "Power", B(-256, -253, 142.5, 157.5, 122.5, 132.5), "#d62828", 0.002)

for i, yc in enumerate((140, 0, -140)):
    hc = fuse(B(262, 263.6, yc - 22.5, yc + 22.5, 70, 90),
              C(8, (263.6, yc + 13, 80), "x", 12), C(8, (263.6, yc - 13, 80), "x", 12))
    if yc:  # outer front sensors turned 30 degrees outward on a small wooden wedge
        hc.rotate(V(262, yc, 80), V(0, 0, 1), 30 if yc > 0 else -30)
    add(f"HC-SR04_Front_{['L', 'C', 'R'][i]}", "Sensors", hc, "#1e4fa0", 0.009)

# rear pair and one per side: board on the inside of the wall, transducers through 16.5 mm holes (flush outside)
for side, yc in (("L", REAR_SONAR_Y), ("R", -REAR_SONAR_Y)):
    hc = fuse(B(-238, -236.4, yc - 22.5, yc + 22.5, SONAR_Z - 10, SONAR_Z + 10),
              C(8, (-238, yc + 13, SONAR_Z), "x", -12), C(8, (-238, yc - 13, SONAR_Z), "x", -12))
    add(f"HC-SR04_Rear_{side}", "Sensors", hc, "#1e4fa0", 0.009)
for s, side in ((1, "L"), (-1, "R")):
    xc = SIDE_SONAR_X
    hc = fuse(B(xc - 22.5, xc + 22.5, *Y(186.4, 188, s), SONAR_Z - 10, SONAR_Z + 10),
              C(8, (xc + 13, s * 188, SONAR_Z), "y", s * 12), C(8, (xc - 13, s * 188, SONAR_Z), "y", s * 12))
    add(f"HC-SR04_Side_{side}", "Sensors", hc, "#1e4fa0", 0.009)

# ---------------------------------------------------------------- cargo box
bx0, bx1, by, bz0, bh = BOX["x0"], BOX["x1"], BOX["y"], BOX["z0"], BOX["h"]
body = B(bx0, bx1, -by, by, bz0, bz0 + bh).cut(B(bx0 + 2.5, bx1 - 2.5, -by + 2.5, by - 2.5, bz0 + 2.5, bz0 + bh + 1))
body = body.fuse(B(bx0 - 2.5, bx1 + 2.5, -by - 2.5, by + 2.5, bz0 + bh - 8, bz0 + bh).cut(
    B(bx0 + 2.5, bx1 - 2.5, -by + 2.5, by - 2.5, bz0 + bh - 9, bz0 + bh + 1))).removeSplitter()
add("Cargo_box_48L_500x400x250", "Cargo", body, "#e6eaef", 1.20, alpha=0.55)
lid_top = bz0 + bh + BOX["lid"]
lid = B(bx0 - 3, bx1 + 3, -by - 3, by + 3, bz0 + bh, lid_top).cut(
    B(bx0 - 0.5, bx1 + 0.5, -by - 0.5, by + 0.5, bz0 + bh - 1, lid_top - 2.5))
add("Cargo_box_lid", "Cargo", lid, "#2b6cb0", 0.40)
add("Payload_5kg_example_300x250x150", "Payload", B(-150, 150, -125, 125, bz0 + 2.5, bz0 + 152.5), "#c49a6c", 5.0)

cam_pivot = V(bx1 + 5, 0, 304)
cam = fuse(B(bx1 + 5, bx1 + 33, -45, 45, 290, 318), C(7.5, (bx1 + 33, 0, 306), "x", 3))
cam.rotate(cam_pivot, V(0, 1, 0), CAM_TILT)
add("Webcam_HD-U01_1080p", "Sensors", cam, "#151515", 0.08)
add("Webcam_bracket", "Sensors", B(bx1, bx1 + 5, -15, 15, 284, 326), BLACK, 0.01)

sz = bz0 + bh - 32
servo = fuse(B(bx0 - 12.2, bx0, -11.4, 11.4, sz, sz + 28.5), B(bx0 - 12.2, bx0, -16.4, 16.4, sz + 15, sz + 17.5),
             C(3, (bx0 - 6.1, 5, sz + 28.5), "z", 4))
add("Servo_MG90S_lid_latch", "Cargo", servo, "#2a2a2a", 0.014)

# ---------------------------------------------------------------- outputs
doc = App.newDocument("DeliveryRover")
groups = {}
objs = []
for p in parts:
    if p["group"] not in groups:
        groups[p["group"]] = doc.addObject("App::Part", p["group"])
    o = doc.addObject("Part::Feature", p["name"].replace(".", "_").replace("-", "_"))
    o.Label = p["name"]
    o.Shape = p["shape"]
    groups[p["group"]].addObject(o)
    objs.append(o)
top = doc.addObject("App::Part", "DeliveryRover")
for g in groups.values():
    top.addObject(g)
doc.recompute()

os.makedirs(OUT_MODEL, exist_ok=True)
os.makedirs(OUT_BUILD, exist_ok=True)
doc.saveAs(os.path.join(OUT_MODEL, "delivery_rover.FCStd"))

import Import  # noqa: E402
import Mesh  # noqa: E402

Import.export([top], os.path.join(OUT_MODEL, "delivery_rover.step"))
Mesh.export([o for o in objs if not o.Label.startswith("Payload")], os.path.join(OUT_MODEL, "delivery_rover.stl"))


def edges_of(shape):
    out = []
    seams = set()
    for f in shape.Faces:
        for e in f.Edges:
            try:
                if e.isSeam(f):
                    seams.add(e.hashCode())
            except Exception:
                pass
    for e in shape.Edges:
        if e.hashCode() in seams:
            continue
        pts = e.discretize(Deflection=0.4) if e.Length > 0.5 else []
        if len(pts) >= 2:
            out.append([[round(c, 2) for c in (q.x, q.y, q.z)] for q in pts])
    return out


mesh = []
for p in parts:
    sh = p["shape"]
    pts, tris = sh.tessellate(0.25)
    vol = sum(s.Volume for s in sh.Solids)
    com = sum((s.CenterOfMass * s.Volume for s in sh.Solids), V(0, 0, 0)) * (1.0 / vol)
    bb = sh.BoundBox
    mesh.append(dict(
        name=p["name"], group=p["group"], color=p["color"], alpha=p["alpha"], mass=p["mass"],
        com=[com.x, com.y, com.z], bbox=[bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax],
        verts=[[round(q.x, 3), round(q.y, 3), round(q.z, 3)] for q in pts], tris=[list(t) for t in tris],
        edges=edges_of(sh),
    ))

layout = dict(deck=DECK, deck_top=DECK_TOP, wheel_d=WHEEL_D, wheel_w=WHEEL_W, axle_x=AXLE_X,
              axle_z=AXLE_Z, gb_z=GB_Z, wheel_yc=WHEEL_YC, caster_x=CASTER_X, caster_y=CASTER_Y,
              caster_h=CASTER_H, riser=RISER, wall_h=WALL_H, box_z0=BOX_Z0, box=BOX, cam_tilt=CAM_TILT,
              cam_pivot=[cam_pivot.x, cam_pivot.y, cam_pivot.z])
with open(os.path.join(OUT_BUILD, "mesh.json"), "w") as f:
    json.dump(dict(layout=layout, parts=mesh), f)
print("parts", len(parts), "tris", sum(len(m["tris"]) for m in mesh))
