"""bridge.py in out net sx sy [x0 y0 x1 y1]: route one connection for `net` from the copper island containing (sx, sy) to any
other piece of that net's copper (zone fill, track, via, pad), on F/In1/In2/B with through vias. Grid router on a
0.05 mm raster of other-net copper inflated by clearance + half track width. Adds locked 0.2 mm tracks / 0.45 / 0.3 mm drill vias."""
import pcbnew, sys, heapq, math
import numpy as np
from PIL import Image, ImageDraw
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); out = sys.argv[2]; net = b.FindNet(sys.argv[3]); NC = net.GetNetCode()
sx, sy = float(sys.argv[4]), float(sys.argv[5])
X0, Y0, X1, Y1 = (map(float, sys.argv[6:10]) if len(sys.argv) > 9 else (sx - 8, sy - 8, sx + 8, sy + 8))
R = 0.05; NX, NY = int((X1 - X0) / R) + 1, int((Y1 - Y0) / R) + 1
LAY = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
import os
CL, HW, VR = float(os.environ.get("CL", 0.15)), float(os.environ.get("HW", 0.1)), 0.225
def px(x, y): return ((x - X0) / R, (y - Y0) / R)
def poly_of(shape_poly):
    res = []
    for i in range(shape_poly.OutlineCount()):
        o = shape_poly.Outline(i); res.append([px(T(o.CPoint(k).x), T(o.CPoint(k).y)) for k in range(o.PointCount())])
    return res
def raster(items_polys):
    img = Image.new('1', (NX, NY), 0); d = ImageDraw.Draw(img)
    for pts in items_polys:
        if len(pts) > 2: d.polygon(pts, fill=1)
    return np.array(img, bool)
box = pcbnew.BOX2I(pcbnew.VECTOR2I(MM(X0 - 1), MM(Y0 - 1)), pcbnew.VECTOR2I(MM(X1 - X0 + 2), MM(Y1 - Y0 + 2)))
copper = [t for t in b.GetTracks()] + [p for f in b.GetFootprints() for p in f.Pads()]
copper = [c for c in copper if c.GetBoundingBox().Intersects(box)]
# the full-board GND pours are refilled afterwards, so other nets may route through them
POURS = ('F GND', 'GND plane', 'In2 GND', 'B GND')
ruleareas = [z for z in b.Zones() if z.GetIsRuleArea()]
zones = [z for z in b.Zones() if not z.GetIsRuleArea() and not (NC != z.GetNetCode() and z.GetZoneName() in POURS)]
TIGHT = [float(v) for v in os.environ.get('TIGHT', '').split(',') if v]; CLT = float(os.environ.get('CLT', 0.1))
def item_poly(c, l, inflate):
    sp = pcbnew.SHAPE_POLY_SET(); c.TransformShapeToPolygon(sp, l, MM(inflate), MM(0.005), pcbnew.ERROR_INSIDE); return sp
