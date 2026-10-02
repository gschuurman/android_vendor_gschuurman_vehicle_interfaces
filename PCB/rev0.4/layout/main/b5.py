"""b5.py in out : rev 0.4 main board with three plug-in modules (GNSS, audio, USB).
b4.py in out : rev 0.4 main board from the routed rev 0.3 board. Left half (GNSS, opto, MCU, TPS55288 stage,
loom connectors) keeps its placement and routing; audio parts leave for the module; the right half is re-placed
for a 100 x 100 mm outline with four M3 holes inside the corners."""
import os, pcbnew, sys, json, math, re
sys.path.insert(0, '/w/pcb4')
from netparse import load
MM = pcbnew.FromMM; V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
FPDIR = '/usr/share/kicad/footprints'
W, H = 100.0, 100.0
nets, pads = load('/w/pcb4/net_carradio_peripheral_rev04.net')
from netparse import comps
uuid = {r: c['uuid'] for r, c in comps('/w/pcb4/net_carradio_peripheral_rev04.net').items()}
# footprints to add (load before LoadBoard: SWIG quirk)
NEWFP = {r: pcbnew.FootprintLoad(f'{FPDIR}/Connector_PinSocket_2.54mm.pretty', 'PinSocket_2x10_P2.54mm_Vertical') for r in ('J23', 'J25')}
NEWFP['J27'] = pcbnew.FootprintLoad(f'{FPDIR}/Connector_PinSocket_2.54mm.pretty', 'PinSocket_2x08_P2.54mm_Vertical')
for r in ('R100', 'R101'): NEWFP[r] = pcbnew.FootprintLoad(f'{FPDIR}/Resistor_SMD.pretty', 'R_0603_1608Metric')
NEWFP['JP2'] = pcbnew.FootprintLoad(f'{FPDIR}/Jumper.pretty', 'SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm')
HOLEFP = [pcbnew.FootprintLoad(f'{FPDIR}/MountingHole.pretty', 'MountingHole_3.2mm_M3_Pad_Via') for _ in range(4)] + \
         [pcbnew.FootprintLoad(f'{FPDIR}/MountingHole.pretty', 'MountingHole_2.7mm_M2.5_Pad_Via') for _ in range(3)]
b = pcbnew.LoadBoard(sys.argv[1])
FPS = list(b.GetFootprints()); TR = list(b.GetTracks()); ZS = list(b.Zones()); DR = list(b.GetDrawings())
FP = {f.GetReference(): f for f in FPS}
def netobj(nm):
    n = b.FindNet(nm)
    if n is None: n = pcbnew.NETINFO_ITEM(b, nm); b.Add(n)
    return n
# ---- footprints: drop audio parts and the old tab holes, add J23
old = {}
for f in FPS:
    old[f.GetReference()] = (f.GetPosition().x / 1e6, f.GetPosition().y / 1e6)
    if f.GetReference() not in pads: b.Remove(f)
FP = {r: f for r, f in FP.items() if r in pads}
for ref, f in NEWFP.items():
    lib, nm = comps('/w/pcb4/net_carradio_peripheral_rev04.net')[ref]['fp'].split(':')
    f.SetFPID(pcbnew.LIB_ID(lib, nm)); f.SetReference(ref); f.SetValue({'J23': 'Audio module socket', 'J25': 'USB module socket', 'J27': 'GNSS module socket', 'JP2': 'GNSS RX source', 'R100': '1k', 'R101': '1k'}[ref])
    b.Add(f); FP[ref] = f
for r, f in FP.items():
    f.SetPath(pcbnew.KIID_PATH('/' + uuid[r]))
    for p in f.Pads():
        nm = pads[r].get(p.GetNumber())
        p.SetNet(netobj(nm) if nm else b.FindNet(''))
missing = set(pads) - set(FP); print('missing footprints', missing)
# ---- the TPS55288 stage and loom corner (bottom left) keep placement and copper; everything else is re-placed
OLD = {}
for f in FPS: OLD[f.GetReference()] = (f.GetPosition().x / 1e6, f.GetPosition().y / 1e6)
BLOCK = {r for r in FP if r in OLD and OLD[r][0] < 53 and OLD[r][1] >= 53} - {'J18', 'J5'}
OLDPADS = [(p.GetPosition().x, p.GetPosition().y) for r in ('J18', 'J5') for p in FP[r].Pads()]
MOVE = set(FP) - BLOCK
PAS = [r for r in MOVE if re.match(r'^(R|C|D|F|L|TH)\d', r)]
print('block', len(BLOCK), 'moving', len(MOVE))
def endpoints(t): return [t.GetPosition()] if isinstance(t, pcbnew.PCB_VIA) else [t.GetStart(), t.GetEnd()]
n = 0
for t in TR:
    pts = endpoints(t)
    near = any(abs(p.x - q[0]) < MM(1.2) and abs(p.y - q[1]) < MM(1.2) for p in pts for q in OLDPADS)
    if near or t.GetNetname() not in nets or not all(p.x < MM(53.5) and p.y > MM(50.0) for p in pts):
        b.Remove(t); n += 1
