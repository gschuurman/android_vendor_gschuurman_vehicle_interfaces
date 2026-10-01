"""simplify.py in out [eps] [skipfile] : collapse grid-router stair-steps.
Chains of unlocked same-net/same-layer/same-width segments joined at plain 2-way nodes (no pad, via or branch)
are replaced by a Douglas-Peucker polyline. Chains listed (by first-segment uuid) in skipfile are left alone."""
import pcbnew, sys, json
from collections import defaultdict
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); ZS = list(b.Zones()); TR = list(b.GetTracks())
eps = float(sys.argv[3]) if len(sys.argv) > 3 else 0.08
skip = set(json.load(open(sys.argv[4]))) if len(sys.argv) > 4 else set()
K = lambda p: (round(p.x / 1000), round(p.y / 1000))          # 1 um key
segs = [t for t in TR if not isinstance(t, pcbnew.PCB_VIA)]
vias = [t for t in TR if isinstance(t, pcbnew.PCB_VIA)]
hard = set()
for v in vias: hard.add(K(v.GetPosition()))
for f in b.GetFootprints():
    for p in f.Pads(): hard.add(K(p.GetPosition()))
groups = defaultdict(list)
for s in segs: groups[(s.GetNetCode(), s.GetLayer(), s.GetWidth())].append(s)
def dp(pts, e):
    if len(pts) < 3: return pts
    (x0, y0), (x1, y1) = pts[0], pts[-1]; dx, dy = x1 - x0, y1 - y0; L = (dx * dx + dy * dy) ** 0.5 or 1e-9
    dmax, im = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dy * (pts[i][0] - x0) - dx * (pts[i][1] - y0)) / L
        if d > dmax: dmax, im = d, i
    if dmax > e: return dp(pts[:im + 1], e)[:-1] + dp(pts[im:], e)
    return [pts[0], pts[-1]]
made = []; nrm = nadd = 0
for (net, layer, w), ss in groups.items():
    deg = defaultdict(list)
    for s in ss: deg[K(s.GetStart())].append(s); deg[K(s.GetEnd())].append(s)
    # also count other-width/other-layer copper ends of same net as hard
    used = set()
    for s0 in ss:
        if id(s0) in used or s0.IsLocked(): continue
        # grow chain both directions
        chain = [s0]; used.add(id(s0)); ends = [K(s0.GetStart()), K(s0.GetEnd())]
        for side in (0, 1):
            while True:
                n = ends[side]
                if n in hard or len(deg[n]) != 2: break
                nxt = [t for t in deg[n] if id(t) not in used]
                if not nxt or nxt[0].IsLocked(): break
                t = nxt[0]; used.add(id(t))
                other = K(t.GetEnd()) if K(t.GetStart()) == n else K(t.GetStart())
                if side == 0: chain.insert(0, t)
                else: chain.append(t)
                ends[side] = other
        if len(chain) < 3: continue
        # ordered points
        pts = [ends[0]]; cur = ends[0]
        for t in chain:
            a, c = K(t.GetStart()), K(t.GetEnd()); nxt = c if a == cur else a; pts.append(nxt); cur = nxt
        if chain[0].m_Uuid.AsString() in skip: continue
        new = dp([(x / 1000, y / 1000) for x, y in pts], eps)
        if len(new) - 1 >= len(chain): continue
        uu = []
        for i in range(len(new) - 1):
            t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(MM(new[i][0]), MM(new[i][1]))); t.SetEnd(pcbnew.VECTOR2I(MM(new[i + 1][0]), MM(new[i + 1][1])))
            t.SetWidth(w); t.SetLayer(layer); t.SetNetCode(net); b.Add(t); uu.append(t.m_Uuid.AsString()); nadd += 1
        made.append(dict(first=chain[0].m_Uuid.AsString(), new=uu))
        for t in chain: b.Remove(t); nrm += 1
json.dump(made, open(sys.argv[2] + '.map.json', 'w'))
pcbnew.ZONE_FILLER(b).Fill(ZS); b.Save(sys.argv[2]); print('chains', len(made), 'removed', nrm, 'added', nadd)
