"""fixjoint.py in out : run after fixpar.py. Where two pieces of one net continue each other end to end with a small
offset (the grid routers' stair steps), the corner leaves a notch that a Gerber DFM reads as a 0.0x mm trace spacing.
The nearest ends get joined directly by a piece of the same width, if that clears other-net copper by 0.15 mm."""
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

# end-to-end joins: two pieces that continue each other with a small offset leave a notch at the joint; join their
# nearest ends directly with a piece of the same width (checked like above)
base = unc(); filled = 0
for a, c in pairs():
    l = a.GetLayer()
    ends = [(p, q) for p in (a.GetStart(), a.GetEnd()) for q in (c.GetStart(), c.GetEnd())]
    p, q = min(ends, key=lambda e: (e[0] - e[1]).EuclideanNorm())
    if (p - q).EuclideanNorm() > MM(0.5): continue
    t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(p)); t.SetEnd(pcbnew.VECTOR2I(q)); t.SetWidth(min(a.GetWidth(), c.GetWidth()))
    t.SetLayer(l); t.SetNet(a.GetNet()); t.SetLocked(True); b.Add(t)
    if clear([t], l): filled += 1
    else: b.Remove(t); gone.append(t)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('joints filled', filled, 'unconnected', unc())
