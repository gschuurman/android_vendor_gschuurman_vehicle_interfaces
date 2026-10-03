"""prune2.py in drc.json out : remove the vias / tracks KiCad's DRC reports as dangling (via_dangling, track_dangling),
whether locked or not. An item whose removal would add an unconnected pair is kept, except a via whose tracks all sit
on one layer: then its tracks are joined at the via centre on that layer and the via goes (JLC flags such vias)."""
import pcbnew, sys, json
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); d = json.load(open(sys.argv[2])); gone = []
def unc():
    b.BuildConnectivity(); c = b.GetConnectivity(); c.RecalculateRatsnest(); return c.GetUnconnectedCount(True)
base = unc(); hits = []
for v in d['violations']:
    if v['type'] in ('via_dangling', 'track_dangling'):
        i = v['items'][0]; hits.append((v['type'], i['pos']['x'], i['pos']['y'], i['description'].split('[')[1].split(']')[0]))
def find(kind, x, y, net):
    p = pcbnew.VECTOR2I(MM(x), MM(y))
    for t in b.GetTracks():
        if t.GetNetname() != net: continue
        if kind == 'via_dangling' and isinstance(t, pcbnew.PCB_VIA) and (t.GetPosition() - p).EuclideanNorm() < MM(0.02): return t
        if kind == 'track_dangling' and not isinstance(t, pcbnew.PCB_VIA) and pcbnew.SEG(t.GetStart(), t.GetEnd()).Distance(p) < MM(0.02): return t
removed = joined = kept = 0
for kind, x, y, net in hits:
    t = find(kind, x, y, net)
    if t is None: continue
    b.Remove(t)
    if unc() <= base: gone.append(t); removed += 1; continue
    b.Add(t)
    if kind == 'via_dangling':
        c = t.GetPosition(); r = t.GetWidth(pcbnew.F_Cu) // 2 + MM(0.05)
        tr = [s for s in b.GetTracks() if not isinstance(s, pcbnew.PCB_VIA) and s.GetNetCode() == t.GetNetCode()
              and min((s.GetStart() - c).EuclideanNorm(), (s.GetEnd() - c).EuclideanNorm()) < r]
        if tr and len({s.GetLayer() for s in tr}) == 1:
            for s in tr:   # pull each end that sits in the via onto its centre
                if (s.GetStart() - c).EuclideanNorm() < r: s.SetStart(c)
                if (s.GetEnd() - c).EuclideanNorm() < r: s.SetEnd(c)
            b.Remove(t)
            if unc() <= base: gone.append(t); joined += 1; continue
            b.Add(t)
    kept += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[3]); print('removed', removed, 'joined', joined, 'kept', kept, 'unconnected', unc())

# second pass: dangling ends that are overshoots past a T-junction get trimmed back to the last connection point
b = pcbnew.LoadBoard(sys.argv[3]); gone = []
base = unc(); trimmed = 0
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
for kind, x, y, net in [h for h in hits if h[0] == 'track_dangling']:
    t = find(kind, x, y, net)
    if t is None: continue
    l = t.GetLayer(); hw = t.GetWidth() // 2
    tid = t.m_Uuid.AsString()   # SWIG gives a new wrapper per lookup, so compare UUIDs, not identity
    others = [o for o in b.GetTracks() if o.m_Uuid.AsString() != tid and o.GetNetCode() == t.GetNetCode() and o.IsOnLayer(l)] + \
             [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetCode() == t.GetNetCode() and p.IsOnLayer(l)]
    def touches(pt):
        s = pcbnew.SHAPE_CIRCLE(pt, hw)
        return any(o.GetEffectiveShape(l).Collide(s, 0) for o in others)
    for get, put, far in ((t.GetStart, t.SetStart, t.GetEnd), (t.GetEnd, t.SetEnd, t.GetStart)):
        e = pcbnew.VECTOR2I(get())
        if touches(e): continue
        f = pcbnew.VECTOR2I(far()); seg = pcbnew.SEG(e, f); L = seg.Length()
        # walk from the dangling end towards the other end until something touches the track
        steps = max(2, int(L / MM(0.02))); new = None
        for k in range(1, steps + 1):
            q = pcbnew.VECTOR2I(int(e.x + (f.x - e.x) * k / steps), int(e.y + (f.y - e.y) * k / steps))
            if touches(q): new = q; break
        if new is None: continue
        put(new)
        if unc() > base: put(e)
        else: trimmed += 1
        break
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[3]); print('trimmed', trimmed, 'unconnected', unc())
