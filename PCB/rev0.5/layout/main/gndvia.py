"""gndvia.py in drc.json out: for every unconnected GND pad in the DRC report, add a short F/B track and a through via to
the GND planes at the nearest spot that clears all other-net copper on every layer (GND is stripped from the DSN,
so pads the fan-out vias miss stay open). Items are locked."""
import pcbnew, sys, json, math
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); d = json.load(open(sys.argv[2])); gnd = b.FindNet('GND')
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]; CL = MM(0.16)
pads = []
for u in d['unconnected_items']:
    for i in u['items']:
        if i['description'].startswith('Pad') and '[GND]' in i['description']:
            ref = i['description'].split(' of ')[1].split(' ')[0]; num = i['description'].split(' ')[1]
            if (ref, num) not in pads: pads.append((ref, num))
others = [t for t in b.GetTracks() if t.GetNetCode() != gnd.GetNetCode()] + \
         [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetCode() != gnd.GetNetCode() or p.GetNetCode() == 0]
holes = [p for f in b.GetFootprints() for p in f.Pads() if p.HasHole()]
def clear(shape, layers, near, extra=0):
    for i in near:
        for l in layers:
            if i.IsOnLayer(l) and i.GetEffectiveShape(l).Collide(shape, CL + extra): return False
    return True
for ref, num in pads:
    p = [q for q in b.FindFootprintByReference(ref).Pads() if q.GetNumber() == num][0]
    c = p.GetPosition(); x0, y0 = T(c.x), T(c.y)
    layer = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
    bb = p.GetBoundingBox(); half = max(T(bb.GetWidth()), T(bb.GetHeight())) / 2
    box = pcbnew.BOX2I(pcbnew.VECTOR2I(MM(x0 - 4), MM(y0 - 4)), pcbnew.VECTOR2I(MM(8), MM(8)))
    near = [i for i in others if i.GetBoundingBox().Intersects(box)]
    nh = [h for h in holes if h.GetBoundingBox().Intersects(box)]
    best = None
    # the track may leave from the pad centre or from either end of the pad's long axis (inside the pad)
    sz = p.GetSize(layer); ang = math.radians(p.GetOrientationDegrees()); ln = (max(T(sz.x), T(sz.y)) - 0.2) / 2
    ax = (ln, 0) if sz.x >= sz.y else (0, ln)
    ax = (ax[0] * math.cos(ang) + ax[1] * math.sin(ang), -ax[0] * math.sin(ang) + ax[1] * math.cos(ang))
    starts = [c] + [pcbnew.VECTOR2I(MM(x0 + k * ax[0]), MM(y0 + k * ax[1])) for k in (1, -1)]
    for ix in range(-50, 51):
        for iy in range(-50, 51):
            x, y = x0 + ix * 0.05, y0 + iy * 0.05; dd = math.hypot(x - x0, y - y0)
            if dd < 0.25 + 0.3 or dd > 2.5 or (best and dd >= best[0]): continue
            if p.GetEffectiveShape(layer).Collide(pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(MM(x), MM(y)), MM(0.225)), MM(0.15)): continue
            v = pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(MM(x), MM(y)), MM(0.225))
            if not clear(v, CU, near): continue
            if any(h.GetEffectiveHoleShape().Collide(v, MM(0.3)) for h in nh): continue
            st = [s0 for s0 in starts if clear(pcbnew.SHAPE_SEGMENT(s0, pcbnew.VECTOR2I(MM(x), MM(y)), MM(0.2)), [layer], near)]
            if not st: continue
            best = (dd, x, y, st[0])
    if not best: print('no spot for', ref, num); continue
    _, x, y, s0 = best; e = pcbnew.VECTOR2I(MM(x), MM(y))
    if s0 != c:
        t = pcbnew.PCB_TRACK(b); t.SetStart(c); t.SetEnd(s0); t.SetWidth(MM(0.2)); t.SetLayer(layer); t.SetNet(gnd); t.SetLocked(True); b.Add(t)
    t = pcbnew.PCB_TRACK(b); t.SetStart(s0); t.SetEnd(e); t.SetWidth(MM(0.2)); t.SetLayer(layer); t.SetNet(gnd); t.SetLocked(True); b.Add(t)
    v = pcbnew.PCB_VIA(b); v.SetPosition(e); v.SetWidth(MM(0.45)); v.SetDrill(MM(0.2)); v.SetNet(gnd); v.SetLocked(True); b.Add(v)
    print('GND via', ref, num, round(x, 2), round(y, 2))
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[3])
