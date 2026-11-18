"""Writes docs/delivery_rover_build_pack.html, then prints it to PDF with headless Brave/Chrome."""
import json
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
A = json.load(open(os.path.join(ROOT, "build", "analysis.json")))
O = A["overall"]


def rs(n):
    return f"{n:,.0f}"


# ------------------------------------------------------------------ bought parts
DARAZ = [("JGB37-520 12 V 60 RPM geared motor with Hall encoder. Options: <b>Without Stand / 60RPM / 12V</b>", 2, 4909,
          "https://www.daraz.lk/products/jgb37-520-hall-encoder-dc-geared-motor-6v12v-reversible-high-torque-21kgcm-all-metal-geared-dc-motor-with-hall-encoder-i750970075.html")]
ALPHA = [
    ("Double BTS7960 43 A motor driver (1 per motor)", 2, 1250, "https://alphatronic.lk/product/double-bts7960-43a-motor-driver-module/"),
    ("XL4015 buck converter, set to 5.1 V", 1, 340, "https://alphatronic.lk/product/xl4015-dc-to-dc-step-down-buck-adjustable-module/"),
    ("MG90S metal-gear servo (lid latch)", 1, 580, "https://alphatronic.lk/product/mg90s-metal-gear-micro-servo-9g/"),
    ("USB webcam HD-U01, 1080p 30 fps, 90° wide angle", 1, 2850, "https://alphatronic.lk/product/usb-laptop-pc-camera-hd-u01-1080p-webcam/"),
    ("USB-C male to USB-A female OTG cable, 15 cm", 1, 450, "https://alphatronic.lk/product/usb-c-male-to-usb-3-0-a-female-otg-cable/"),
]
DUINO = [
    ("130 mm truck wheel, 60 mm wide, 6 mm coupling (blue)", 2, 1890, "https://www.duino.lk/product/130mm-truck-wheels-tires-60mm-width/"),
    ("GA/GB 37 mm geared motor mounting bracket", 2, 580, "https://www.duino.lk/product/ga-gb-37mm-diameter-dc-geared-motor/"),
    ("18650 3.7 V 3200 mAh cell", 6, 680, "https://www.duino.lk/product/battery-3800mah-3-7v-18650-rechargeable/"),
    ("3S 25 A BMS 12.6 V with balance", 1, 470, "https://www.duino.lk/product/3s-bms-11-1v-12-6v-25a-w-balance-li-ion-battery/"),
    ("12.6 V 2 A charger", 1, 1190, "https://www.duino.lk/product/12-6v-2a-3pin-ac-dc-power-adaptor/"),
    ("HC-SR04 ultrasonic sensor (3 front, 2 rear, 2 sides) <span class='new'>+4</span>", 7, 275, "https://www.duino.lk/product/ultrasonic-distance-measuring-transducer/"),
    ("KCD1 10 A rocker switch (main power and kill switch)", 1, 90, "https://www.duino.lk/product/kcd1-rocker-switch-red-10a-250v-ac-4-pin/"),
    ("5 × 20 mm fuse holder", 1, 60, "https://www.duino.lk/product/10a-250v-5x20mm-glass-fuse-holder/"),
    ("XT60 male and female pair (battery plug)", 1, 110, "https://www.duino.lk/product/xt-60-male-female-bullet-connectors-plugs/"),
]
SHOP = [
    ("Plastic storage box with lid, about 48 L, footprint 500 × 400 (or smaller), about 250 high <span class='new'>body</span>", "1", 3000),
    ("12 mm plywood, 2 ft × 2 ft (610 × 610): deck, 4 walls, sonar strip, risers", "1", 1000),
    ("2\" (50 mm) swivel caster, rated 10 kg or more, about 70 mm high", "2", 900),
    ("Screws, bolts, nuts and washers (see the fastener list)", "set", 900),
    ("18 AWG red/black wire 2 m each, 26 AWG hook-up wire, Dupont jumpers, heat shrink", "set", 700),
    ("Resistors 1 kΩ and 2 kΩ, 7 of each (5 V to 3.3 V echo dividers), small perfboard", "set", 100),
    ("Spot-weld the 6 cells into a 3S2P pack (battery or phone-repair shop)", "1", 500),
    ("10 A glass fuses, 5 × 20 mm", "2", 50),
]
FASTENERS = [
    ("Motor to bracket", "M3 × 6 machine screw", 8, "4 per motor, into the gearbox face"),
    ("Bracket to deck underside", "M4 × 20 bolt + nut + washer (or 4 × 20 wood screw)", 8, "mark through the bracket holes"),
    ("Caster + riser to deck", "M4 × 50 bolt + nyloc nut + 2 washers", 8, "through caster plate, 2 riser layers and deck"),
    ("Walls to deck", "4 × 40 countersunk wood screw", 14, "up through the deck (holes 3–16 on the template)"),
    ("Wall corners", "4 × 30 wood screw + PVA glue", 8, "2 per corner"),
    ("Box floor to wall tops", "4 × 30 wood screw + 25 mm washer", 6, "from inside the box, down into the wall tops"),
    ("Sonar strip to deck front edge", "4 × 30 wood screw", 3, ""),
    ("BTS7960, XL4015 to deck", "M3 × 10 screw + 5 mm nylon spacer", 12, "or 3 × 12 wood screws"),
    ("ESP32 and BMS", "double-sided foam tape", "—", ""),
    ("HC-SR04 (7)", "hot glue or 2 × M2 screws each", "—", "wall sensors: board inside, cans through Ø16.5 holes"),
    ("Servo latch", "2 × M2 × 10 + nuts", 2, "rear wall of the box, under the lid lip"),
    ("Webcam bracket", "M3 × 10 + nut, 2 washers", 2, "front face of the box"),
    ("Battery pack", "Velcro strap or 2 cable ties", 1, ""),
    ("Wiring", "cable ties 100 mm, adhesive tie bases", "20", ""),
]
TOOLS = ["Drill with 3, 4.5, 8 mm bits; 16 mm spade bit or hole saw", "Jigsaw or hand saw; sandpaper", "Screwdrivers, 7 mm and 8 mm spanners",
         "Soldering iron, solder, flux; hot-glue gun", "Multimeter (set the XL4015 to 5.1 V before connecting anything)", "Wire stripper; heat gun or lighter for heat shrink"]

