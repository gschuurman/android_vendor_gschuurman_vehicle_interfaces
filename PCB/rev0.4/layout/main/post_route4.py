"""Import the Freerouting session, pour GND on F/In2/B, tidy silkscreen, fill zones.
usage: post_route.py base.kicad_pcb base.ses out.kicad_pcb"""
import pcbnew, sys, re
src, ses, out = sys.argv[1:4]
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(src)
if ses != '-':
    ok = pcbnew.ImportSpecctraSES(b, ses); print('ses import', ok)
W, H = 100.0, 100.0
def zone(layer, net, pts, prio=0, name=''):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet(net))
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(MM(x), MM(y))
    z.SetAssignedPriority(prio); z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.2))
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.4))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    if name: z.SetZoneName(name)
    b.Add(z); return z
have = {(z.GetLayer(), z.GetNetname()) for z in b.Zones() if not z.GetIsRuleArea()}
full = [(0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)]
for layer, nm in [(pcbnew.F_Cu, 'F GND'), (pcbnew.In1_Cu, 'GND plane'), (pcbnew.In2_Cu, 'In2 GND'), (pcbnew.B_Cu, 'B GND')]:
    if (layer, 'GND') not in have: zone(layer, 'GND', full, 0, nm)
# DNP flags from the schematic
net = open('/w/pcb4/net_carradio_peripheral_rev04.net').read()
for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)(.*?)\(tstamps "', net, re.S):
    if '(name "dnp")' in m.group(2):
        f = b.FindFootprintByReference(m.group(1))
        if f: f.SetDNP(True); print('DNP', m.group(1))
# silkscreen: references only, small
for f in b.GetFootprints():
    f.Value().SetVisible(False)
    r = f.Reference(); r.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0))); r.SetTextThickness(MM(0.15))
    for fld in f.GetFields():
        if fld.GetName() not in ('Reference',): fld.SetVisible(False)
filler = pcbnew.ZONE_FILLER(b); filler.Fill(b.Zones())
b.Save(out)
print('saved', out, 'tracks', len(b.GetTracks()))
