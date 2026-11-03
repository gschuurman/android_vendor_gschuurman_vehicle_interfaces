"""dfm2.py board : copper checks the way a Gerber-only DFM sees them (nets ignored): via-via overlap/gap, via-pad gap,
and same-layer track pairs that come within 0.1 mm without touching."""
import pcbnew, sys
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
def gap(sa, sb):
    if sa.Collide(sb, 0): return 0.0
    lo, hi = 0, MM(1)
    if not sa.Collide(sb, hi): return None
    while hi - lo > MM(0.002):
        m = (lo + hi) // 2
        if sa.Collide(sb, m): hi = m
        else: lo = m
    return T(hi)
vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
L = pcbnew.F_Cu
print('== via-via (overlapping or < 0.2 mm)')
for i, a in enumerate(vias):
    for c in vias[i + 1:]:
        if (a.GetPosition() - c.GetPosition()).EuclideanNorm() > MM(1.2): continue
        g = gap(a.GetEffectiveShape(L), c.GetEffectiveShape(L))
        if g is not None and (g < 0.2): print(f'  {g:.3f}  {a.GetNetname()} ({T(a.GetPosition().x):.3f},{T(a.GetPosition().y):.3f}) - {c.GetNetname()} ({T(c.GetPosition().x):.3f},{T(c.GetPosition().y):.3f})')
print('== via-pad < 0.1 mm (not overlapping)')
for v in vias:
    for f in b.GetFootprints():
        for p in f.Pads():
            for l in (pcbnew.F_Cu, pcbnew.B_Cu):
                if not p.IsOnLayer(l) or (p.GetPosition() - v.GetPosition()).EuclideanNorm() > MM(4): continue
                g = gap(v.GetEffectiveShape(l), p.GetEffectiveShape(l))
                if g is not None and 0 < g < 0.1: print(f'  {g:.3f}  via {v.GetNetname()} ({T(v.GetPosition().x):.3f},{T(v.GetPosition().y):.3f}) - {f.GetReference()}:{p.GetNumber()} {p.GetNetname()}')
print('== track-track same layer, 0 < gap < 0.1 mm')
tr = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
for i, a in enumerate(tr):
    ba = a.GetBoundingBox(); ba.Inflate(MM(0.3))
    for c in tr[i + 1:]:
        if c.GetLayer() != a.GetLayer() or not ba.Intersects(c.GetBoundingBox()): continue
        g = gap(a.GetEffectiveShape(a.GetLayer()), c.GetEffectiveShape(a.GetLayer()))
        if g is not None and 0 < g < 0.1: print(f'  {g:.3f}  {a.GetLayerName()} {a.GetNetname()} ({T(a.GetStart().x):.2f},{T(a.GetStart().y):.2f})-({T(a.GetEnd().x):.2f},{T(a.GetEnd().y):.2f}) | {c.GetNetname()} ({T(c.GetStart().x):.2f},{T(c.GetStart().y):.2f})-({T(c.GetEnd().x):.2f},{T(c.GetEnd().y):.2f})')
