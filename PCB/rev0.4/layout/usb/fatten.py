"""fatten.py in out NET[,NET..] [grow_mm] : add copper zones that hug the routed tracks/pads of high-current nets.
The zone outline is the tracks (and the net's SMD pads) grown by grow_mm; the fill then keeps normal clearance
to other nets, so the copper widens wherever there is room."""
import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); nets = sys.argv[3].split(','); g = MM(float(sys.argv[4]) if len(sys.argv) > 4 else 0.8)
TR = list(b.GetTracks()); FPS = list(b.GetFootprints())
for nm in nets:
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        ps = pcbnew.SHAPE_POLY_SET()
        for t in TR:
            if t.GetNetname() == nm and not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == layer:
                t.TransformShapeToPolygon(ps, layer, g, MM(0.01), pcbnew.ERROR_INSIDE)
        if ps.OutlineCount() == 0: continue
        for f in FPS:
            for p in f.Pads():
                if p.GetNetname() == nm and p.IsOnLayer(layer):
                    p.TransformShapeToPolygon(ps, layer, MM(0.05), MM(0.01), pcbnew.ERROR_INSIDE)
        ps.Simplify()
        for i in range(ps.OutlineCount()):
            z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet(nm)); z.SetZoneName('FAT ' + nm)
            o = z.Outline(); o.NewOutline(); ol = ps.Outline(i)
            for k in range(ol.PointCount()): p = ol.CPoint(k); o.Append(p.x, p.y)
            z.SetAssignedPriority(5); z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.25))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
            b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[2]); print('fatten ok')
