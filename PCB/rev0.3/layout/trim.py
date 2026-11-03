"""trim.py in drc.json out : shorten tracks DRC flags as dangling back to the last point where they touch same-net copper."""
import pcbnew, sys, json
b = pcbnew.LoadBoard(sys.argv[1]); d = json.load(open(sys.argv[2])); ZS = list(b.Zones()); TR = list(b.GetTracks())
pads = [p for f in b.GetFootprints() for p in f.Pads()]
bad = {i['uuid'] for v in d['violations'] if v['type'] == 'track_dangling' for i in v['items']}
def pts_of(net, me):
    out = []
    for t in TR:
        if t is me or t.GetNetCode() != net: continue
        if isinstance(t, pcbnew.PCB_VIA): out.append((t.GetPosition(), t.GetWidth(pcbnew.F_Cu) // 2, None))
        else: out += [(t.GetStart(), t.GetWidth() // 2, t.GetLayer()), (t.GetEnd(), t.GetWidth() // 2, t.GetLayer())]
    for p in pads:
        if p.GetNetCode() == net: out.append((p.GetPosition(), min(p.GetSize().x, p.GetSize().y) // 2, None))
    return out
def touched(pt, net, me):
    for q, r, ly in pts_of(net, me):
        if (ly is None or ly == me.GetLayer()) and (q - pt).EuclideanNorm() <= r + me.GetWidth() // 2: return True
    for t in TR:   # lies on another same-net segment of this layer
        if t is me or isinstance(t, pcbnew.PCB_VIA) or t.GetNetCode() != net or t.GetLayer() != me.GetLayer(): continue
        if t.HitTest(pt, 1000): return True
    return False
n = 0
for t in TR:
    if isinstance(t, pcbnew.PCB_VIA) or t.m_Uuid.AsString() not in bad: continue
    net = t.GetNetCode(); s, e = t.GetStart(), t.GetEnd()
    for free, fixed, setter in ((s, e, t.SetStart), (e, s, t.SetEnd)):
        if touched(free, net, t): continue
        # candidate contact points along the segment, nearest to the free end first
        L = (fixed - free).EuclideanNorm() or 1
        best = None
        for q, r, ly in pts_of(net, t):
            if ly is not None and ly != t.GetLayer(): continue
            v = q - free; u = (v.x * (fixed.x - free.x) + v.y * (fixed.y - free.y)) / L
            if not 0 < u < L: continue
            px = pcbnew.VECTOR2I(int(free.x + (fixed.x - free.x) * u / L), int(free.y + (fixed.y - free.y) * u / L))
            if (px - q).EuclideanNorm() <= r and (best is None or u < best[0]): best = (u, q)
        if best: setter(best[1]); n += 1; print('trimmed', t.GetNetname())
        break
pcbnew.ZONE_FILLER(b).Fill(ZS); b.Save(sys.argv[3]); print('trim', n)
