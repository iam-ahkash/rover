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
CH = "<span class='chg'>changed</span> "
NEW = "<span class='chg'>new</span> "
T = "https://tronic.lk/product/"
AL = "https://alphatronic.lk/product/"
DARAZ = [(CH + "JGB37-520 12 V 60 RPM geared motor with Hall encoder. Options: <b>Without Stand / 60RPM / 12V</b> (link now opens on this option)", 2, 4909,
          "https://www.daraz.lk/products/jgb37-520-hall-encoder-dc-geared-motor-6v12v-reversible-high-torque-21kgcm-all-metal-geared-dc-motor-with-hall-encoder-i750970075-s2878199189.html")]
ALPHA = [
    ("Double BTS7960 43 A motor driver (1 per motor)", 2, 1250, AL + "double-bts7960-43a-motor-driver-module/"),
    ("XL4015 buck converter, set to 5.1 V", 1, 340, AL + "xl4015-dc-to-dc-step-down-buck-adjustable-module/"),
    ("MG90S metal-gear servo (lid latch)", 1, 580, AL + "mg90s-metal-gear-micro-servo-9g/"),
    ("USB webcam HD-U01, 1080p 30 fps, 90° wide angle", 1, 2850, AL + "usb-laptop-pc-camera-hd-u01-1080p-webcam/"),
    ("Panel-mount 5 × 20 mm glass fuse holder", 1, 50, AL + "glass-fuse-holder-panel-mount-fuse-socket/"),
    ("Resistors 1/4 W: <b>1.5 kΩ × 7 and 2.2 kΩ × 7</b> (echo dividers)", 14, 1, AL + "resistor-1-4w-10w-to-1mw/"),
    ("14 AWG silicone wire, 1 m: <b>1 red, 1 black</b> (battery and motor power)", 2, 340, AL + "14awg-silicone-wire-1m-red-black/"),
    ("24 AWG circuit wire per metre: <b>3 red, 3 black, 2 green, 2 yellow</b> (signals, 5 V)", 10, 30, AL + "circuit-wire-24awg/"),
    ("Heat shrink per metre: <b>2.5 mm × 2, 5 mm × 1, 8 mm × 1</b>", 1, 170, AL + "heat-shrink-tubing-1mm-28mm/"),
    ("Cable ties 4 × 150 mm, pack of 10", 2, 25, AL + "cable-tie-4x150mm-10pcs/"),
    ("M3 × 6 bolt + nut (motor to bracket)", 8, 15, AL + "m3-phillips-head-bolts-with-nuts/"),
    ("M3 × 10 bolt + nut (driver boards, buck converter, webcam)", 14, 15, AL + "m3-phillips-head-bolts-with-nuts/"),
    ("M4 hex nut, stainless (bracket bolts)", 8, 10, AL + "m4-hex-nut-stainless-steel/"),
]
TRONIC = [
    ("HC-SR04 ultrasonic sensor (3 front, 2 rear, 2 sides)", 7, 280, T + "hc-sr04-4pin-ultrasonic-sensor-module"),
    ("18650 3.7 V 3200 mAh cell (Good Quality)", 6, 620, T + "18650-flat-top-3-7v-3200ma-li-ion-rechargeable-battery-"),
    ("3S 40 A BMS protection board", 1, 420, T + "li-ion-18650-3s-40a-bms-pcm-battery-protection-board"),
    ("12.6 V 2 A SMPS adapter (charger; the BMS stops the charge)", 1, 850, T + "12-6v-2a-smps-power-adapter"),
    ("XT60 male and female pair (battery plug)", 1, 80, T + "xt60-male-female-bullet-connectors-plugs-for-rc-lipo-ba"),
    ("SPDT rocker switch 15 A 250 V (main power and kill switch)", 1, 30, T + "spdt-black-rectangular-rocker-switch-big-3-pin-250vac-1"),
    ("Glass fuse 10 A, 5 × 20 mm (1 spare)", 2, 4, T + "glass-fuse-230vac-10a-5x20mm"),
    ("Vero dot board 90 × 70 mm (echo dividers, power rail)", 2, 50, T + "vero-dot-board-90x70mm-single-layer-prototype-pcb"),
    ("Jumper wires female to female, 30 cm, strip of 40", 1, 180, T + "long-jumper-wire-female-to-female-1x40-pin-30cm"),
    ("OTG adapter, USB-C male to USB-A female (phone to webcam)", 1, 80, T + "otg-adapter-type-c"),
    ("M3 nylon spacer 5 mm (under the boards)", 12, 2, T + "m3-black-nylon-spacer-h-5mm-id-3mm-od-7mm-standoff-wash"),
    ("Rubber grommet 8 mm (webcam cable through the box floor)", 2, 5, T + "rubber-grommets-8mm"),
]
DUINO = [
    ("130 mm truck wheel, 60 mm wide, 6 mm coupling (blue): <b>not sold in Colombo</b>", 2, 1890, "https://www.duino.lk/product/130mm-truck-wheels-tires-60mm-width/"),
    ("GA/GB 37 mm geared motor mounting bracket: alphatronic is out of stock", 2, 580, "https://www.duino.lk/product/ga-gb-37mm-diameter-dc-geared-motor/"),
]
SHOP = [
    (CH + "Plastic storage box with lid, about 25 L: 400 × 300 footprint (or a little smaller), about 250 high. Holds 3 to 5 food parcels", "1", 1500),
    (NEW + "3\" (75 mm) swivel caster with top plate, about 100 mm high, rated 25 kg or more (hardware shop or Daraz)", "2", 1200),
    (CH + "12 mm plywood, 2 ft × 2 ft (610 × 610): deck, 4 walls, sonar strip, 2 bracket spacers", "1", 1000),
    (CH + "M4 × 40 bolts (brackets, through the spacers), M4 × 30 bolts and nyloc nuts (casters), M4 washers, wood screws 4 × 40 and 4 × 30", "set", 600),
    ("Spot-weld the 6 cells into a 3S2P pack with nickel strip (battery or phone-repair shop)", "1", 500),
    ("Double-sided foam tape and a Velcro strap (ESP32, BMS, battery)", "set", 150),
]
FASTENERS = [
    ("Motor to bracket", "M3 × 6 machine screw", 8, "4 per motor, into the gearbox face"),
    (CH + "Bracket + spacer to deck underside", "M4 × 40 bolt + M4 nut + washer", 8, "through bracket, 12 mm spacer and deck"),
    (CH + "Caster + shim to deck", "M4 × 30 bolt + nyloc nut + 2 washers", 8, "through caster plate, 5 mm shim and deck"),
    ("Walls to deck", "4 × 40 countersunk wood screw", 14, "up through the deck (holes 3–16 on the template)"),
    ("Wall corners", "4 × 30 wood screw + PVA glue", 8, "2 per corner"),
    ("Box floor to wall tops", "4 × 30 wood screw + 25 mm washer", 6, "from inside the box, down into the wall tops"),
    ("Sonar strip to deck front edge", "4 × 30 wood screw", 3, ""),
    ("BTS7960, XL4015 to deck", "M3 × 10 bolt + nut + 5 mm nylon spacer", 12, "bolt through the deck"),
    ("ESP32 and BMS", "double-sided foam tape", "—", ""),
    ("HC-SR04 (7)", "hot glue or 2 × M2 screws each", "—", "wall sensors: board inside, cans through Ø16.5 holes"),
    ("Servo latch", "2 × M2 × 10 + nuts", 2, "rear wall of the box, under the lid lip"),
    ("Webcam bracket", "M3 × 10 + nut, 2 washers", 2, "front face of the box"),
    ("Battery pack", "Velcro strap or 2 cable ties", 1, ""),
    ("Wiring", "cable ties 4 × 150 mm", "20", ""),
]
TOOLS = ["Drill with 3, 4.5, 8 mm bits; 16 mm spade bit or hole saw", "Jigsaw or hand saw; sandpaper", "Screwdrivers, 7 mm and 8 mm spanners",
         "Soldering iron, solder, flux; hot-glue gun", "Multimeter (set the XL4015 to 5.1 V before connecting anything)", "Wire stripper; heat gun or lighter for heat shrink"]

