"""fx2.py in out: move the J14 GND stub vias clear of the pad ends (0.45 mm past the pad, every other one 1.1 mm),
and give three undersized power vias a 0.6/0.3 size."""
import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
TR = list(b.GetTracks())
vias = sorted([t for t in TR if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == 'GND' and abs(t.GetPosition().x / 1e6 - 95.105) < 0.01
               and 10 < t.GetPosition().y / 1e6 < 31], key=lambda v: v.GetPosition().y)
segs = [t for t in TR if not isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == 'GND' and abs(t.GetEnd().x / 1e6 - 95.105) < 0.01 and 10 < t.GetEnd().y / 1e6 < 31]
prev = None; stag = False
for v in vias:
    y = v.GetPosition().y / 1e6
    stag = prev is not None and abs(y - prev) < 0.6 and not stag
    x = 94.505 + 0.6 + (0.45 if not stag else 1.1)
    for s in segs:
        if abs(s.GetEnd().y / 1e6 - y) < 0.01: s.SetEnd(pcbnew.VECTOR2I(MM(x), MM(y)))
    v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); prev = y
print('moved', len(vias))
for t in TR:
    if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() in ('/+5V_SYS', '/VSYS_IN') and t.GetWidth(pcbnew.F_Cu) - t.GetDrillValue() < MM(0.2):
        t.SetWidth(MM(0.6)); t.SetDrill(MM(0.3)); print('via', t.GetPosition().x / 1e6, t.GetPosition().y / 1e6)
b.Save(sys.argv[2])
