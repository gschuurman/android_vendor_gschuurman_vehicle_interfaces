"""addvia.py in out net x y: add a 0.45/0.2 through via (e.g. where a removed through-hole pad used to join two layers)."""
import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); x, y = float(sys.argv[4]), float(sys.argv[5])
v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetWidth(MM(0.45)); v.SetDrill(MM(0.2)); v.SetNet(b.FindNet(sys.argv[3])); b.Add(v)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('via added')
