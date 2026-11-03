"""fixpar.py in out : remove the slivers between parallel pieces of one net on F.Cu / B.Cu that run less than 0.1 mm
apart without touching (left by the grid routers; JLC's Gerber DFM reports them as trace spacing 'danger').
For each pair: delete one piece if the net stays connected; otherwise shift the shorter piece onto the longer one's
line (tracks ending on it follow), so the two become one trace. Every change is checked against other-net copper
(0.15 mm) and connectivity, and undone if it fails."""
import pcbnew, sys, math
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); gone = []
CL = MM(0.15); POURS = ('F GND', 'GND plane', 'In2 GND', 'B GND')
def unc():
    b.BuildConnectivity(); c = b.GetConnectivity(); c.RecalculateRatsnest(); return c.GetUnconnectedCount(True)
def gap(sa, sb):
    if sa.Collide(sb, 0): return 0
    lo, hi = 0, MM(0.1)
    if not sa.Collide(sb, hi): return None
    while hi - lo > MM(0.001):
        m = (lo + hi) // 2
        if sa.Collide(sb, m): hi = m
        else: lo = m
    return hi
def ang(t): return math.atan2(t.GetEnd().y - t.GetStart().y, t.GetEnd().x - t.GetStart().x) % math.pi
def pairs():
    out = []
    for l in (pcbnew.F_Cu, pcbnew.B_Cu):
        tr = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == l and t.GetLength() > 0]
        for i, a in enumerate(tr):
            ba = a.GetBoundingBox(); ba.Inflate(MM(0.2))
            for c in tr[i + 1:]:
                if c.GetNetCode() != a.GetNetCode() or not ba.Intersects(c.GetBoundingBox()): continue
                if min(abs(ang(a) - ang(c)), math.pi - abs(ang(a) - ang(c))) > 0.05: continue
                g = gap(a.GetEffectiveShape(l), c.GetEffectiveShape(l))
                if g: out.append((a, c))
    return out
def clear(items, l):
    for t in items:
        sh = t.GetEffectiveShape(l); bb = t.GetBoundingBox(); bb.Inflate(MM(1))
        for o in list(b.GetTracks()) + [p for f in b.GetFootprints() for p in f.Pads()]:
            if o.GetNetCode() == t.GetNetCode() or not o.IsOnLayer(l) or not o.GetBoundingBox().Intersects(bb): continue
            if o.GetEffectiveShape(l).Collide(sh, CL): return False
        for z in b.Zones():
            if z.GetIsRuleArea() or z.GetNetCode() == t.GetNetCode() or z.GetZoneName() in POURS or not z.IsOnLayer(l): continue
            if z.GetFilledPolysList(l).Collide(sh, CL): return False
    return True
base = unc(); deleted = shifted = failed = 0
for rnd in range(5):
    ps = pairs()
    if not ps: break
    done = set()
    for a, c in ps:
        ka, kc = a.m_Uuid.AsString(), c.m_Uuid.AsString()
        if ka in done or kc in done: continue
        l = a.GetLayer(); ok = False
        for v in sorted((a, c), key=lambda t: t.GetLength()):
            b.Remove(v)
            if unc() <= base: gone.append(v); done.add(v.m_Uuid.AsString()); deleted += 1; ok = True; break
            b.Add(v)
        if ok: continue
        s, k = (a, c) if a.GetLength() < c.GetLength() else (c, a)
        ks = pcbnew.SEG(k.GetStart(), k.GetEnd())
        old = (pcbnew.VECTOR2I(s.GetStart()), pcbnew.VECTOR2I(s.GetEnd()))
        new = (ks.LineProject(old[0]), ks.LineProject(old[1]))
        if any(isinstance(o, pcbnew.PCB_VIA) and ((o.GetPosition() - old[0]).EuclideanNorm() < MM(0.01) or (o.GetPosition() - old[1]).EuclideanNorm() < MM(0.01))
               for o in b.GetTracks() if o.GetNetCode() == s.GetNetCode()):
            failed += 1; continue   # a via sits on an end: leave it
        moved = []
        for o in b.GetTracks():
            if isinstance(o, pcbnew.PCB_VIA) or o.GetNetCode() != s.GetNetCode() or o.m_Uuid.AsString() == s.m_Uuid.AsString() or o.GetLayer() != l: continue
            for e, n in zip(old, new):
                if (o.GetStart() - e).EuclideanNorm() < MM(0.005): moved.append((o, 'S', pcbnew.VECTOR2I(o.GetStart()))); o.SetStart(n)
                if (o.GetEnd() - e).EuclideanNorm() < MM(0.005): moved.append((o, 'E', pcbnew.VECTOR2I(o.GetEnd()))); o.SetEnd(n)
        s.SetStart(new[0]); s.SetEnd(new[1])
        if unc() <= base and clear([s] + [m[0] for m in moved], l):
            shifted += 1; done.add(s.m_Uuid.AsString())
        else:
            s.SetStart(old[0]); s.SetEnd(old[1])
            for o, w, p in moved: (o.SetStart if w == 'S' else o.SetEnd)(p)
            failed += 1
left = pairs()
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
print('deleted', deleted, 'shifted', shifted, 'not fixed', failed, 'pairs left', len(left), 'unconnected', unc())
for a, c in left: print('  left:', b.GetLayerName(a.GetLayer()), a.GetNetname(), round(T(a.GetStart().x), 2), round(T(a.GetStart().y), 2))

