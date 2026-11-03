import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
for z in list(b.Zones()):
    if z.GetZoneName() == 'PWR BB_VOUT':
        o = z.Outline(); old = [(round(o.CVertex(k).x / 1e6, 3), round(o.CVertex(k).y / 1e6, 3)) for k in range(o.TotalVertices())]
        old = [p for p in old if p not in [(44.0, 71.6), (44.0, 70.0), (40.0, 70.0), (40.0, 71.6)]]
        i = old.index((48.7, 71.6))
        new = old[:i] + [(40.0, 71.6), (40.0, 70.0), (44.0, 70.0), (44.0, 71.6)] + old[i:]
        o.RemoveAllContours(); o.NewOutline()
        for x, y in new: o.Append(MM(x), MM(y))
        print(new)
for fp in b.GetFootprints():
    if fp.GetReference().startswith('NT'):
        for fld in fp.GetFields(): fld.SetVisible(False)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
