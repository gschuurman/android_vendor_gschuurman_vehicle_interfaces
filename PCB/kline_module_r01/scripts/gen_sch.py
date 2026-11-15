import re, uuid, sys
sys.path.insert(0, ".")
from design import *
U = lambda: str(uuid.uuid4())
def block(t, name):
    i = t.index('(symbol "%s"' % name); d = 0
    for j in range(i, len(t)):
        if t[j] == "(": d += 1
        elif t[j] == ")":
            d -= 1
            if d == 0: return t[i:j+1]
L9637 = '''(symbol "L9637D" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
 (property "Reference" "U" (at 0 8.89 0) (effects (font (size 1.27 1.27))))
 (property "Value" "L9637D" (at 0 -8.89 0) (effects (font (size 1.27 1.27))))
 (property "Footprint" "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
 (property "Datasheet" "https://www.st.com/resource/en/datasheet/l9637.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
 (symbol "L9637D_0_1" (rectangle (start -7.62 6.35) (end 7.62 -6.35) (stroke (width 0.254) (type default)) (fill (type background))))
 (symbol "L9637D_1_1"
  (pin passive line (at -10.16 3.81 0) (length 2.54) (name "TX" (effects (font (size 1.27 1.27)))) (number "4" (effects (font (size 1.27 1.27)))))
  (pin passive line (at -10.16 1.27 0) (length 2.54) (name "RX" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
  (pin passive line (at -10.16 -1.27 0) (length 2.54) (name "VCC" (effects (font (size 1.27 1.27)))) (number "3" (effects (font (size 1.27 1.27)))))
  (pin passive line (at -10.16 -3.81 0) (length 2.54) (name "LO" (effects (font (size 1.27 1.27)))) (number "2" (effects (font (size 1.27 1.27)))))
  (pin passive line (at 10.16 3.81 180) (length 2.54) (name "VS" (effects (font (size 1.27 1.27)))) (number "7" (effects (font (size 1.27 1.27)))))
  (pin passive line (at 10.16 1.27 180) (length 2.54) (name "K" (effects (font (size 1.27 1.27)))) (number "6" (effects (font (size 1.27 1.27)))))
  (pin passive line (at 10.16 -1.27 180) (length 2.54) (name "LI" (effects (font (size 1.27 1.27)))) (number "8" (effects (font (size 1.27 1.27)))))
  (pin passive line (at 10.16 -3.81 180) (length 2.54) (name "GND" (effects (font (size 1.27 1.27)))) (number "5" (effects (font (size 1.27 1.27)))))
 )
)'''
syms = {}
def getsym(lib_id):
    if lib_id in syms: return syms[lib_id]
    lib, name = lib_id.split(":")
    if lib == "kline": blk = L9637
    else:
        t = open("/usr/share/kicad/symbols/%s.kicad_sym" % lib).read()
        blk = block(t, name)
        m = re.search(r'\(extends "([^"]+)"\)', blk)
        if m: raise SystemExit("extends " + lib_id)
    pins = {}
    for m in re.finditer(r'\(pin \S+ \S+\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\s*\(length ([-\d.]+)\).*?\(number "([^"]+)"', blk, re.S):
        pins[m.group(5)] = (float(m.group(1)), float(m.group(2)), int(float(m.group(3))))
    blk = blk.replace('(symbol "%s"' % name, '(symbol "%s"' % lib_id, 1)
    syms[lib_id] = (blk, pins); return syms[lib_id]
root = U(); out = []
def label(name, x, y, rot):
    j = "left" if rot in (0, 90) else "right"
    out.append(f'(label "{name}" (at {x} {y} {rot}) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify {j} bottom)) (uuid {U()}))')
def txt(s, x, y, size=1.27):
    s = s.replace('"', "'")
    out.append(f'(text "{s}" (at {x} {y} 0) (effects (font (size {size} {size})) (justify left bottom)) (uuid {U()}))')
