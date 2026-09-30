"""Build the rev 0.3 board: footprints + nets from the netlist, floorplan, passives auto-placed near their IC.
Runs inside the KiCad 10 container (pcbnew 10). Coordinates in mm, origin = board top-left, y down."""
import pcbnew, sys, json, math, re
sys.path.insert(0, '/w/pcb')
from sexp import parse
from floorplan import W, H, FIXED, KEEPOUT, HOLES

FPDIR = '/usr/share/kicad/footprints'
MM = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))

net = parse(open('/w/pcb/net_03.net').read())[0]
def get(x, k): return [e for e in x if isinstance(e, list) and e and e[0] == k]
comps = {}
for c in get(get(net, 'components')[0], 'comp'):
    ref = get(c, 'ref')[0][1]
    fp = get(c, 'footprint'); fp = fp[0][1] if fp else ''
    props = {get(p, 'name')[0][1]: (get(p, 'value')[0][1] if get(p, 'value') else '') for p in get(c, 'property')}
    comps[ref] = dict(value=get(c, 'value')[0][1], fp=fp, uuid=get(c, 'tstamps')[0][1], props=props)
nets = {}
for n in get(get(net, 'nets')[0], 'net'):
    nm = get(n, 'name')[0][1]
    nets[nm] = [(get(nd, 'ref')[0][1], get(nd, 'pin')[0][1]) for nd in get(n, 'node')]

# placeholders for parts whose real footprint comes from the LCSC library (easyeda2kicad)
PLACEHOLDER = {}

board = pcbnew.BOARD()
board.SetCopperLayerCount(4)
ds = board.GetDesignSettings()

netinfo = {}
for nm in nets:
    ni = pcbnew.NETINFO_ITEM(board, nm); board.Add(ni); netinfo[nm] = ni
padnet = {}
for nm, nodes in nets.items():
    for r, p in nodes: padnet[(r, p)] = nm

fps = {}
for ref, c in comps.items():
    fpname = c['fp'] or PLACEHOLDER.get(ref, '')
    lib, name = fpname.split(':')
    f = pcbnew.FootprintLoad('/w/pcb/carradio.pretty' if lib == 'carradio' else f'{FPDIR}/{lib}.pretty', name)
    f.SetFPID(pcbnew.LIB_ID(lib, name))
    f.SetReference(ref); f.SetValue(c['value'])
    f.SetPath(pcbnew.KIID_PATH('/' + c['uuid']))
    for k in ('LCSC', 'MPN'):
        if c['props'].get(k): f.SetField(k, c['props'][k]) if hasattr(f, 'SetField') else None
    for pad in f.Pads():
        nm = padnet.get((ref, pad.GetNumber()))
        if nm: pad.SetNet(netinfo[nm])
    board.Add(f); fps[ref] = f
    nums = {p.GetNumber() for p in f.Pads()}
    for (r, pn), nm in padnet.items():
        if r == ref and pn not in nums: print('PIN WITHOUT PAD', ref, pn, nm)
    for p in f.Pads():
        if p.GetNumber() and not p.GetNetname() and not p.IsNPTH() if hasattr(p,'IsNPTH') else False: print('PAD WITHOUT NET', ref, p.GetNumber())

# ---------------------------------------------------------------- geometry helpers
def crt_bbox(f):
    c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return (bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)

placed = []   # (ref, x0,y0,x1,y1)
def put(ref, x, y, rot=0, flip=False):
    f = fps[ref]
    f.SetOrientationDegrees(rot)
    f.SetPosition(V(x, y))
    if flip and not f.IsFlipped(): f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM if hasattr(pcbnew, 'FLIP_DIRECTION_TOP_BOTTOM') else False)
    placed.append((ref,) + crt_bbox(f))

def put_bb(ref, rot=0, left=None, top=None, right=None, bottom=None, cx=None, cy=None):
    """Place so the courtyard's edge/centre lands on the given coordinate."""
    f = fps[ref]; f.SetOrientationDegrees(rot); f.SetPosition(V(0, 0))
    x0, y0, x1, y1 = crt_bbox(f)
    dx = (left - x0) if left is not None else (right - x1) if right is not None else (cx - (x0 + x1) / 2)
    dy = (top - y0) if top is not None else (bottom - y1) if bottom is not None else (cy - (y0 + y1) / 2)
    put(ref, dx, dy, rot)

HALO = {'U20': 1.2, 'U13': 0.8, 'U14': 0.8, 'U10': 0.6, 'U11': 0.6, 'U12': 0.6, 'U21': 0.6, 'U7': 0.6, 'U15': 0.5, 'U16': 0.5}
def overlaps(b, m=0.45):
    for r, x0, y0, x1, y1 in placed:
        mm = m + HALO.get(r, 0)
        if b[0] < x1 + mm and b[2] > x0 - mm and b[1] < y1 + mm and b[3] > y0 - mm: return r
    for (x0, y0, x1, y1) in KEEPOUT:
        if b[0] < x1 and b[2] > x0 and b[1] < y1 and b[3] > y0: return 'keepout'
    if b[0] < 0.4 or b[1] < 0.4 or b[2] > W - 0.4 or b[3] > H - 0.4: return 'edge'
    return None

