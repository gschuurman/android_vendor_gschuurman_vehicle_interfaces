"""Add the power copper zones (from ppoly.json) and stitching vias (pvias.json), locked.
usage: addpower.py in.kicad_pcb out.kicad_pcb"""
import pcbnew, sys, json
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
LAY = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu}
for z in json.load(open('/w/lay/ppoly.json')):
    zn = pcbnew.ZONE(b); zn.SetLayer(LAY[z['layer']]); zn.SetNet(b.FindNet(z['net']))
    ol = zn.Outline(); ol.NewOutline()
    for x, y in z['pts']: ol.Append(MM(x), MM(y))
    for h in z['holes']:
        ol.NewHole()
        for x, y in h: ol.Append(MM(x), MM(y), -1, 0)
    zn.SetAssignedPriority(10); zn.SetLocalClearance(MM(0.2)); zn.SetMinThickness(MM(0.2))
    zn.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); zn.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    zn.SetZoneName('PWR ' + z['net'].strip('/')); zn.SetLocked(True); b.Add(zn)
for net, x, y in json.load(open('/w/lay/pvias.json')):
    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3))
    v.SetNet(b.FindNet(net)); v.SetLocked(True); b.Add(v)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[2]); print('zones', len(b.Zones()))