def place(ref, lib_id, val, fp, lcsc, x, y, nets):
    blk, pins = getsym(lib_id)
    props = (f'(property "Reference" "{ref}" (at {x} {y-6.35} 0) (effects (font (size 1.27 1.27))))\n'
             f'(property "Value" "{val}" (at {x} {y+6.35} 0) (effects (font (size 1.27 1.27))))\n'
             f'(property "Footprint" "{fp}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n'
             f'(property "Datasheet" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n'
             f'(property "LCSC" "{lcsc}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n')
    pinu = "".join(f'(pin "{n}" (uuid {U()}))' for n in pins)
    out.append(f'(symbol (lib_id "{lib_id}") (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {U()})\n{props}{pinu}\n'
               f'(instances (project "{NAME}" (path "/{root}" (reference "{ref}") (unit 1)))))')
    for n, (px, py, a) in pins.items():
        cx, cy = round(x + px, 2), round(y - py, 2)
        net = nets.get(n)
        if net:
            rot = {0: 180, 180: 0, 90: 270, 270: 90}[a]
            label(net, cx, cy, rot)
        else:
            out.append(f'(no_connect (at {cx} {cy}) (uuid {U()}))')
G = 2.54
# grid placement (mm, on 2.54 grid)
POS = {"J1": (40.64, 63.5), "U1": (101.6, 63.5), "J2": (172.72, 63.5), "C1": (76.2, 88.9), "D2": (147.32, 88.9), "C4": (162.56, 88.9),
       "R1": (182.88, 88.9), "JP1": (198.12, 88.9), "Q1": (50.8, 119.38), "D1": (73.66, 119.38), "R2": (88.9, 119.38), "R3": (104.14, 119.38),
       "Q2": (124.46, 119.38), "R4": (142.24, 119.38), "C2": (162.56, 119.38), "D3": (182.88, 119.38), "R5": (198.12, 119.38), "H1": (220.98, 63.5)}
for ref, sym, val, fpn, x, y, rot, side, padnets, lcsc, mpn, note in PARTS:
    px, py = POS[ref]
    place(ref, sym, val, fpn, lcsc, px, py, padnets)
txt("K-line module rev 0.1 for the car radio main board rev 0.6 (plugs into J10, held by an M2 screw + 11 mm spacer at H8)", 20.32, 25.4, 2.0)
notes = [
 "Car side: J2 pin 1 = K-line (OBD-II socket pin 7, ECU pin per the MG F wiring diagram), pin 2 = GND (OBD-II pin 4/5). Battery comes from J10 pin 7 (F6 on the main board).",
 "U1 L9637D runs VCC from +3V3 (datasheet range 3-7 V), so RX swings 0-3.3 V straight into GPIO33 and TX takes 3.3 V logic (VIH max 2.5 V). RX/TX/LO have internal pull-ups to VCC.",
 "Q1 switches battery to VS and to the 510R ISO 9141 pull-up. GPIO28 low (default, R4) = Q1 off: no parked drain and no 12 V pushed into the ECU K-line with ignition off.",
 "D1 limits Q1 Vgs to 12 V up to the 35.5 V clamp of the main-board TVS. JP1 is bridged: cut it if the ECU already pulls K up and you want the tester-side pull-up gone.",
 "Firmware: GPIO28 high, wait ~10 ms. MEMS 1.9: ISO 9141 5-baud init of address 0x16 bit-banged on GPIO32, then UART0 9600 8N1 (per rovermems.com). L-line not used (LI/LO open, defined by U1).",
]
for i, n in enumerate(notes): txt(n, 20.32, 33.02 + i * 3.6, 1.0)
labels_txt = [("J10 on the main board", 30.48, 55.88), ("to the car (JST XH side entry)", 160.02, 55.88), ("K-line protection and pull-up", 140.97, 78.74), ("K-line power switch (GPIO28) and power LED", 45.72, 106.68)]
for s, x, y in labels_txt: txt(s, x, y, 1.6)
lib = "\n".join(syms[k][0] for k in syms)
sch = f'''(kicad_sch (version 20230121) (generator eeschema)
(uuid {root})
(paper "A4")
(title_block (title "Car radio K-line module (MG F MEMS 1.9)") (date "2026-11-15") (rev "0.1"))
(lib_symbols
{lib}
)
{chr(10).join(out)}
(sheet_instances (path "/" (page "1")))
)
'''
open(NAME + "/" + NAME + ".kicad_sch", "w").write(sch)
print("ok", len(PARTS))
