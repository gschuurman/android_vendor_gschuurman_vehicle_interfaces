"""fixnear.py in out : close same-net copper near misses that a Gerber-only DFM (no nets) reports as spacing errors.
Only what such a check flags: parallel tracks of one net on F.Cu / B.Cu, and vias of one net, that come within 0.1 mm
without touching. Each pair gets a short bridge between their closest points, so it becomes one piece of copper.
(Bridging every same-net near miss is a bad idea: the grid routers leave thousands of tiny fragments.)"""
import math
import pcbnew, sys
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
def gap(sa, sb):
    if sa.Collide(sb, 0): return 0
    lo, hi = 0, MM(0.1)
    if not sa.Collide(sb, hi): return None
    while hi - lo > MM(0.001):
        m = (lo + hi) // 2
        if sa.Collide(sb, m): hi = m
        else: lo = m
    return hi
def pts(t):
    if isinstance(t, pcbnew.PCB_VIA): return pcbnew.SEG(t.GetPosition(), t.GetPosition())
    return pcbnew.SEG(t.GetStart(), t.GetEnd())
items = list(b.GetTracks()); n = 0; new = []
def ang(t): return math.atan2(t.GetEnd().y - t.GetStart().y, t.GetEnd().x - t.GetStart().x) % math.pi
for l in (pcbnew.F_Cu, pcbnew.B_Cu):
    on = [t for t in items if t.IsOnLayer(l) and (isinstance(t, pcbnew.PCB_VIA) or (t.GetLayer() == l and t.GetLength() > MM(0.3)))]
    for i, a in enumerate(on):
        ba = a.GetBoundingBox(); ba.Inflate(MM(0.15))
        for c in on[i + 1:]:
            if c.GetNetCode() != a.GetNetCode() or not ba.Intersects(c.GetBoundingBox()): continue
            va, vc = isinstance(a, pcbnew.PCB_VIA), isinstance(c, pcbnew.PCB_VIA)
            if va != vc: continue
            if not va and min(abs(ang(a) - ang(c)), math.pi - abs(ang(a) - ang(c))) > 0.05: continue
            g = gap(a.GetEffectiveShape(l), c.GetEffectiveShape(l))
            if not g: continue
            sa, sc = pts(a), pts(c)
            # closest points between the two centre lines
            cands = [(sa.NearestPoint(sc.A), sc.A), (sa.NearestPoint(sc.B), sc.B), (sa.A, sc.NearestPoint(sa.A)), (sa.B, sc.NearestPoint(sa.B))]
            p, q = min(cands, key=lambda pq: (pq[0] - pq[1]).EuclideanNorm())
            w = min(x.GetWidth(l) if isinstance(x, pcbnew.PCB_VIA) else x.GetWidth() for x in (a, c))
            t = pcbnew.PCB_TRACK(b); t.SetStart(p); t.SetEnd(q); t.SetWidth(max(w, MM(0.2))); t.SetLayer(l); t.SetNet(a.GetNet()); t.SetLocked(True)
            new.append(t); n += 1
for t in new: b.Add(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('bridged', n)