print('ripped', n, 'tracks/vias')
for z in ZS:
    if z.GetZoneName() == 'HDMI reference': b.Remove(z)
# ---- placement
def crt(f):
    c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return (bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)
placed = {r: crt(f) for r, f in FP.items() if r in BLOCK}
for r in MOVE: FP[r].SetPosition(V(150, 150))
def put_bb(ref, rot=0, left=None, top=None, right=None, bottom=None, cx=None, cy=None, raw=None):
    f = FP[ref]
    if raw: f.SetOrientationDegrees(raw[2]); f.SetPosition(V(raw[0], raw[1])); placed[ref] = crt(f); return
    f.SetOrientationDegrees(rot); f.SetPosition(V(0, 0))
    x0, y0, x1, y1 = crt(f)
    dx = (left - x0) if left is not None else (right - x1) if right is not None else (cx - (x0 + x1) / 2)
    dy = (top - y0) if top is not None else (bottom - y1) if bottom is not None else (cy - (y0 + y1) / 2)
    f.SetPosition(V(dx, dy)); placed[ref] = crt(f)
for rot in (90, 270):
    put_bb('J14', rot, right=99.7, top=8.6)
    pl = [p for p in FP['J14'].Pads() if p.GetNumber().isdigit()]
    px = sum(p.GetPosition().x for p in pl) / len(pl) / 1e6
    if px < (placed['J14'][0] + placed['J14'][2]) / 2: break
