"""bands.py in out : add 0.6 mm no-track/no-via rule bands along a rectangular board outline (keeps Freerouting off the edge)."""
import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); bb = b.GetBoardEdgesBoundingBox()
X0, Y0, X1, Y1 = bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    for (x0, y0, x1, y1) in [(X0, Y0, X1, Y0 + 0.6), (X0, Y1 - 0.6, X1, Y1), (X1 - 0.6, Y0, X1, Y1), (X0, Y0, X0 + 0.6, Y1)]:
        kz = pcbnew.ZONE(b); kz.SetIsRuleArea(True); kz.SetDoNotAllowTracks(True); kz.SetDoNotAllowVias(True); kz.SetDoNotAllowZoneFills(False)
        kz.SetDoNotAllowPads(False); kz.SetDoNotAllowFootprints(False); kz.SetLayer(layer); kz.SetZoneName('edge band')
        o = kz.Outline(); o.NewOutline()
        for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]: o.Append(MM(x), MM(y))
        b.Add(kz)
b.Save(sys.argv[2])
