import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); print('ses', pcbnew.ImportSpecctraSES(b, sys.argv[2]))
bb = b.GetBoardEdgesBoundingBox(); W, H = bb.GetWidth() / 1e6, bb.GetHeight() / 1e6
for layer, nm in [(pcbnew.F_Cu, 'F GND'), (pcbnew.B_Cu, 'B GND')]:
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet('GND')); z.SetZoneName(nm)
    o = z.Outline(); o.NewOutline()
    for x, y in [(0.4, 0.4), (W - 0.4, 0.4), (W - 0.4, H - 0.4), (0.4, H - 0.4)]: o.Append(MM(x), MM(y))
    z.SetLocalClearance(MM(0.3)); z.SetMinThickness(MM(0.25)); z.SetThermalReliefGap(MM(0.4)); z.SetThermalReliefSpokeWidth(MM(0.45))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS); b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
for f in b.GetFootprints():
    f.Value().SetVisible(False)
    t = f.Reference(); t.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8))); t.SetTextThickness(MM(0.12))
b.Save(sys.argv[3]); print('ok')
