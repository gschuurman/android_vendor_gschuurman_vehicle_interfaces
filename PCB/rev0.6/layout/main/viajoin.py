"""viajoin.py in out : a track of the same net passing within 0.18 mm of a via hole without touching the via gets joined
to it by a short piece (via centre to the nearest point of the track, same width) on F.Cu / B.Cu, so a Gerber-only DFM
no longer sees a hole close to an unrelated trace. Each join is checked against other-net copper (0.15 mm)."""
import pcbnew, sys
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); CL = MM(0.15); POURS = ('F GND', 'GND plane', 'In2 GND', 'B GND')
vs = [v for v in b.GetTracks() if isinstance(v, pcbnew.PCB_VIA)]
tr = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu)]
others = list(b.GetTracks()) + [p for f in b.GetFootprints() for p in f.Pads()]
zones = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetZoneName() not in POURS]
added = skipped = 0; new = []
for v in vs:
    c = v.GetPosition(); r = v.GetDrill() // 2; rp = v.GetWidth(pcbnew.F_Cu) // 2
    for t in tr:
        if t.GetNetCode() != v.GetNetCode(): continue
        s = pcbnew.SEG(t.GetStart(), t.GetEnd()); d = s.Distance(c)
        if d <= rp + t.GetWidth() // 2 or d - r - t.GetWidth() // 2 >= MM(0.18): continue
        q = s.NearestPoint(c); l = t.GetLayer()
        sh = pcbnew.SHAPE_SEGMENT(c, q, t.GetWidth())
        bb = pcbnew.BOX2I(pcbnew.VECTOR2I(min(c.x, q.x) - MM(1), min(c.y, q.y) - MM(1)), pcbnew.VECTOR2I(abs(c.x - q.x) + MM(2), abs(c.y - q.y) + MM(2)))
        ok = all(not (o.GetNetCode() != v.GetNetCode() and o.IsOnLayer(l) and o.GetBoundingBox().Intersects(bb) and o.GetEffectiveShape(l).Collide(sh, CL)) for o in others)
        ok = ok and all(not (z.GetNetCode() != v.GetNetCode() and z.IsOnLayer(l) and z.GetFilledPolysList(l).Collide(sh, CL)) for z in zones)
        if not ok: skipped += 1; continue
        j = pcbnew.PCB_TRACK(b); j.SetStart(pcbnew.VECTOR2I(c)); j.SetEnd(q); j.SetWidth(t.GetWidth()); j.SetLayer(l); j.SetNet(v.GetNet()); j.SetLocked(True)
        new.append(j); added += 1
for j in new: b.Add(j)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('joined', added, 'skipped', skipped)