DIMS = [
    (CH + "Deck (plywood)", "400 × 300 × 12", "cut list"),
    (CH + "Electronics walls", "400 × 45 × 12 (2), 276 × 45 × 12 (2)", "cut list"),
    (CH + "Cargo box (body), about 25 L", "400 × 300 × 250, lid 406 × 306 × 15", "pick a box this size or a little smaller"),
    ("Wheel", "Ø130 × 60, 6 mm hub", "listing"),
    ("JGB37-520 motor", "gearbox Ø37 × 26.5, can Ø35.5 × 30.5, encoder Ø34 × 17; shaft Ø6 D, 7 mm off centre", "datasheet, check yours"),
    ("37 mm bracket", "plate 44 × 46, flange 44 × 30, 2.5 thick (modelled)", "measure yours"),
    (CH + "3\" caster", "about 100 high, plate 65 × 50, wheel Ø75 × 24, about 25 mm trail", "typical, measure yours: shim = 105 − caster height"),
    (NEW + "Bracket spacer / caster shim", "44 × 30 × 12 plywood (2) / 65 × 50 × 5 (2)", "cut list / hardboard or washers"),
    ("3S2P pack", "65 × 56 × 37 (6 × 18650 Ø18.4 × 65)", "calculated"),
    ("BMS 3S 40 A", "60 × 45 × 4", "typical"),
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
    ("Echo F-L / F-C / F-R", "GPIO 34 / 35 / 36", "each through 1.5 kΩ (series) + 2.2 kΩ (to GND): 2.97 V"),
    ("Echo S-L / S-R", "GPIO 39 / 27", "divider as above"),
    ("Echo B-L / B-R", "GPIO 14 / 23", "divider as above"),
    ("Servo signal", "GPIO 13", "servo powered from 5 V"),
    ("Status LED", "GPIO 2", "on-board LED"),
    ("Spare", "GPIO 5, 15", ""),
]