RIP = os.environ.get('RIP') == '1'
SOFT = int(os.environ.get("SOFT", 300))
blk_t, blk_v, own, soft_t, soft_v = [], [], [], [], []
blk_tT, blk_vT = [], []
holes = [c for c in copper if isinstance(c, pcbnew.PAD) and c.HasHole()]
for l in LAY:
    pt, pv, po, st_, sv_ = [], [], [], [], []
    ptT, pvT = [], []
    for c in copper:
        if not c.IsOnLayer(l): continue
        if c.GetNetCode() == NC: po += poly_of(item_poly(c, l, 0))
        elif RIP and not isinstance(c, pcbnew.PAD) and not c.IsLocked():
            st_ += poly_of(item_poly(c, l, CL + HW)); sv_ += poly_of(item_poly(c, l, CL + VR))
        else:
            pt += poly_of(item_poly(c, l, CL + HW)); pv += poly_of(item_poly(c, l, CL + VR))
            if TIGHT: ptT += poly_of(item_poly(c, l, CLT + HW)); pvT += poly_of(item_poly(c, l, CLT + VR))
    for z in ruleareas:   # keep-outs: no tracks / no vias on this layer
        if not z.IsOnLayer(l): continue
        if z.GetDoNotAllowTracks():
            sp = pcbnew.SHAPE_POLY_SET(z.Outline()); sp.Inflate(MM(HW + 0.03), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005)); pt += poly_of(sp); ptT += poly_of(sp)
        if z.GetDoNotAllowVias():
            sp = pcbnew.SHAPE_POLY_SET(z.Outline()); sp.Inflate(MM(VR + 0.03), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005)); pv += poly_of(sp); pvT += poly_of(sp)
    for z in zones:
        if not z.IsOnLayer(l): continue
        fp = z.GetFilledPolysList(l)
        if z.GetNetCode() == NC: po += poly_of(fp)
        else:
            sp = pcbnew.SHAPE_POLY_SET(fp); sp.Inflate(MM(CL + HW), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005)); pt += poly_of(sp)
            sp = pcbnew.SHAPE_POLY_SET(fp); sp.Inflate(MM(CL + VR), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005)); pv += poly_of(sp)
            if TIGHT:
                sp = pcbnew.SHAPE_POLY_SET(fp); sp.Inflate(MM(CLT + HW), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005)); ptT += poly_of(sp)
                sp = pcbnew.SHAPE_POLY_SET(fp); sp.Inflate(MM(CLT + VR), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005)); pvT += poly_of(sp)
    # board edge
    blk_t.append(raster(pt)); blk_v.append(raster(pv)); own.append(raster(po)); soft_t.append(raster(st_)); soft_v.append(raster(sv_))
    if TIGHT:
        # inside the box (shrunk by the normal clearance so copper just outside still sees CL) use the tight raster
        m = np.zeros((NY, NX), bool); tx0, ty0, tx1, ty1 = TIGHT
        j0, j1 = int(max(0, (tx0 + CL + 0.3 - X0) / R)), int(min(NX, (tx1 - CL - 0.3 - X0) / R)); i0, i1 = int(max(0, (ty0 + CL + 0.3 - Y0) / R)), int(min(NY, (ty1 - CL - 0.3 - Y0) / R))
        m[i0:i1, j0:j1] = True
        blk_t[-1] = np.where(m, raster(ptT), blk_t[-1]); blk_v[-1] = np.where(m, raster(pvT), blk_v[-1])
hv = []
for h in holes: hv += poly_of(item_poly(h, pcbnew.F_Cu, 0.3 + VR))
holeblk = raster(hv)
viablk = np.any(blk_v, axis=0) | holeblk
viasoft = np.any(soft_v, axis=0)
# label own-net copper islands per layer, connected through vias/PTH: flood from start
from scipy import ndimage
lab = [ndimage.label(o)[0] for o in own]
si, sj = int(round((sy - Y0) / R)), int(round((sx - X0) / R))
start_l = [k for k in range(4) if lab[k][si, sj]]
# island = all own pieces reachable from start via same-net vias/PTH pads (through all layers)
thru = [c for c in copper if c.GetNetCode() == NC and (isinstance(c, pcbnew.PCB_VIA) or (isinstance(c, pcbnew.PAD) and c.HasHole()))]
isl = [set() for _ in range(4)]
for k in start_l: isl[k].add(lab[k][si, sj])
changed = True
while changed:
    changed = False
    for c in thru:
        p = c.GetPosition(); i, j = int(round((T(p.y) - Y0) / R)), int(round((T(p.x) - X0) / R))
        if not (0 <= i < NY and 0 <= j < NX): continue
        if any(lab[k][i, j] in isl[k] and lab[k][i, j] for k in range(4)):
            for k in range(4):
                if lab[k][i, j] and lab[k][i, j] not in isl[k]: isl[k].add(lab[k][i, j]); changed = True
src = [np.isin(lab[k], list(isl[k])) & (lab[k] > 0) for k in range(4)]
dst = [(lab[k] > 0) & ~src[k] for k in range(4)]
if os.environ.get('BIGONLY') == '1':   # only the big pieces (the planes), not stray fragments of the same net
    for k in range(4):
        ids, cnt = np.unique(lab[k][dst[k]], return_counts=True)
        if len(cnt): dst[k] = np.isin(lab[k], ids[cnt >= 0.3 * cnt.max()]) & dst[k]
if os.environ.get('DSTLAYERS'):   # e.g. 1 = only finish in the In1 plane
    keep = {int(v) for v in os.environ['DSTLAYERS'].split(',')}
    for k in range(4):
        if k not in keep: dst[k] = np.zeros_like(dst[k])
print('island cells', [int(s.sum()) for s in src], 'target cells', [int(s.sum()) for s in dst])
# Dijkstra from all src cells (free for track) to any dst cell
INF = 1 << 30; dist = np.full((4, NY, NX), INF, np.int32); prev = {}
pq = []
for k in range(4):
    ys, xs = np.nonzero(src[k])
    for i, j in zip(ys, xs): dist[k, i, j] = 0; heapq.heappush(pq, (0, k, i, j))
