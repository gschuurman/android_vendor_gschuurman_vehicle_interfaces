"""pairroute.py in out netP netN sx sy ex ey [x0 y0 x1 y1]: route an edge-coupled differential pair on F.Cu (over the In1
GND plane). A centreline is grid-routed from (sx, sy) to (ex, ey) on a 0.05 mm raster of other-net copper inflated by
clearance + half the pair width, then offset to two W-wide traces with gap G. Each trace end is joined to the nearest
pad of its net with a straight stub. Unlocked other-net copper the pair crosses is ripped (cost SOFT per crossing);
GND pours are refilled afterwards. Tracks are locked. Env: W (0.30), G (0.15), CL (0.15), SOFT (400);
SWAPSTART = net: that net's stub at the start end runs on B.Cu (with a via) under the other one, for pins in mirrored
order at the two ends (the start pads must be through-hole). PRE = 'x,y' and POST = 'x,y[;x,y...]' add straight lead-ins before the start / after the end, so the pair meets the pins square."""
import pcbnew, sys, os, heapq, math
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import LineString
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); out = sys.argv[2]
NP, NN = b.FindNet(sys.argv[3]), b.FindNet(sys.argv[4]); OWN = {NP.GetNetCode(), NN.GetNetCode()}
sx, sy, ex, ey = map(float, sys.argv[5:9])
X0, Y0, X1, Y1 = (map(float, sys.argv[9:13]) if len(sys.argv) > 12 else (min(sx, ex) - 6, min(sy, ey) - 6, max(sx, ex) + 6, max(sy, ey) + 6))
W, G, CL, SOFT = float(os.environ.get('W', 0.30)), float(os.environ.get('G', 0.15)), float(os.environ.get('CL', 0.15)), int(os.environ.get('SOFT', 400))
HALF = W + G / 2   # centreline to outer trace edge
R = 0.05; NX, NY = int((X1 - X0) / R) + 1, int((Y1 - Y0) / R) + 1
POURS = ('F GND', 'GND plane', 'In2 GND', 'B GND')
def px(x, y): return ((x - X0) / R, (y - Y0) / R)
def polys(sp):
    res = []
    for i in range(sp.OutlineCount()):
        o = sp.Outline(i); res.append([px(T(o.CPoint(k).x), T(o.CPoint(k).y)) for k in range(o.PointCount())])
    return res
def raster(pl):
    img = Image.new('1', (NX, NY), 0); d = ImageDraw.Draw(img)
    for p in pl:
        if len(p) > 2: d.polygon(p, fill=1)
    return np.array(img, bool)
box = pcbnew.BOX2I(pcbnew.VECTOR2I(MM(X0 - 1), MM(Y0 - 1)), pcbnew.VECTOR2I(MM(X1 - X0 + 2), MM(Y1 - Y0 + 2)))
items = [t for t in b.GetTracks()] + [p for f in b.GetFootprints() for p in f.Pads()]
items = [c for c in items if c.GetBoundingBox().Intersects(box) and c.GetNetCode() not in OWN and c.IsOnLayer(pcbnew.F_Cu)]
hard, soft = [], []
INF = CL + HALF + 0.03
for c in items:
    sp = pcbnew.SHAPE_POLY_SET(); c.TransformShapeToPolygon(sp, pcbnew.F_Cu, MM(INF), MM(0.005), pcbnew.ERROR_INSIDE)
    (soft if (not isinstance(c, pcbnew.PAD) and not c.IsLocked()) else hard).extend(polys(sp))
for z in b.Zones():
    if z.GetIsRuleArea() or not z.IsOnLayer(pcbnew.F_Cu) or z.GetZoneName() in POURS or z.GetNetCode() in OWN: continue
    sp = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(pcbnew.F_Cu)); sp.Inflate(MM(INF), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MM(0.005)); hard.extend(polys(sp))
# board edge
eb = b.GetBoardEdgesBoundingBox(); edge = np.ones((NY, NX), bool)
i0, i1 = int(max(0, (T(eb.GetY()) + 0.3 + HALF - Y0) / R)), int(min(NY, (T(eb.GetBottom()) - 0.3 - HALF - Y0) / R))
j0, j1 = int(max(0, (T(eb.GetX()) + 0.3 + HALF - X0) / R)), int(min(NX, (T(eb.GetRight()) - 0.3 - HALF - X0) / R))
edge[i0:i1, j0:j1] = False
HB, SB = raster(hard) | edge, raster(soft)
si, sj = int(round((sy - Y0) / R)), int(round((sx - X0) / R)); gi, gj = int(round((ey - Y0) / R)), int(round((ex - X0) / R))
HB[si, sj] = HB[gi, gj] = False
dist = np.full((NY, NX), 1 << 30, np.int64); prev = {}; pq = [(0, si, sj)]; dist[si, sj] = 0
DIRS = ((0, 1, 10), (1, 0, 10), (0, -1, 10), (-1, 0, 10), (1, 1, 14), (1, -1, 14), (-1, 1, 14), (-1, -1, 14))
while pq:
    dd, i, j = heapq.heappop(pq)
    if dd > dist[i, j]: continue
    if (i, j) == (gi, gj): break
    pdir = prev.get((i, j), (None, None))[1]
    for di, dj, c in DIRS:
        ni, nj = i + di, j + dj
        if not (0 <= ni < NY and 0 <= nj < NX) or HB[ni, nj]: continue
        nd = dd + c + (SOFT if SB[ni, nj] and not SB[i, j] else (20 if SB[ni, nj] else 0)) + (6 if pdir and pdir != (di, dj) else 0)
        if nd < dist[ni, nj]: dist[ni, nj] = nd; prev[(ni, nj)] = ((i, j), (di, dj)); heapq.heappush(pq, (nd, ni, nj))