STEPS = [
    "Cut the plywood (cut plan). Glue and screw the four walls into a frame, then screw the frame to the deck from below (14 countersunk screws).",
    "Drill the deck: two Ø16 wire holes, the wall-screw holes, then the bracket and caster holes by marking through the parts. Cut the 40 × 15 vent slots and the Ø16.5 sensor holes in the walls, and the 28 × 12.5 switch hole in the rear wall (thin the wall to about 2 mm around it from inside so the clips grip).",
    CH + "Fit the motors to the brackets (shaft at the bottom, 7 mm below the gearbox centre). Put a 44 × 30 plywood spacer on each bracket flange and bolt both under the deck with M4 × 40 bolts, axle 115 mm from the rear edge. Push the wheels on and tighten their grub screws.",
    CH + "Bolt the 3\" casters under the deck with a 5 mm shim each (shim = 105 − caster height), swivel centres 65 mm from the front edge and 90 mm either side of the centre line. Check the deck sits level; change the shims if not.",
    "Have the cells spot-welded as 3S2P, solder the BMS balance leads, and fit the XT60. Charge it once with the 12.6 V adapter, through the BMS.",
    "Set the XL4015 to 5.1 V with the multimeter <b>before</b> connecting anything to it.",
    "Mount the boards (layout drawing). Wire the power path: battery, XT60, fuse, rocker switch, then the BTS7960s and the XL4015. Join all grounds at one point.",
    "Build the 7 echo dividers on perfboard, wire the sensors and the encoders to the ESP32 (pin map), and route the motor and encoder cables up through the Ø16 holes.",
    "Screw the sonar strip to the front edge; glue the front-left and front-right sensors on 30° wedges. Fit the wall sensors from inside.",
    "Put the phone on the foam pad (screen up, at the front), plug in the OTG adapter and lead the webcam cable to the webcam through a small grommet in the box floor.",
    "Screw the box floor down onto the wall tops, mount the webcam (about 316 mm up, tilted 12° down) and the servo latch, and calibrate the phone compass with everything powered.",
]

daraz = sum(q * p for _, q, p, _ in DARAZ)
alpha = sum(q * p for _, q, p, _ in ALPHA)
tronic = sum(q * p for _, q, p, _ in TRONIC)
duino = sum(q * p for _, q, p, _ in DUINO)
shop = sum(p for _, _, p in SHOP)
delivery = 830
total = daraz + alpha + tronic + duino + shop + delivery
n1, n2, n3 = 1 + len(DARAZ), 1 + len(DARAZ) + len(ALPHA), 1 + len(DARAZ) + len(ALPHA) + len(TRONIC)
n4 = n3 + len(DUINO)


