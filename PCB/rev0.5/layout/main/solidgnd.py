"""solidgnd.py in out REF:PAD,... : connect these GND through-hole pads to the pours solid instead of with thermal spokes
(routing left too few spokes on the module-socket GND pins: starved_thermal)."""
import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1])
for rp in sys.argv[3].split(','):
    ref, num = rp.split(':')
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num: p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL); print('solid', ref, num)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