for spec in FIXED:
    ref, kw = spec[0], dict(spec[1])
    if 'raw' in kw: put(ref, *kw['raw'])
    else: put_bb(ref, **kw)

# ---------------------------------------------------------------- passives near their owner
PASSIVE = re.compile(r'^(R|C|D|F|L|TH|FB)\d')
BIGPASSIVE = {'L3', 'L4', 'C48', 'C60', 'D14', 'D2', 'D5', 'D13', 'R74', 'F4', 'L1'}
fixed_refs = {s[0] for s in FIXED}
passives = [r for r in comps if PASSIVE.match(r) and r not in fixed_refs]
anchors = [r for r in comps if r not in passives]
rails = {'GND'}
def weight(nm):
    if nm in rails: return 0
    return 1.0 / max(1, len(nets[nm]) - 1) ** 1.3

def owner(ref):
    score = {}
    for pad in fps[ref].Pads():
        nm = padnet.get((ref, pad.GetNumber()))
        if not nm or nm in rails: continue
        for r, p in nets[nm]:
            if r != ref and r in anchors: score[r] = score.get(r, 0) + weight(nm)
    # second order: through other passives (e.g. divider chains)
    if not score:
        for pad in fps[ref].Pads():
            nm = padnet.get((ref, pad.GetNumber()))
            if not nm or nm in rails: continue
            for r, p in nets[nm]:
                if r != ref and r in passives:
                    for pad2 in fps[r].Pads():
                        nm2 = padnet.get((r, pad2.GetNumber()))
                        if nm2 and nm2 not in rails:
                            for r2, _ in nets[nm2]:
                                if r2 in anchors: score[r2] = score.get(r2, 0) + 0.3 * weight(nm2)
    return max(score, key=score.get) if score else None

def target(ref, own):
    """Point to aim for: owner pads on the passive's nets."""
    pts = []
    for pad in fps[ref].Pads():
        nm = padnet.get((ref, pad.GetNumber()))
        if not nm or nm in rails: continue
        for p2 in fps[own].Pads():
            if p2.GetNetname() == nm:
                q = p2.GetPosition(); pts.append((q.x / 1e6, q.y / 1e6))
    if not pts:
        q = fps[own].GetPosition(); pts = [(q.x / 1e6, q.y / 1e6)]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))

own = {r: owner(r) for r in passives}
order = sorted(passives, key=lambda r: (own[r] or 'zz', -len([1 for p in fps[r].Pads()]), r))
# place bigger passives first
order.sort(key=lambda r: 0 if r in BIGPASSIVE else 1)
fail = []
for ref in order:
    o = own[ref]
    tx, ty = target(ref, o) if o else (W / 2, H / 2)
    f = fps[ref]
    best = None
    for rad in [i * 0.25 for i in range(0, 160)]:
        n = max(1, int(2 * math.pi * rad / 0.5))
        for k in range(n):
            a = 2 * math.pi * k / n
            x, y = tx + rad * math.cos(a), ty + rad * math.sin(a)
            x, y = round(x * 4) / 4, round(y * 4) / 4
            for rot in (0, 90):
                f.SetOrientationDegrees(rot); f.SetPosition(V(x, y))
                b = crt_bbox(f)
                if not overlaps(b):
                    best = (x, y, rot); break
            if best: break
        if best: break
    if best:
        put(ref, *best)
    else:
        fail.append(ref)
print('owners sample', {k: own[k] for k in list(own)[:10]})
print('unplaced', fail)

# ---------------------------------------------------------------- outline, holes
def seg(x0, y0, x1, y1):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(V(x0, y0)); s.SetEnd(V(x1, y1)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
R = 2.0
pts = [(R, 0, W - R, 0), (W, R, W, H - R), (W - R, H, R, H), (0, H - R, 0, R)]
for p in pts: seg(*p)
for cx, cy, a0 in [(R, R, 180), (W - R, R, 270), (W - R, H - R, 0), (R, H - R, 90)]:
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(V(cx, cy)); s.SetStart(V(cx + R * math.cos(math.radians(a0)), cy + R * math.sin(math.radians(a0))))
    s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True)
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
for i, (x, y) in enumerate(HOLES):
    h = pcbnew.FootprintLoad(f'{FPDIR}/MountingHole.pretty', 'MountingHole_3.2mm_M3_Pad_Via')
    h.SetReference(f'H{i+1}'); h.SetValue('M3'); h.SetPosition(V(x, y))
    h.SetBoardOnly(True); h.SetExcludedFromBOM(True); h.SetExcludedFromPosFiles(True)
    for pad in h.Pads(): pad.SetNet(netinfo['GND'])
    board.Add(h)

json.dump({r: [round(v, 2) for v in b] for r, *b in placed}, open('/w/lay/placed.json', 'w'))
json.dump(own, open('/w/lay/owners.json', 'w'))
board.Save('/w/lay/board_placed.kicad_pcb')
print('saved', len(placed), 'placed of', len(comps))