def table_buy(rows, start):
    out = ["<table><tr><th>#</th><th>Part</th><th class='n'>Qty</th><th class='n'>Each</th><th class='n'>Total</th><th>Link</th></tr>"]
    for i, (name, q, p, url) in enumerate(rows):
        short = url.split("//")[1].split("/")[0].replace("www.", "")
        out.append(f"<tr class='{'chgrow' if 'chg' in name else ''}'><td>{start + i}</td><td>{name}</td><td class='n'>{q}</td><td class='n'>{rs(p)}</td><td class='n'>{rs(q * p)}</td>"
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
.chg {{ font-size: 6.5pt; background: #d97706; color: white; border-radius: 6px; padding: 0 5px; text-transform: uppercase; font-weight: bold; }}
tr.chgrow td, li.chgrow {{ background: #fff4c2; }}
.revb {{ background: #fff4c2; border-left: 4px solid #d97706; padding: 6px 10px; margin: 6px 0; font-size: 8.4pt; }}
.revb ul {{ margin: 2px 0; }}
.new {{ font-size: 7pt; background: #dbeafe; color: #1e40af; border-radius: 6px; padding: 0 5px; }}
.total td {{ font-weight: bold; font-size: 10pt; border-top: 2px solid #333; }}
.kv td:first-child {{ color: #555; width: 55%; }}
ol {{ padding-left: 18px; margin: 3px 0; }} ol li {{ margin-bottom: 3px; }}
ul {{ padding-left: 16px; margin: 3px 0; }}
pre {{ font-size: 7.6pt; background: #f8fafc; border: 1px solid #ddd; padding: 6px; margin: 4px 0; }}
</style></head><body>

<h1>Delivery Rover: Build Pack</h1>
<p class="sub"><b>Rev B</b> · 3 kg of food (3 to 5 parcels) · the storage box is the whole body · electronics in a closed compartment underneath · phone inside as the brain · 7 ultrasonic sensors · all sizes in mm · 19 Nov 2026</p>
<img class="fig" src="img/render_iso.png" style="width:44%">
<div class="revb"><b>What changed in revision B (19 Nov 2026).</b> Highlighted <span class='chg'>changed</span> / <span class='chg'>new</span> in yellow through this pack.
<ul>
<li>Payload is now 3 kg of food (3 to 5 parcels) instead of 5 kg. Pizza is left for a later add-on.</li>
<li>Box is about 25 L (400 × 300 × 250) instead of 48 L, and the whole rover shrank to match: {O['length']} × {O['width']} × {O['height']} mm (was 549 × 530 × 415). Deck 400 × 300.</li>
<li>Front casters are 3" (75 mm wheels) for uneven tar, instead of the 2.25" ones. A 12 mm plywood spacer under each motor bracket lifts the deck 12 mm to fit them; the 33 mm risers are gone.</li>
<li>Drive axle moved to 115 mm from the rear edge so the taller, shorter rover doesn't tip back easily.</li>
<li>Same motors (JGB37-520 with encoders), drivers, battery, 7 sensors and wiring. The electronics are rearranged to fit the 376 × 276 compartment.</li>
<li>Parts list: box, casters, plywood use and bolt lengths changed; total now about Rs {rs(total)} (was Rs 38,244).</li>
</ul></div>
<div class="grid2">
<table class="kv">
<tr><th colspan="2">Overall</th></tr>
<tr><td>Length × width × height</td><td>{O['length']} × {O['width']} × {O['height']}</td></tr>
<tr><td>Deck (and box footprint)</td><td>400 × 300, top at {O['deck_top']}</td></tr>
<tr><td>Wheelbase (axle to caster swivel)</td><td>{O['wheelbase']}</td></tr>
<tr><td>Track (wheel centres)</td><td>{O['track']}</td></tr>
<tr><td>Ground clearance (under the motors)</td><td>{O['ground_clearance']}</td></tr>
<tr><td>Cargo space inside the box</td><td>about 395 × 295 × 245 (28 L): 6 parcels of 19 × 14 × 7.5 cm</td></tr>
<tr><td>Electronics compartment</td><td>376 × 276 × 45 high</td></tr>
</table>
<table class="kv">
<tr><th colspan="2">Performance (from the model)</th></tr>
<tr><td>Rover mass / with 3 kg of parcels</td><td>{A['mass_rover']} kg / {A['mass_total']} kg</td></tr>
<tr><td>Speed (60 RPM, Ø130 wheels)</td><td>{A['speed']} m/s</td></tr>
<tr><td>Weight on the drive wheels</td><td>{A['drive_share']} %</td></tr>
<tr><td>Torque needed per motor (8% ramp + accel.)</td><td>{A['torque_kgcm']} kg·cm</td></tr>
<tr><td>Static tip angle: forward / back / side</td><td>{A['tip_fwd']}° / {A['tip_back']}° / {A['tip_side']}°</td></tr>
<tr><td>Turning on the spot: swept circle</td><td>Ø{A['spin_diameter']}</td></tr>
<tr><td>Camera height / sees ground from</td><td>{O['camera_height']:.0f} / {A['cam_ground_ahead']} ahead</td></tr>
</table>
</div>
<div class="grid2"><img class="fig" src="img/render_open.png" style="width:80%"><img class="fig" src="img/render_rear.png" style="width:80%"></div>
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
<p class="note">Colombo first: alphatronic.lk and tronic.lk have almost everything. Only the 130 mm wheels and the 37 mm brackets come from duino.lk (Kandy), because no Colombo shop has them in stock. Prices checked on the shop pages on 19 Nov 2026.</p>
<h3>daraz.lk: Rs {rs(daraz)} (delivered)</h3>{table_buy(DARAZ, 1)}
<h3>alphatronic.lk (Colombo): Rs {rs(alpha)}</h3>{table_buy(ALPHA, n1)}
<h3>tronic.lk (Colombo): Rs {rs(tronic)}</h3>{table_buy(TRONIC, n2)}
<h3>duino.lk (Kandy, delivered): Rs {rs(duino)}</h3>{table_buy(DUINO, n3)}
<div class="revb"><b>Removed in rev B:</b> tronic 2.25" casters (2 × Rs 960) and tronic M4 × 20 bolts (8 × Rs 10). The 3" casters are not stocked at tronic or alphatronic, so they are on the hardware-shop list.</div>
<p class="note">ESP32: using your own. Search tronic.lk with Google ("site:tronic.lk ..."): the shop's own search misses items.</p>
<h3>Hardware shop (estimates): about Rs {rs(shop)}</h3>
<table><tr><th>#</th><th>Item</th><th class="n">Qty</th><th class="n">About</th></tr>
{''.join(f"<tr class='{'chgrow' if 'chg' in n else ''}'><td>{n4 + i}</td><td>{n}</td><td class='n'>{q}</td><td class='n'>{rs(p)}</td></tr>" for i, (n, q, p) in enumerate(SHOP))}</table>
<table>
<tr><td>daraz.lk</td><td class="n">{rs(daraz)}</td></tr><tr><td>alphatronic.lk (Colombo)</td><td class="n">{rs(alpha)}</td></tr>
<tr><td>tronic.lk (Colombo)</td><td class="n">{rs(tronic)}</td></tr><tr><td>duino.lk (Kandy)</td><td class="n">{rs(duino)}</td></tr>
<tr><td>Hardware shop (estimate)</td><td class="n">{rs(shop)}</td></tr>
<tr><td>Delivery (duino about 480, Daraz about 350; collect the Colombo orders yourself)</td><td class="n">about {rs(delivery)}</td></tr>
<tr class="total"><td>Total (using your own phone and ESP32)</td><td class="n">≈ Rs {rs(total)}</td></tr></table>
<div class="warn"><b>About Rs {rs(total - 35000)} over the Rs 35,000 budget</b> (was Rs 3,244 over). The motors (Rs 9,818) are the biggest cost. The hardware-shop prices are estimates, so shopping around for the box and casters could close the gap.</div>

<div class="page"></div>
<h2>Fasteners, consumables and tools</h2>
<table><tr><th>Where</th><th>What</th><th class="n">Qty</th><th>Note</th></tr>
{''.join(f"<tr class='{'chgrow' if 'chg' in a else ''}'><td>{a}</td><td>{b}</td><td class='n'>{c}</td><td>{d}</td></tr>" for a, b, c, d in FASTENERS)}</table>
<h3>Tools</h3><ul>{''.join(f"<li>{t}</li>" for t in TOOLS)}</ul>
<h2>Component sizes used in the model</h2>
<table><tr><th>Part</th><th>Size (mm)</th><th>Source</th></tr>
{''.join(f"<tr class='{'chgrow' if 'chg' in a else ''}'><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in DIMS)}</table>

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
<ol>{''.join(f"<li class='{'chgrow' if 'chg' in s else ''}'>{s}</li>" for s in STEPS)}</ol>

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
<div class="warn">At {A['mass_total']} kg loaded, an 8% ramp while speeding up needs about {A['torque_kgcm']} kg·cm per motor, inside the motors' continuous rating (about 4–5 kg·cm). The spare torque helps over cracks and patch edges on uneven tar.</div>
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