print('J14 rot', rot)
# modules stacked on top of the main board (module PCB about 11 mm up):
#   GNSS 26.5 x 35 at (0, 19), audio 36.5 x 41 at (27, 13) turned 90 degrees, USB 36 x 55 at (64, 32.5)
def socket_targets(p1, p2, p3, n):
    t = {}
    for k in range(n // 2):
        t[str(2 * k + 1)] = (p1[0] + k * (p3[0] - p1[0]), p1[1] + k * (p3[1] - p1[1]))
        t[str(2 * k + 2)] = (p2[0] + k * (p3[0] - p1[0]), p2[1] + k * (p3[1] - p1[1]))
    return t
def place_socket(ref, tgt):
    f = FP[ref]
    for rot in (0, 90, 180, 270):
        f.SetOrientationDegrees(rot); f.SetPosition(V(0, 0))
        pp = {p.GetNumber(): (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6) for p in f.Pads()}
        dx, dy = tgt['1'][0] - pp['1'][0], tgt['1'][1] - pp['1'][1]
        if all(math.dist((pp[k][0] + dx, pp[k][1] + dy), v) < 0.01 for k, v in tgt.items()):
            f.SetPosition(V(dx, dy)); placed[ref] = crt(f); return rot
    raise SystemExit('no socket orientation for ' + ref)
MODS = json.load(open('/w/lay/modules.json'))
for ref, m in MODS['sockets'].items(): print(ref, 'rot', place_socket(ref, socket_targets(*m['pins'], m['n'])))
FIXED = [('J2', dict(rot=90, left=8.0, top=0.5)), ('J13', dict(rot=180, left=68.4, top=0.5)),
         ('J18', dict(rot=0, left=1.0, top=11.0)), ('J5', dict(rot=0, left=11.0, top=11.4)),
         ('U2', dict(cx=88.0, cy=40.0)), ('U3', dict(cx=88.0, cy=48.0)), ('U4', dict(cx=88.0, cy=56.0)),
         ('U20', dict(cx=41.0, cy=30.0)), ('U21', dict(rot=90, cx=30.0, cy=31.0)), ('Y3', dict(cx=44.0, cy=40.0)), ('U19', dict(cx=50.0, cy=40.0)),
         ('U13', dict(cx=52.5, cy=20.0)), ('Y1', dict(cx=52.0, cy=26.0)), ('JP2', dict(rot=0, cx=13.0, cy=27.4)), ('U6', dict(rot=0, cx=18.0, cy=30.0)),
         ('SW1', dict(rot=0, left=53.2, top=55.5)), ('SW2', dict(rot=0, left=53.2, top=62.0)), ('JP1', dict(rot=0, left=54.0, top=68.5)),
         ('Q2', dict(cx=57.0, cy=76.6)), ('Q3', dict(cx=57.0, cy=81.4)),
         ('J21', dict(rot=0, left=73.0, top=60.0)), ('J10', dict(rot=0, left=77.0, top=62.0)),
         ('J8', dict(rot=90, left=54.6, bottom=99.5)), ('J12', dict(rot=0, left=65.2, bottom=99.5)), ('J7', dict(rot=0, left=78.8, bottom=99.5))]
for ref, kw in FIXED: put_bb(ref, **kw)
# keep a free ring around the RP2350B so its 0.4 mm pins can escape (passives keep RING + M + 0.6 mm away)
RING = float(os.environ.get('RING', '1.2'))
_u = placed['U20']; placed['U20'] = (_u[0] - RING, _u[1] - RING, _u[2] + RING, _u[3] + RING)
HOLES = [(4.5, 4.5), (95.5, 4.5), (4.5, 95.5), (95.5, 95.5)] + [tuple(h) for h in MODS['holes']]   # M2.5 standoffs: USB, audio, GNSS module
for i, (x, y) in enumerate(HOLES):
    placed[f'_H{i}'] = (x - 3.1, y - 3.1, x + 3.1, y + 3.1) if i < 4 else (x - 2.6, y - 2.6, x + 2.6, y + 2.6)
KEEPOUT = [(68.0, 12.0, 94.5, 25.5)]
M = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
def overlaps(bb, me, m=None):
    m = M if m is None else m
    for r, (x0, y0, x1, y1) in placed.items():
        if r == me: continue
        mm = m + (0.6 if r[0] == 'U' else 0)
        if bb[0] < x1 + mm and bb[2] > x0 - mm and bb[1] < y1 + mm and bb[3] > y0 - mm: return r
    for (x0, y0, x1, y1) in KEEPOUT:
        if bb[0] < x1 and bb[2] > x0 and bb[1] < y1 and bb[3] > y0: return 'keepout'
    if bb[0] < 0.4 or bb[1] < 0.4 or bb[2] > W - 0.4 or bb[3] > H - 0.4: return 'edge'
anchors = set(FP) - set(PAS)
def owner(ref):
    sc = {}
    for p, nm in pads[ref].items():
        if nm == 'GND': continue
        w = 1.0 / max(1, len(nets[nm]) - 1) ** 1.3
        for r2, _ in nets[nm]:
            if r2 != ref and r2 in anchors: sc[r2] = sc.get(r2, 0) + w
    return max(sc, key=sc.get) if sc else None
def target(ref, o):
    pts = []
    for p, nm in pads[ref].items():
        if nm == 'GND': continue
        for q in FP[o].Pads():
            if q.GetNetname() == nm: pts.append((q.GetPosition().x / 1e6, q.GetPosition().y / 1e6))
    if not pts: q = FP[o].GetPosition(); pts = [(q.x / 1e6, q.y / 1e6)]
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
fail = []
own = {r: owner(r) for r in PAS}
# MCU (U20) and QSPI flash (U19) passives go on the bottom side, under their pins (Glenn's hand-solder spacing
# leaves no room on top for the RP2350B fan-out)
import os
BOT = {r for r in PAS if own[r] in ('U20', 'U19') and r[0] in 'RC'} if os.environ.get('BOTTOM', '1') == '1' else set()
placed_b = {}
for r, f in FP.items():
    if r in placed and any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in f.Pads()): placed_b[r] = placed[r]
for k, v in placed.items():
    if k.startswith('_H'): placed_b[k] = v
u = FP['U20'].GetPosition(); placed_b['_EP'] = (u.x / 1e6 - 2.2, u.y / 1e6 - 2.2, u.x / 1e6 + 2.2, u.y / 1e6 + 2.2)
def overlaps_b(bb, me):
    for r, (x0, y0, x1, y1) in placed_b.items():
        if r != me and bb[0] < x1 + M and bb[2] > x0 - M and bb[1] < y1 + M and bb[3] > y0 - M: return r
    if bb[0] < 0.4 or bb[1] < 0.4 or bb[2] > W - 0.4 or bb[3] > H - 0.4: return 'edge'
