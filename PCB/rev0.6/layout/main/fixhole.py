"""fixhole.py in out: the In1 ILLUM_LED run at x=16.4 passes 0.115 mm from J1's NPTH peg (17.125, 88.585); move it to x=16.3
and the BATT_RAW stitching vias beside it from x=15.83 to 15.73 to keep their clearance."""
import pcbnew, sys
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); n = 0
segs = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == '/ILLUM_LED' and t.GetLayer() == pcbnew.In1_Cu]
for t in segs:
    for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
        p = get()
        if abs(T(p.x) - 16.4) < 0.01 and 85.2 < T(p.y) < 92.8: put(pcbnew.VECTOR2I(MM(16.3), p.y)); n += 1
        elif abs(T(p.x) - 16.4) < 0.01 and abs(T(p.y) - 92.9) < 0.01 and abs(T((t.GetEnd() if get == t.GetStart else t.GetStart()).x) - 16.4) < 0.01:
            pass
# the run's end at (16.3, 92.9) must still meet the via at (16.4, 92.9)
for t in segs:
    for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
        p = get()
        if abs(T(p.x) - 16.4) < 0.01 and abs(T(p.y) - 92.9) < 0.01:
            q = pcbnew.VECTOR2I(p); put(pcbnew.VECTOR2I(MM(16.3), MM(92.8)))
            j = pcbnew.PCB_TRACK(b); j.SetStart(pcbnew.VECTOR2I(MM(16.3), MM(92.8))); j.SetEnd(q); j.SetWidth(t.GetWidth()); j.SetLayer(t.GetLayer()); j.SetNet(t.GetNet()); b.Add(j)
for v in b.GetTracks():
    if isinstance(v, pcbnew.PCB_VIA) and v.GetNetname() == '/BATT_RAW' and abs(T(v.GetPosition().x) - 15.83) < 0.01 and 85 < T(v.GetPosition().y) < 91:
        v.SetPosition(pcbnew.VECTOR2I(MM(15.73), v.GetPosition().y)); n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); print('moved', n); b.Save(sys.argv[2])
