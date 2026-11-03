"""am.py out.kicad_pcb : audio module rev 0.4 placement (2-layer, roomy spacing for hand soldering)."""
import pcbnew, sys, re, math
sys.path.insert(0, '/w/am')
sys.path.insert(0, '/w/am')
from netparse import load
MM = pcbnew.FromMM; V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
FPDIR = '/usr/share/kicad/footprints'
W, H = 41.0, 36.5
nets, pads = load('/w/am/net_carradio_audio_rev04.net')
from netparse import comps
comp = comps('/w/am/net_carradio_audio_rev04.net')
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
# main board: module origin (8.5, 13.0); J23 pin 1 (21.315, 45.115), pin 2 (21.315, 47.655), pin 3 (23.855, 45.115)
TGT = socket_pins((8.5, 13.0), (21.315, 45.115), (21.315, 47.655), (23.855, 45.115))
print('J24 rot', place_header(FP['J24'], TGT)); placed['J24'] = crt(FP['J24'])
c = FP['J24'].GetCourtyard(pcbnew.B_CrtYd)
if c.OutlineCount(): bb = c.BBox(); placed['J24'] = (bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)
FIXED = [('U10', dict(rot=270, cx=9.5, cy=13.0)), ('U11', dict(rot=270, cx=31.0, cy=13.0)),
         ('U8', dict(rot=0, cx=20.25, cy=4.0)), ('U9', dict(rot=0, cx=20.25, cy=21.0))]
for r, kw in FIXED: put_bb(r, **kw)
FIXED.append(('J24', {}))
pin1 = [p for p in FP['J24'].Pads() if p.GetNumber() == '1'][0].GetPosition()
HX, HY = 46.0 - 8.5, 17.0 - 13.0                          # standoff over main board H6
placed['_H'] = (HX - 3.0, HY - 3.0, HX + 3.0, HY + 3.0)
PAS = [r for r in FP if r not in dict(FIXED)]
anchors = set(dict(FIXED))
OWN = {'C18': 'U8', 'C19': 'U8', 'C20': 'U9', 'C21': 'U9'}
OWN.update({f'C{i}': 'U10' for i in range(22, 30)}); OWN.update({f'C{i}': 'U11' for i in range(32, 40)})
def owner(ref):
    if ref in OWN: return OWN[ref]
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
M = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0     # extra gap between courtyards for hand soldering
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