if (gi, gj) not in prev:
    im = np.zeros((NY, NX, 3), np.uint8); im[HB] = (200, 0, 0); im[SB & ~HB] = (120, 60, 0); im[dist < (1 << 30)] = (0, 160, 0)
    im[max(0, si - 3):si + 4, max(0, sj - 3):sj + 4] = (255, 255, 255); im[max(0, gi - 3):gi + 4, max(0, gj - 3):gj + 4] = (0, 200, 255)
    Image.fromarray(im).save('pair_dbg.png'); print('no path (pair_dbg.png)'); sys.exit(1)
path = [(gi, gj)]
while path[-1] in prev: path.append(prev[path[-1]][0])
path.reverse()
pts = [path[0]]
for a in range(1, len(path) - 1):
    d1 = (path[a][0] - path[a - 1][0], path[a][1] - path[a - 1][1]); d2 = (path[a + 1][0] - path[a][0], path[a + 1][1] - path[a][1])
    if d1 != d2: pts.append(path[a])
pts.append(path[-1])
cl = [(X0 + j * R, Y0 + i * R) for i, j in pts]
if os.environ.get('PRE'): cl = [tuple(map(float, os.environ['PRE'].split(',')))] + cl
if os.environ.get('POST'): cl = cl + [tuple(map(float, q.split(','))) for q in os.environ['POST'].split(';')]
centre = LineString(cl).simplify(0.02)
off = W / 2 + G / 2
sides = [centre.offset_curve(off, join_style=2, mitre_limit=3.0), centre.offset_curve(-off, join_style=2, mitre_limit=3.0)]
def pads_of(net): return [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetCode() == net.GetNetCode()]
def P(x, y): return pcbnew.VECTOR2I(MM(float(x)), MM(float(y)))
# give each offset line to the net whose pads are nearest its two ends
def cost(line, net):
    ps = [(T(p.GetPosition().x), T(p.GetPosition().y)) for p in pads_of(net)]
    c = list(line.coords); ends = (c[-1],) if os.environ.get('SWAPSTART') else (c[0], c[-1])
    return sum(min(math.dist(e, q) for q in ps) for e in ends)
if cost(sides[0], NP) + cost(sides[1], NN) > cost(sides[0], NN) + cost(sides[1], NP): sides.reverse()
before = {t.m_Uuid.AsString() for t in b.GetTracks()}
lens = []
for line, net in zip(sides, (NP, NN)):
    c = list(line.coords); L = line.length
    for a, d in zip(c, c[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*d)); t.SetWidth(MM(W)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net); t.SetLocked(True); b.Add(t)
    for k, e in enumerate((c[0], c[-1])):
        q = min(pads_of(net), key=lambda p: math.dist(e, (T(p.GetPosition().x), T(p.GetPosition().y))))
        lay = pcbnew.F_Cu
        if k == 0 and net.GetNetname() == os.environ.get('SWAPSTART'):
            # via 0.6 mm outboard of the trace end (away from the partner), F.Cu jog to it, B.Cu stub under the partner
            o = [list(l.coords)[0] for l in sides if l is not line][0]; dx, dy = e[0] - o[0], e[1] - o[1]; dl = math.hypot(dx, dy)
            vp = (e[0] + 0.6 * dx / dl, e[1] + 0.6 * dy / dl)
            t = pcbnew.PCB_TRACK(b); t.SetStart(P(*e)); t.SetEnd(P(*vp)); t.SetWidth(MM(W)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net); t.SetLocked(True); b.Add(t)
            v = pcbnew.PCB_VIA(b); v.SetPosition(P(*vp)); v.SetWidth(MM(0.45)); v.SetDrill(MM(0.2)); v.SetNet(net); v.SetLocked(True); b.Add(v)
            L += 0.6; e = vp; lay = pcbnew.B_Cu
        elif k == 0 and os.environ.get('SWAPSTART'):
            # the partner continues 0.5 mm straight out of the pair before turning to its pin, clear of the swap via
            c1 = c[1]; dx, dy = e[0] - c1[0], e[1] - c1[1]; dl = math.hypot(dx, dy); ep = (e[0] + 0.5 * dx / dl, e[1] + 0.5 * dy / dl)
            t = pcbnew.PCB_TRACK(b); t.SetStart(P(*e)); t.SetEnd(P(*ep)); t.SetWidth(MM(W)); t.SetLayer(pcbnew.F_Cu); t.SetNet(net); t.SetLocked(True); b.Add(t)
            L += 0.5; e = ep
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(*e)); t.SetEnd(q.GetPosition()); t.SetWidth(MM(W)); t.SetLayer(lay); t.SetNet(net); t.SetLocked(True); b.Add(t)
        L += math.dist(e, (T(q.GetPosition().x), T(q.GetPosition().y)))
    lens.append(L)
new = [t for t in b.GetTracks() if t.GetNetCode() in OWN and t.m_Uuid.AsString() not in before]
gone = []; ripped = 0
for c in [c for c in b.GetTracks() if c.GetNetCode() not in OWN and not c.IsLocked() and c.IsOnLayer(pcbnew.F_Cu)]:
    if any(c.GetEffectiveShape(pcbnew.F_Cu).Collide(t.GetEffectiveShape(pcbnew.F_Cu), MM(CL)) for t in new):
        b.Remove(c); gone.append(c); ripped += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(out)
print('pair', sys.argv[3], round(lens[0], 2), sys.argv[4], round(lens[1], 2), 'skew', round(abs(lens[0] - lens[1]), 2), 'ripped', ripped)