DIMS = [
    ("Deck (plywood)", "500 × 400 × 12", "cut list"),
    ("Electronics walls", "500 × 45 × 12 (2), 376 × 45 × 12 (2)", "cut list"),
    ("Cargo box (body)", "500 × 400 × 250, lid 506 × 406 × 15", "pick a box this size or smaller"),
    ("Wheel", "Ø130 × 60, 6 mm hub", "listing"),
    ("JGB37-520 motor", "gearbox Ø37 × 26.5, can Ø35.5 × 30.5, encoder Ø34 × 17; shaft Ø6 D, 7 mm off centre", "datasheet, check yours"),
    ("37 mm bracket", "plate 44 × 46, flange 44 × 30, 2.5 thick (modelled)", "measure yours"),
    ("2\" caster", "70 high, plate 50 × 50, wheel Ø50 × 18, 20 mm trail", "measure: riser = 93 − caster height"),
    ("Riser block", "60 × 60 × 23 (2 × 12 mm plywood, sanded)", "cut list"),
    ("3S2P pack", "65 × 56 × 37 (6 × 18650 Ø18.4 × 65)", "calculated"),
    ("BMS 3S 25 A", "60 × 45 × 4", "typical"),
    ("BTS7960 module", "50 × 50, about 37 high with heatsink", "typical"),
    ("XL4015 module", "54 × 23 × 15", "typical"),
    ("ESP32 DevKit 30-pin", "52 × 28 × 13", "typical"),
    ("HC-SR04", "45 × 20 board, Ø16 × 12 cans, 26 mm apart", "datasheet"),
    ("MG90S servo", "22.8 × 12.2 × 28.5", "datasheet"),
    ("Webcam HD-U01", "about 90 × 28 × 28", "estimate, measure yours"),
    ("Phone (Redmi K50 Pro)", "163.1 × 76.2 × 8.5", "maker's spec"),
]

