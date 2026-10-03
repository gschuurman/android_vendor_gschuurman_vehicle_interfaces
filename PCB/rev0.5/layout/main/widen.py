"""widen.py in out net width [min]: widen each track of `net` to `width` (falling back in 0.05 mm steps to `min`) where
the wider track still clears other-net copper (tracks, vias, pads, non-GND-pour zone fills) by the larger netclass clearance."""
import pcbnew, sys
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); net = sys.argv[3]; WMAX = float(sys.argv[4]); WMIN = float(sys.argv[5]) if len(sys.argv) > 5 else 0.3
CL = MM(0.16); POURS = ('F GND', 'GND plane', 'In2 GND', 'B GND')
others = [t for t in b.GetTracks() if t.GetNetname() != net] + [p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname() != net]
zones = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() != net and z.GetZoneName() not in POURS]
keep = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowTracks()]
done = {}
for t in b.GetTracks():
    if t.GetNetname() != net or isinstance(t, pcbnew.PCB_VIA) or T(t.GetWidth()) >= WMAX - 1e-6: continue
    l = t.GetLayer(); old = t.GetWidth(); w = WMAX
    while w >= max(WMIN, T(old)) - 1e-6:
        seg = pcbnew.SHAPE_SEGMENT(t.GetStart(), t.GetEnd(), MM(w)); bb = t.GetBoundingBox(); bb.Inflate(MM(w + 1))
        ok = all(not (o.IsOnLayer(l) and o.GetBoundingBox().Intersects(bb) and o.GetEffectiveShape(l).Collide(seg, CL)) for o in others)
        ok = ok and all(not (z.IsOnLayer(l) and z.GetFilledPolysList(l).Collide(seg, CL)) for z in zones)
        ok = ok and all(not (z.IsOnLayer(l) and z.Outline().Collide(seg, 0)) for z in keep)
        if ok: break
        w = round(w - 0.05, 3)
    if w > T(old) + 1e-6: t.SetWidth(MM(w)); done[w] = done.get(w, 0) + T(t.GetLength())
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('widened (width: mm)', {k: round(v, 1) for k, v in done.items()})
