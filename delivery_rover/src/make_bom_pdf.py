"""Slices the parts list out of docs/delivery_rover_build_pack.html into docs/delivery_rover_BOM.pdf."""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
s = open(os.path.join(DOCS, "delivery_rover_build_pack.html")).read()
head = s[:s.index("<body>") + 6].replace("Delivery Rover Build Pack", "Delivery Rover Parts List")
a = s.index("<h2>Bill of materials")
b = s.index("<h2>Component sizes used in the model</h2>")
body = s[a:b].replace('<div class="page"></div>', '<div class="page"></div>')
html = (head + "<h1>Delivery Rover: Parts List</h1>"
        "<p class='sub'>Rev B: smaller rover for 3 to 5 food parcels · changes highlighted in yellow · Colombo shops first · prices checked 19 Nov 2026 · links are clickable</p>"
        + body + "</body></html>")
out = os.path.join(DOCS, "delivery_rover_BOM.html")
open(out, "w").write(html)
pdf = os.path.join(DOCS, "delivery_rover_BOM.pdf")
subprocess.run(["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser", "--headless", "--disable-gpu", "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}", "file://" + out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
print(pdf, os.path.getsize(pdf))