PINS = [
    ("BTS7960 #1 (left) RPWM / LPWM", "GPIO 25 / 26", "R_EN + L_EN tied to 5 V (always on)"),
    ("BTS7960 #2 (right) RPWM / LPWM", "GPIO 32 / 33", "R_EN + L_EN tied to 5 V"),
    ("Left encoder A / B", "GPIO 18 / 19", "PCNT; encoder powered from 3.3 V"),
    ("Right encoder A / B", "GPIO 21 / 22", "PCNT"),
    ("Sonar trigger group 1: front-centre + rear-left", "GPIO 4", "groups never face the same way"),
    ("Sonar trigger group 2: front-left + side-right + rear-right", "GPIO 16", "fire groups one after another"),
    ("Sonar trigger group 3: front-right + side-left", "GPIO 17", "full scan about 75 ms (13 Hz)"),
    ("Echo F-L / F-C / F-R", "GPIO 34 / 35 / 36", "each through 1 kΩ (series) + 2 kΩ (to GND)"),
    ("Echo S-L / S-R", "GPIO 39 / 27", "divider as above"),
    ("Echo B-L / B-R", "GPIO 14 / 23", "divider as above"),
    ("Servo signal", "GPIO 13", "servo powered from 5 V"),
    ("Status LED", "GPIO 2", "on-board LED"),
    ("Spare", "GPIO 5, 15", ""),
]

STEPS = [
    "Cut the plywood (cut plan). Glue and screw the four walls into a frame, then screw the frame to the deck from below (14 countersunk screws).",
    "Drill the deck: two Ø16 wire holes, the wall-screw holes, then the bracket and caster holes by marking through the parts. Cut the 40 × 15 vent slots and the Ø16.5 sensor holes in the walls, and the 19 × 13 switch hole in the rear wall (thin the wall to about 2 mm around it from inside so the clips grip).",
    "Fit the motors to the brackets (shaft at the bottom, 7 mm below the gearbox centre), bolt the brackets under the deck with the axle 140 mm from the rear edge, and push the wheels on and tighten their grub screws.",
    "Stack two 60 × 60 risers under each caster and bolt them through the deck, 445 mm from the rear edge and 60 mm in from each side. Check the deck sits level; sand the risers if not.",
    "Have the cells spot-welded as 3S2P, solder the BMS balance leads, and fit the XT60. Charge it once with the 12.6 V charger.",
    "Set the XL4015 to 5.1 V with the multimeter <b>before</b> connecting anything to it.",
    "Mount the boards (layout drawing). Wire the power path: battery, XT60, fuse, rocker switch, then the BTS7960s and the XL4015. Join all grounds at one point.",
    "Build the 7 echo dividers on perfboard, wire the sensors and the encoders to the ESP32 (pin map), and route the motor and encoder cables up through the Ø16 holes.",
    "Screw the sonar strip to the front edge; glue the front-left and front-right sensors on 30° wedges. Fit the wall sensors from inside.",
    "Put the phone on the foam pad (screen up, at the front), plug in the OTG cable and lead it up to the webcam through a small grommet in the box floor.",
    "Screw the box floor down onto the wall tops, mount the webcam (about 300 mm up, tilted 12° down) and the servo latch, and calibrate the phone compass with everything powered.",
]

daraz = sum(q * p for _, q, p, _ in DARAZ)
alpha = sum(q * p for _, q, p, _ in ALPHA)
duino = sum(q * p for _, q, p, _ in DUINO)
shop = sum(p for _, _, p in SHOP)
delivery = 1330
total = daraz + alpha + duino + shop + delivery


def table_buy(rows, start):
    out = ["<table><tr><th>#</th><th>Part</th><th class='n'>Qty</th><th class='n'>Each</th><th class='n'>Total</th><th>Link</th></tr>"]
    for i, (name, q, p, url) in enumerate(rows):
        short = url.split("//")[1].split("/")[0].replace("www.", "")
        out.append(f"<tr><td>{start + i}</td><td>{name}</td><td class='n'>{q}</td><td class='n'>{rs(p)}</td><td class='n'>{rs(q * p)}</td>"
                   f"<td><a href='{url}'>{short}</a></td></tr>")
    out.append("</table>")
    return "".join(out)


masses = "".join(f"<tr><td>{m['name'].replace('_', ' ')}</td><td class='n'>{m['kg']:.3f}</td></tr>" for m in A["masses"] if m["kg"] >= 0.05)
holes = "".join(f"<tr><td>{h['n']}</td><td>{h['name']}</td><td>{h['size']}</td><td class='n'>{h['from_rear']}</td><td class='n'>{h['from_left']}</td></tr>" for h in A["holes"])

