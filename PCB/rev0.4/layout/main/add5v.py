"""add5v.py in out : In2 copper strip for +5V_SYS from the TPS55288 output (R74/NT2) to the VIM3 VIN connector J18."""
import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
z = pcbnew.ZONE(b); z.SetLayer(pcbnew.In2_Cu); z.SetNet(b.FindNet('/+5V_SYS')); z.SetZoneName('In2 +5V_SYS feed')
o = z.Outline(); o.NewOutline()
for x, y in [(0.6, 10.6), (9.6, 10.6), (9.6, 17.6), (7.0, 17.6), (7.0, 50.0), (46.0, 50.0), (46.0, 80.0), (38.5, 80.0), (38.5, 56.0), (0.6, 56.0)]:
    o.Append(MM(x), MM(y))
z.SetAssignedPriority(5); z.SetLocalClearance(MM(0.3)); z.SetMinThickness(MM(0.25)); z.SetThermalReliefGap(MM(0.4)); z.SetThermalReliefSpokeWidth(MM(0.6))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS); z.SetIsFilled(False); b.Add(z)
b.Save(sys.argv[2]); print('5V strip added')
