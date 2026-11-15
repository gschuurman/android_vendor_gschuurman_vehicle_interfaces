import pcbnew, sys
sys.path.insert(0, ".")
from design import *
F = NAME + "/" + NAME + ".kicad_pcb"
b = pcbnew.LoadBoard(F)
def V(x, y): return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
g = b.FindNet("GND")
for k in b.Zones():
    if k.GetIsRuleArea():
        k.SetDoNotAllowPads(False); k.SetDoNotAllowFootprints(False)
for fp in b.GetFootprints():
    if fp.GetReference() == "J1":
        for p in fp.Pads():
            if p.GetNetname() == "GND": p.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
for L in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(b); z.SetLayer(L); z.SetNet(g)
    o = z.Outline(); o.NewOutline()
    for x, y in [(BX0, BY0), (BX1, BY0), (BX1, BY1), (BX0, BY1)]: o.Append(V(x, y))
    z.SetLocalClearance(pcbnew.FromMM(0.4)); z.SetMinThickness(pcbnew.FromMM(0.25))
    z.SetThermalReliefGap(pcbnew.FromMM(0.4)); z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.5))
    z.SetIsFilled(False); b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(F, b)
b = pcbnew.LoadBoard(F)
pcbnew.WriteDRCReport(b, NAME + "/drc.rpt", pcbnew.EDA_UNITS_MILLIMETRES, True)