for ref in sorted(BOT):
    f = FP[ref]; f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    tx, ty = target(ref, own[ref]); best = None
    for rad in [i * 0.25 for i in range(0, 200)]:
        k = max(1, int(2 * math.pi * rad / 0.5))
        for j in range(k):
            a = 2 * math.pi * j / k
            x, y = round((tx + rad * math.cos(a)) * 4) / 4, round((ty + rad * math.sin(a)) * 4) / 4
            for rot in (0, 90):
                f.SetOrientationDegrees(rot); f.SetPosition(V(x, y)); bb = crt(f)
                if not overlaps_b(bb, ref): best = (x, y, rot); break
            if best: break
        if best: break
    if best: f.SetOrientationDegrees(best[2]); f.SetPosition(V(best[0], best[1])); placed_b[ref] = crt(f)
    else: fail.append(ref)
print('bottom side', len(BOT), sorted(BOT))
PAS = [r for r in PAS if r not in BOT]
PRIO = {'U20': 1, 'U12': 2, 'U21': 3}
for ref in sorted(PAS, key=lambda r: (PRIO.get(own[r], 9), own[r] or 'zz', r)):
    o = own[ref]; tx, ty = target(ref, o) if o else (60, 60)
    f = FP[ref]; best = None
    for rad in [i * 0.25 for i in range(0, 320)]:
        k = max(1, int(2 * math.pi * rad / 0.5))
        for j in range(k):
            a = 2 * math.pi * j / k
            x, y = round((tx + rad * math.cos(a)) * 4) / 4, round((ty + rad * math.sin(a)) * 4) / 4
            for rot in (0, 90):
                f.SetOrientationDegrees(rot); f.SetPosition(V(x, y)); bb = crt(f)
                if not overlaps(bb, ref): best = (x, y, rot); break
            if best: break
        if best: break
    if best: f.SetOrientationDegrees(best[2]); f.SetPosition(V(best[0], best[1])); placed[ref] = crt(f)
    else: fail.append(ref)
print('owners', own); print('unplaced', fail)
for ref in fail:
    f = FP[ref]; f.SetOrientationDegrees(0); f.SetPosition(V(80, 82)); bb = crt(f); print("DBG", ref, own[ref], target(ref, own[ref]) if own[ref] else None, [round(v,2) for v in bb], overlaps(bb, ref))
# ---- holes, outline, pours
for d in DR:
    if d.GetLayer() == pcbnew.Edge_Cuts: b.Remove(d)
for f in list(b.GetFootprints()):
    if f.GetReference().startswith('H') and f.GetReference()[1:].isdigit(): b.Remove(f)
gnd = b.FindNet('GND')
for i, (x, y) in enumerate(HOLES):
    h = HOLEFP[i]; nm = 'MountingHole_3.2mm_M3_Pad_Via' if i < 4 else 'MountingHole_2.7mm_M2.5_Pad_Via'
    h.SetFPID(pcbnew.LIB_ID('MountingHole', nm)); h.SetReference(f'H{i+1}'); h.SetValue('M3' if i < 4 else ['M2.5 standoff, USB module', 'M2.5 standoff, audio module', 'M2.5 standoff, GNSS module'][i - 4])
    h.SetBoardOnly(True); h.SetExcludedFromBOM(True); h.SetExcludedFromPosFiles(True)
    for p in h.Pads(): p.SetNet(gnd)
    h.Reference().SetVisible(False); b.Add(h); h.SetPosition(V(x, y))
def seg(p, q):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(*p)); s.SetEnd(V(*q)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
R = 2.0
for p, q in [((R, 0), (W - R, 0)), ((W, R), (W, H - R)), ((W - R, H), (R, H)), ((0, H - R), (0, R))]: seg(p, q)
for cx, cy, a0 in [(R, R, 180), (W - R, R, 270), (W - R, H - R, 0), (R, H - R, 90)]:
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetCenter(V(cx, cy))
    s.SetStart(V(cx + R * math.cos(math.radians(a0)), cy + R * math.sin(math.radians(a0))))
    s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
e = 0.3
for z in ZS:
    if z.GetNetname() == 'GND' and z.GetZoneName() in ('F GND', 'In2 GND', 'B GND', 'GND plane'):
        o = z.Outline(); o.RemoveAllContours(); o.NewOutline()
        for p in [(e, e), (W - e, e), (W - e, H - e), (e, H - e)]: o.Append(MM(p[0]), MM(p[1]))
json.dump({r: [round(v, 2) for v in bb] for r, bb in list(placed.items()) + [('B:' + k, v) for k, v in placed_b.items()]}, open('/w/lay/placed5.json', 'w'))
b.Save(sys.argv[2]); print('saved')