VC = 60; goal = None
while pq:
    dd, k, i, j = heapq.heappop(pq)
    if dd > dist[k, i, j]: continue
    if dst[k][i, j]: goal = (k, i, j); break
    for di, dj, c in ((0, 1, 10), (1, 0, 10), (0, -1, 10), (-1, 0, 10), (1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14)):
        ni, nj = i + di, j + dj
        if not (0 <= ni < NY and 0 <= nj < NX): continue
        if blk_t[k][ni, nj] and not dst[k][ni, nj] and not src[k][ni, nj]: continue
        nd = dd + c + (SOFT if soft_t[k][ni, nj] and not soft_t[k][i, j] else (30 if soft_t[k][ni, nj] else 0))
        if nd < dist[k, ni, nj]: dist[k, ni, nj] = nd; prev[(k, ni, nj)] = (k, i, j); heapq.heappush(pq, (nd, k, ni, nj))
    if not viablk[i, j]:
        for nk in range(4):
            if nk == k: continue
            nd = dd + VC + (SOFT if viasoft[i, j] else 0)
            if nd < dist[nk, i, j]: dist[nk, i, j] = nd; prev[(nk, i, j)] = (k, i, j); heapq.heappush(pq, (nd, nk, i, j))
if not goal:
    for k in range(4):
        im = np.zeros((NY, NX, 3), np.uint8); im[blk_t[k]] = (200, 0, 0); im[src[k]] = (0, 200, 0); im[dst[k]] = (0, 0, 200); im[(dist[k] < INF) & ~src[k]] = (230, 230, 0)
        Image.fromarray(im).save(f'dbg{k}.png')
    print('no path'); sys.exit(1)
before = {t.m_Uuid.AsString() for t in b.GetTracks()}
path = [goal]
while path[-1] in prev: path.append(prev[path[-1]])
path.reverse()
def XY(i, j): return pcbnew.VECTOR2I(MM(float(X0 + int(j) * R)), MM(float(Y0 + int(i) * R)))
# emit: merge collinear runs per layer, vias at layer changes
segs = 0; vias = 0
run = [path[0]]
def flush(run):
    global segs
    if len(run) < 2: return
    pts = [run[0]]
    for a in range(1, len(run) - 1):
        d1 = (run[a][1] - pts[-1][1], run[a][2] - pts[-1][2]); d2 = (run[a + 1][1] - run[a][1], run[a + 1][2] - run[a][2])
        if (np.sign(d1[0]), np.sign(d1[1])) != (np.sign(d2[0]), np.sign(d2[1])) or d1[0] * d2[1] != d1[1] * d2[0]: pts.append(run[a])
    pts.append(run[-1])
    for a, c in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(XY(a[1], a[2])); t.SetEnd(XY(c[1], c[2])); t.SetWidth(MM(2 * HW)); t.SetLayer(LAY[a[0]])
        t.SetNet(net); t.SetLocked(True); b.Add(t); segs += 1
for a, c in zip(path, path[1:]):
    if a[0] != c[0]:
        flush(run); run = [c]
        v = pcbnew.PCB_VIA(b); v.SetPosition(XY(a[1], a[2])); v.SetWidth(MM(0.45)); v.SetDrill(MM(0.3)); v.SetNet(net); v.SetLocked(True); b.Add(v); vias += 1
    else: run.append(c)
flush(run)
print('path cells', len(path), 'segs', segs, 'vias', vias, 'from', LAY[path[0][0]], 'to layer', b.GetLayerName(LAY[goal[0]]), X0 + goal[2] * R, Y0 + goal[1] * R)
if RIP:
    new = [t for t in b.GetTracks() if t.GetNetCode() == NC and t.IsLocked() and t.m_Uuid.AsString() not in before]
    ripped = 0
    for c in [c for c in b.GetTracks() if c.GetNetCode() != NC and not c.IsLocked() and c.GetBoundingBox().Intersects(box)]:
        hit = False
        for t in new:
            for l in LAY:
                if c.IsOnLayer(l) and t.IsOnLayer(l) and c.GetEffectiveShape(l).Collide(t.GetEffectiveShape(l), MM(0.13)): hit = True; break
            if hit: break
        if hit: b.Remove(c); ripped += 1
    print('ripped', ripped)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(out)
