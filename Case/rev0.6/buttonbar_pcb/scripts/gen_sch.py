import re, uuid, sys
sys.path.insert(0, ".")
from design import *
U = lambda: str(uuid.uuid4())
def extract(lib, name):
    t = open("/usr/share/kicad/symbols/%s.kicad_sym" % lib).read()
    i = t.index('(symbol "%s"' % name); d = 0
    for j in range(i, len(t)):
        if t[j] == "(": d += 1
        elif t[j] == ")":
            d -= 1
            if d == 0: break
    blk = t[i:j+1]
    if "(extends" in blk: raise SystemExit("extends " + name)
    pins = {}
    for m in re.finditer(r'\(pin \S+ \S+\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\s*\(length ([-\d.]+)\).*?\(number "([^"]+)"', blk, re.S):
        pins[m.group(5)] = (float(m.group(1)), float(m.group(2)))
    return blk.replace('(symbol "%s"' % name, '(symbol "%s:%s"' % (lib, name), 1), pins
syms = {k: extract(*k.split(":")) for k in ["Switch:SW_Push", "Device:D_Schottky", "Connector_Generic:Conn_01x05"]}
root = U(); out = []
def sym(lib_id, ref, val, x, y, fp, rot=0):
    blk, pins = syms[lib_id]; su = U()
    props = (f'(property "Reference" "{ref}" (at {x} {y-3.5} 0) (effects (font (size 1.27 1.27))))\n'
             f'(property "Value" "{val}" (at {x} {y+3.5} 0) (effects (font (size 1.27 1.27))))\n'
             f'(property "Footprint" "{fp}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n'
             f'(property "Datasheet" "" (at {x} {y} 0) (effects (font (size 1.27 1.27)) hide))\n')
    pinu = "".join(f'(pin "{n}" (uuid {U()}))' for n in pins)
    out.append(f'(symbol (lib_id "{lib_id}") (at {x} {y} {rot}) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {su})\n{props}{pinu}\n'
               f'(instances (project "buttonbar" (path "/{root}" (reference "{ref}") (unit 1)))))')
    res = {}
    for n, (px, py) in pins.items():
        if rot == 0: res[n] = (round(x + px, 2), round(y - py, 2))
        elif rot == 180: res[n] = (round(x - px, 2), round(y + py, 2))
    return res
def label(name, x, y, rot=0):
    out.append(f'(label "{name.lstrip("/")}" (at {x} {y} {rot}) (fields_autoplaced) (effects (font (size 1.27 1.27)) (justify {"left" if rot==0 else "right"} bottom)) (uuid {U()}))')
def gnd_label(x, y, rot=0): label("GND", x, y, rot)
def txt(s, x, y, size=1.5):
    out.append(f'(text "{s}" (at {x} {y} 0) (effects (font (size {size} {size})) (justify left bottom)) (uuid {U()}))')
G = 2.54
txt("Button bar strip for the rev 0.6 case: 9 buttons on J12 only (diode-coded)", 20.32, 20.32, 2.0)
txt("Single-line buttons pull one J12 line to GND. Combo buttons pull two lines low through BAT85 Schottky diodes", 20.32, 25.4, 1.4)
txt("(1N4148 is too high with the 1k series + 10k pull-up on the main board). Firmware decodes the 4-line pattern after ~30 ms.", 20.32, 29.21, 1.4)
y0 = 43.18
dl = {d[4]: [] for d in diodes()}
for d in diodes(): dl[d[4]].append(d)
for i, (ref, lab, x, ls) in enumerate(BTNS):
    yy = y0 + i * 12.7; sx = 50.8
    p = sym("Switch:SW_Push", ref, lab, sx, yy, "buttonbar:SW_Tactile_6x3.5mm_2pin_P5.08mm")
    gnd_label(p["1"][0], p["1"][1], 180)
    if len(ls) == 1:
        label(LINES[ls], p["2"][0], p["2"][1])
    else:
        label(node(ref), p["2"][0], p["2"][1])
        for k, dd in enumerate(dl[node(ref)]):
            dx = 88.9 + k * 30.48; dy = yy
            q = sym("Device:D_Schottky", dd[0], "BAT85", dx, dy, "buttonbar:D_DO-34_SOD68_P7.62mm_Horizontal")
            label(node(ref), q["1"][0], q["1"][1], 180)
            label(dd[3], q["2"][0], q["2"][1])
    txt(f"{lab}: lines {' + '.join(ls)}", 142.24, yy + 0.6, 1.27)
j = sym("Connector_Generic:Conn_01x05", "J1", "to main board J12", 195.58, 71.12, "buttonbar:PinHeader_1x05_P2.54mm_Vertical", 180)
for n, p in J1_PINS and enumerate(J1_PINS, 1):
    pass
for i, l in enumerate(J1_PINS, 1):
    x, y = j[str(i)]
    if l == "GND": gnd_label(x, y)
    else: label(LINES[l], x, y)
txt("J12 on main board rev 0.6: 1 S=GPIO18 (screen off), 2 U=GPIO17 (vol+), 3 D=GPIO22 (vol-), 4 M=GPIO16 (mute), 5 GND", 160.02, 88.9, 1.27)
lib = "\n".join(v[0] for v in syms.values())
sch = (f'(kicad_sch (version 20230121) (generator eeschema)\n(uuid {root})\n(paper "A4")\n'
       f'(title_block (title "Button bar strip") (date "2026-11-04") (rev "1") (comment 1 "Case rev 0.6, front button bar"))\n'
       f'(lib_symbols\n{lib}\n)\n' + "\n".join(out) +
       f'\n(sheet_instances (path "/" (page "1")))\n)\n')
open("buttonbar/buttonbar.kicad_sch", "w").write(sch); print("ok", len(out))