html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Delivery Rover Build Pack</title>
<style>
@page {{ size: A4; margin: 12mm 12mm 13mm; }}
body {{ font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; font-size: 8.8pt; color: #1a1a1a; line-height: 1.32; margin: 0; }}
h1 {{ font-size: 20pt; margin: 0; }}
h2 {{ font-size: 12pt; margin: 10px 0 5px; padding-bottom: 3px; border-bottom: 2px solid #2b6cb0; break-after: avoid; }}
h2 .r {{ float: right; color: #2b6cb0; }}
h3 {{ font-size: 9.5pt; margin: 8px 0 3px; break-after: avoid; }}
.sub {{ color: #555; margin: 2px 0 8px; }}
table {{ width: 100%; border-collapse: collapse; margin: 2px 0 4px; break-inside: avoid; }}
th, td {{ text-align: left; padding: 2.2px 5px; border-bottom: 1px solid #ddd; vertical-align: top; }}
th {{ background: #f1f5f9; font-size: 8pt; }}
td.n, th.n {{ text-align: right; white-space: nowrap; }}
a {{ color: #2b6cb0; text-decoration: none; }}
.page {{ break-before: page; }}
.fig {{ width: 100%; display: block; margin: 2px auto 6px; }}
.grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; align-items: start; }}
.note {{ color: #555; font-size: 8pt; margin: 3px 0; }}
.warn {{ background: #fff7e0; border-left: 3px solid #e0a800; padding: 5px 8px; margin: 6px 0; font-size: 8.4pt; }}
.new {{ font-size: 7pt; background: #dbeafe; color: #1e40af; border-radius: 6px; padding: 0 5px; }}
.total td {{ font-weight: bold; font-size: 10pt; border-top: 2px solid #333; }}
.kv td:first-child {{ color: #555; width: 55%; }}
ol {{ padding-left: 18px; margin: 3px 0; }} ol li {{ margin-bottom: 3px; }}
ul {{ padding-left: 16px; margin: 3px 0; }}
pre {{ font-size: 7.6pt; background: #f8fafc; border: 1px solid #ddd; padding: 6px; margin: 4px 0; }}
</style></head><body>

<h1>Delivery Rover: Build Pack</h1>
<p class="sub">5 kg payload · the storage box is the whole body · electronics in a closed compartment underneath · phone inside as the brain · 7 ultrasonic sensors · all sizes in mm · 18 Nov 2026</p>
<img class="fig" src="img/render_iso.png" style="width:82%">
<div class="grid2">
<table class="kv">
<tr><th colspan="2">Overall</th></tr>
<tr><td>Length × width × height</td><td>{O['length']} × {O['width']} × {O['height']}</td></tr>
<tr><td>Deck (and box footprint)</td><td>500 × 400, top at {O['deck_top']}</td></tr>
<tr><td>Wheelbase (axle to caster swivel)</td><td>{O['wheelbase']}</td></tr>
<tr><td>Track (wheel centres)</td><td>{O['track']}</td></tr>
<tr><td>Ground clearance (under the motors)</td><td>{O['ground_clearance']}</td></tr>
<tr><td>Cargo space inside the box</td><td>about 495 × 395 × 245 (48 L)</td></tr>
<tr><td>Electronics compartment</td><td>476 × 376 × 45 high</td></tr>
</table>
<table class="kv">
<tr><th colspan="2">Performance (from the model)</th></tr>
<tr><td>Rover mass / with 5 kg package</td><td>{A['mass_rover']} kg / {A['mass_total']} kg</td></tr>
<tr><td>Speed (60 RPM, Ø130 wheels)</td><td>{A['speed']} m/s</td></tr>
<tr><td>Weight on the drive wheels</td><td>{A['drive_share']} %</td></tr>
<tr><td>Torque needed per motor (8% ramp + accel.)</td><td>{A['torque_kgcm']} kg·cm</td></tr>
<tr><td>Static tip angle: forward / back / side</td><td>{A['tip_fwd']}° / {A['tip_back']}° / {A['tip_side']}°</td></tr>
<tr><td>Turning on the spot: swept circle</td><td>Ø{A['spin_diameter']}</td></tr>
<tr><td>Camera height / sees ground from</td><td>{O['camera_height']:.0f} / {A['cam_ground_ahead']} ahead</td></tr>
</table>
</div>
<div class="grid2"><img class="fig" src="img/render_open.png"><img class="fig" src="img/render_rear.png"></div>
<p class="note">Left: box removed, showing the electronics compartment. Right: rear, with the main switch and the two rear sensors in the rear wall.</p>

<div class="page"></div>
<h2>Side and front views</h2>
<img class="fig" src="img/dwg_side.svg" style="width:96%">
<img class="fig" src="img/dwg_front.svg" style="width:78%">

<div class="page"></div>
<h2>Top view and electronics compartment</h2>
<img class="fig" src="img/dwg_top.svg" style="width:80%">
<img class="fig" src="img/dwg_bay.svg" style="width:92%">

<div class="page"></div>
<h2>Underside and ultrasonic coverage</h2>
<img class="fig" src="img/dwg_under.svg" style="width:66%">
<img class="fig" src="img/dwg_sonar.svg" style="width:58%">
<p class="note">7 sensors with about 30° beams cover the front (a continuous 90° fan), both sides and the rear. The four corner diagonals are blind at a distance; the rover turns slowly, and the front camera also watches ahead. Closing the corners fully would need about 4 more sensors and an analogue multiplexer, because the ESP32 runs out of pins.</p>

<div class="page"></div>
<h2>Plywood cut plan and hole list</h2>
<div class="grid2"><img class="fig" src="img/dwg_cut.svg">
<div><h3>Hole list (mm from the rear edge / left edge, seen from above)</h3>
<table><tr><th>#</th><th>Hole</th><th>Size</th><th class="n">Rear</th><th class="n">Left</th></tr>{holes}</table>
<p class="note">Bracket and caster holes: hold the part in place and mark through it, because hole spacing varies by seller.</p></div></div>
<div class="page"></div><h2>Deck drilling template</h2><img class="fig" src="img/dwg_drill.svg" style="width:100%"><p class="note">Numbers match the hole list on the previous page. Seen from above, front to the right.</p>

<div class="page"></div>
<h2>Bill of materials <span class="r">≈ Rs {rs(total)}</span></h2>
<h3>daraz.lk: Rs {rs(daraz)} (log in and add to cart)</h3>{table_buy(DARAZ, 1)}
<h3>alphatronic.lk: Rs {rs(alpha)} (in cart)</h3>{table_buy(ALPHA, 2)}
<h3>duino.lk: Rs {rs(duino)} (in cart)</h3>{table_buy(DUINO, 7)}
<p class="note">ESP32: using your own. duino has the ESP32 CP2102 Type-C 30-pin for Rs 1,570 if needed.</p>
<h3>Hardware shop (estimates): about Rs {rs(shop)}</h3>
<table><tr><th>#</th><th>Item</th><th class="n">Qty</th><th class="n">About</th></tr>
{''.join(f"<tr><td>{16 + i}</td><td>{n}</td><td class='n'>{q}</td><td class='n'>{rs(p)}</td></tr>" for i, (n, q, p) in enumerate(SHOP))}</table>
<table>
<tr><td>daraz.lk</td><td class="n">{rs(daraz)}</td></tr><tr><td>alphatronic.lk</td><td class="n">{rs(alpha)}</td></tr>
<tr><td>duino.lk</td><td class="n">{rs(duino)}</td></tr><tr><td>Hardware shop (estimate)</td><td class="n">{rs(shop)}</td></tr>
<tr><td>Delivery (duino 480, alphatronic about 500, Daraz about 350)</td><td class="n">about {rs(delivery)}</td></tr>
<tr class="total"><td>Total (using your own phone and ESP32)</td><td class="n">≈ Rs {rs(total)}</td></tr></table>
<div class="warn"><b>About Rs {rs(total - 35000)} over the Rs 35,000 budget.</b> Two changes push the total over: the full-body box (about Rs 3,000 instead of Rs 1,500 for the 20 L box) and 4 more HC-SR04 (Rs 1,100). The hardware-shop prices are estimates; a cheaper box is the biggest saving.</div>

<div class="page"></div>
<h2>Fasteners, consumables and tools</h2>
<table><tr><th>Where</th><th>What</th><th class="n">Qty</th><th>Note</th></tr>
{''.join(f"<tr><td>{a}</td><td>{b}</td><td class='n'>{c}</td><td>{d}</td></tr>" for a, b, c, d in FASTENERS)}</table>
<h3>Tools</h3><ul>{''.join(f"<li>{t}</li>" for t in TOOLS)}</ul>
<h2>Component sizes used in the model</h2>
<table><tr><th>Part</th><th>Size (mm)</th><th>Source</th></tr>
{''.join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in DIMS)}</table>

<div class="page"></div>
<h2>Wiring and ESP32 pin map</h2>
<pre>3S2P pack ─ XT60 ─ fuse 10 A ─ rocker switch (rear wall, kill switch) ─┬─ BTS7960 #1 B+/B− ─ left motor M+/M−
                                                                        ├─ BTS7960 #2 B+/B− ─ right motor M+/M−
                                                                        └─ XL4015 (set 5.1 V) ─ 5 V rail
5 V rail: ESP32 VIN, BTS7960 VCC + R_EN + L_EN, 7 × HC-SR04 VCC, servo
3.3 V (ESP32 pin): both encoder boards
Phone (front of the compartment): USB-C OTG ─ webcam on the box front; Wi-Fi ─ ESP32
All grounds joined at one point near the XL4015.</pre>
<table><tr><th>Signal</th><th>ESP32 pin</th><th>Note</th></tr>
{''.join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in PINS)}</table>
<p class="note">5 V power budget: ESP32 about 250 mA, 7 sensors about 105 mA, servo up to 700 mA when moving. The XL4015 gives 5 A, so there is plenty of headroom.</p>
<h2>Assembly order</h2>
<ol>{''.join(f"<li>{s}</li>" for s in STEPS)}</ol>

<div class="page"></div>
<h2>Weight and balance</h2>
<div class="grid2">
<table><tr><th>Part (≥ 50 g)</th><th class="n">kg</th></tr>{masses}
<tr class="total"><td>Rover / with package</td><td class="n">{A['mass_rover']} / {A['mass_total']}</td></tr></table>
<div>
<table class="kv">
<tr><td>Centre of gravity, loaded (x fwd, y, z)</td><td>{A['cg_total'][0]}, {A['cg_total'][1]}, {A['cg_total'][2]}</td></tr>
<tr><td>Weight on the drive wheels</td><td>{A['drive_share']} %</td></tr>
<tr><td>Grip available (μ 0.7)</td><td>about {A['grip_N']} N</td></tr>
<tr><td>Force needed, worst case</td><td>{A['force_N']} N</td></tr>
<tr><td>Torque per motor needed</td><td>{A['torque_kgcm']} kg·cm</td></tr>
<tr><td>Motor rating (60 RPM, continuous)</td><td>about 4–5 kg·cm</td></tr>
</table>
<div class="warn">At {A['mass_total']} kg loaded, an 8% ramp while speeding up needs about {A['torque_kgcm']} kg·cm per motor: at the top of the motors' continuous rating. That is fine on flat paving (about 2 kg·cm). On ramps, accelerate gently, or keep the package to 4 kg.</div>
<p class="note">Put heavy packages at the back of the box, over the drive wheels, for grip. The battery is already at the back of the compartment for the same reason.</p>
</div></div>
<h2>3D files</h2>
<table><tr><th>File</th><th>Open with</th></tr>
<tr><td>model/delivery_rover.step</td><td>Fusion 360, SolidWorks, Onshape, FreeCAD: real solids, every part named</td></tr>
<tr><td>model/delivery_rover.FCStd</td><td>FreeCAD</td></tr>
<tr><td>model/delivery_rover.glb</td><td>Blender, Windows 3D Viewer, any glTF viewer: coloured</td></tr>
<tr><td>model/delivery_rover.stl</td><td>Mesh tools and slicers (single mesh)</td></tr>
<tr><td>docs/rover_viewer.html</td><td>Any browser: turn, zoom, hide the box/lid/package, click a part for its name</td></tr>
<tr><td>src/build_model.py</td><td>The model as code: change a size and run it in FreeCAD to rebuild everything</td></tr>
</table>
</body></html>"""

out_html = os.path.join(DOCS, "delivery_rover_build_pack.html")
open(out_html, "w").write(html)
browser = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
pdf = os.path.join(DOCS, "delivery_rover_build_pack.pdf")
subprocess.run([browser, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", "file://" + out_html],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
print("total", total, "pdf", os.path.getsize(pdf))
