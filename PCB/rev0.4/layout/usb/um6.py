"""um.py out.kicad_pcb : USB module rev 0.4 placement (2-layer, roomy spacing for hand soldering)."""
import pcbnew, sys, re, math
sys.path.insert(0, '/w/um')
from netparse import load
MM = pcbnew.FromMM; V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
FPDIR = '/usr/share/kicad/footprints'
W, H = 36.0, 55.0
nets, pads = load('/w/um/net_carradio_usb_rev04.net')
from netparse import comps
comp = comps('/w/um/net_carradio_usb_rev04.net')
FPL = {}
for r, c in comp.items():
    lib, nm = c['fp'].split(':'); FPL[r] = pcbnew.FootprintLoad(f'{FPDIR}/{lib}.pretty', nm)
HOLE = pcbnew.FootprintLoad(f'{FPDIR}/MountingHole.pretty', 'MountingHole_2.7mm_M2.5_Pad_Via')
b = pcbnew.BOARD(); b.SetCopperLayerCount(2)
NI = {}
for nm in nets: NI[nm] = pcbnew.NETINFO_ITEM(b, nm); b.Add(NI[nm])
FP = {}
for r, c in comp.items():
    f = FPL[r]; lib, nm = c['fp'].split(':'); f.SetFPID(pcbnew.LIB_ID(lib, nm)); f.SetReference(r); f.SetValue(c['val'])
    f.SetPath(pcbnew.KIID_PATH('/' + c['uuid'])); b.Add(f); FP[r] = f
    for p in f.Pads():
        n = pads[r].get(p.GetNumber())
        if n: p.SetNet(NI[n])
def crt(f):
    c = f.GetCourtyard(pcbnew.F_CrtYd); bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return (bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)
placed = {}
def put_bb(ref, rot=0, left=None, top=None, right=None, bottom=None, cx=None, cy=None):
    f = FP[ref]; f.SetOrientationDegrees(rot); f.SetPosition(V(0, 0)); x0, y0, x1, y1 = crt(f)
    dx = (left - x0) if left is not None else (right - x1) if right is not None else (cx - (x0 + x1) / 2)
    dy = (top - y0) if top is not None else (bottom - y1) if bottom is not None else (cy - (y0 + y1) / 2)
    f.SetPosition(V(dx, dy)); placed[ref] = crt(f)
from hdrmatch import place_header, socket_pins
J = FP['J26']; J.Flip(J.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT); J.SetOrientationDegrees(0); J.SetPosition(V(0, 0))
c = J.GetCourtyard(pcbnew.B_CrtYd).BBox(); J.SetPosition(V(0.8 - c.GetX() / 1e6, 1.0 - c.GetY() / 1e6))
c = FP['J26'].GetCourtyard(pcbnew.B_CrtYd); bb = c.BBox(); placed['J26'] = (bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)
FIXED = [('J17', dict(rot=90, right=W + 0.55, top=1.0)), ('J19', dict(rot=90, right=W + 0.55, top=19.2)), ('J20', dict(rot=90, right=W + 0.55, top=37.4)),
         ('U14', dict(rot=0, cx=14.0, cy=17.0)), ('Y2', dict(rot=0, cx=14.0, cy=23.5)),
         ('U17', dict(rot=0, cx=18.0, cy=29.0)), ('U18', dict(rot=0, cx=18.0, cy=47.5)),
         ('U15', dict(rot=0, cx=9.5, cy=37.0)), ('L4', dict(rot=0, cx=10.8, cy=45.6)), ('U16', dict(rot=0, cx=17.0, cy=38.5))]
for r, kw in FIXED: put_bb(r, **kw)
FIXED.append(('J26', {}))
pin1 = [p for p in FP['J26'].Pads() if p.GetNumber() == '1'][0].GetPosition()
HX, HY = 3.8, 51.2       # standoff, over main board H5
placed['_H'] = (HX - 3.0, HY - 3.0, HX + 3.0, HY + 3.0)
PAS = [r for r in FP if r not in dict(FIXED)]
anchors = set(dict(FIXED))
def owner(ref):
    sc = {}
    for p, nm in pads[ref].items():
        if nm == 'GND': continue
        w = 1.0 / max(1, len(nets[nm]) - 1) ** 1.3
        for r2, _ in nets[nm]:
            if r2 != ref and r2 in anchors: sc[r2] = sc.get(r2, 0) + w
    if not sc:   # RC output caps: follow their resistor
        for p, nm in pads[ref].items():
            for r2, _ in nets.get(nm, []):
                if r2 != ref and r2 in FP and r2[0] == 'R': return r2
    return max(sc, key=sc.get) if sc else None
def target(ref, o):
    pts = []
    for p, nm in pads[ref].items():
        if nm == 'GND': continue
        for q in FP[o].Pads():
            if q.GetNetname() == nm: pts.append((q.GetPosition().x / 1e6, q.GetPosition().y / 1e6))
    if not pts: q = FP[o].GetPosition(); pts = [(q.x / 1e6, q.y / 1e6)]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
M = 0.8     # extra gap between courtyards for hand soldering
def ok(bb, me):
    if bb[0] < 0.8 or bb[1] < 0.8 or bb[2] > W - 0.8 or bb[3] > H - 0.8: return False
    for r, (x0, y0, x1, y1) in placed.items():
        if r != me and bb[0] < x1 + M and bb[2] > x0 - M and bb[1] < y1 + M and bb[3] > y0 - M: return False
    return True
order = sorted(PAS, key=lambda r: (r[0] != 'R', r))     # resistors first so their RC caps can follow them
fail = []
for ref in order:
    o = owner(ref); tx, ty = target(ref, o) if o else (W / 2, H / 2)
    f = FP[ref]; best = None
    for rad in [i * 0.25 for i in range(0, 120)]:
        k = max(1, int(2 * math.pi * rad / 0.5))
        for j in range(k):
            a = 2 * math.pi * j / k
            x, y = round((tx + rad * math.cos(a)) * 4) / 4, round((ty + rad * math.sin(a)) * 4) / 4
            for rot in (0, 90):
                f.SetOrientationDegrees(rot); f.SetPosition(V(x, y))
                if ok(crt(f), ref): best = (x, y, rot); break
            if best: break
        if best: break
    if best: f.SetOrientationDegrees(best[2]); f.SetPosition(V(best[0], best[1])); placed[ref] = crt(f)
    else: fail.append(ref)
print('unplaced', fail)
h = HOLE; h.SetFPID(pcbnew.LIB_ID('MountingHole', 'MountingHole_2.7mm_M2.5_Pad_Via')); h.SetReference('H1'); h.SetValue('M2.5 standoff')
h.SetBoardOnly(True); h.SetExcludedFromBOM(True); h.SetExcludedFromPosFiles(True)
for p in h.Pads(): p.SetNet(NI['GND'])
b.Add(h); h.SetPosition(V(HX, HY))
def seg(p, q):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(*p)); s.SetEnd(V(*q)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
for p, q in [((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))]: seg(p, q)
b.Save(sys.argv[1]); print('saved', 'hole', HX, HY, 'pin1', pin1.x / 1e6, pin1.y / 1e6)
pp = {p.GetNumber(): (round(p.GetPosition().x / 1e6, 3), round(p.GetPosition().y / 1e6, 3)) for p in FP['J26'].Pads()}
print('J26 pins', pp['1'], pp['2'], pp['3'])
for r in sorted(placed): print(r, [round(v, 2) for v in placed[r]])
