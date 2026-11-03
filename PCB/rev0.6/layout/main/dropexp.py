"""dropexp.py in out netlist: rev 0.5 netlist change on the PCB. GPIO11/12/13/29/34 no longer reach the expansion headers:
their copper (stubs, escape vias, routes) goes and the pads become unconnected; J21 pins 2/3 carry I2C1 (LUX_SDA/SCL)."""
import pcbnew, sys, re
b = pcbnew.LoadBoard(sys.argv[1])
# the schematic's names for no-connect pins, e.g. unconnected-(U20-GPIO11-Pad9)
UNC = {(m.group(1), m.group(2)): m.group(0) for m in re.finditer(r'unconnected-\(([^-]+)-[^)]*-Pad([0-9A-Z]+)\)', open(sys.argv[3], encoding='utf-8').read())}
DROP = ['/EXP_GP11', '/EXP_GP12', '/EXP_GP13', '/EXP_GP29', '/EXP_GP34']
for f in list(b.Footprints()):
    for p in f.Pads():
        if (p.GetNetname() in DROP or f.GetReference() in ('J10', 'J21')) and (f.GetReference(), p.GetNumber()) in UNC:
            # KiCad's name for a pin with a no-connect flag, so schematic parity stays clean
            nm = UNC[(f.GetReference(), p.GetNumber())]
            ni = b.FindNet(nm)
            if not ni: ni = pcbnew.NETINFO_ITEM(b, nm); b.Add(ni)
            p.SetNet(ni)
J21 = b.FindFootprintByReference('J21')
for p in J21.Pads():
    if p.GetNumber() == '2': p.SetNet(b.FindNet('/LUX_SDA'))
    if p.GetNumber() == '3': p.SetNet(b.FindNet('/LUX_SCL'))
n = 0; gone = []   # keep removed items referenced: freeing them corrupts the SWIG bindings
for t in list(b.GetTracks()):
    if t.GetNetname() in DROP: b.Remove(t); gone.append(t); n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('removed copper', n)
