import pcbnew, sys, math
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
for l in (pcbnew.F_Cu, pcbnew.B_Cu):
    tr = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == l and t.GetLength() > MM(0.3)]
    for i, a in enumerate(tr):
        da = math.atan2(a.GetEnd().y - a.GetStart().y, a.GetEnd().x - a.GetStart().x) % math.pi
        for c in tr[i + 1:]:
            dc = math.atan2(c.GetEnd().y - c.GetStart().y, c.GetEnd().x - c.GetStart().x) % math.pi
            if min(abs(da - dc), math.pi - abs(da - dc)) > 0.05: continue
            g = gap(a.GetEffectiveShape(l), c.GetEffectiveShape(l))
            if g and g < MM(0.1): print(b.GetLayerName(l), round(T(g), 3), a.GetNetname(), (round(T(a.GetStart().x), 2), round(T(a.GetStart().y), 2), round(T(a.GetEnd().x), 2), round(T(a.GetEnd().y), 2)), c.GetNetname(), (round(T(c.GetStart().x), 2), round(T(c.GetStart().y), 2), round(T(c.GetEnd().x), 2), round(T(c.GetEnd().y), 2)))
