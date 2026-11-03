"""Remove unlocked tracks/vias (not GND) touching a box. usage: boxevict.py in out x0 y0 x1 y1"""
import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); x0, y0, x1, y1 = map(float, sys.argv[3:7])
box = pcbnew.BOX2I(pcbnew.VECTOR2I(MM(x0), MM(y0)), pcbnew.VECTOR2L(MM(x1 - x0), MM(y1 - y0)))
n = 0
for t in list(b.GetTracks()):
    if t.IsLocked() or t.GetNetname() == 'GND': continue
    if t.HitTest(box, False): b.Remove(t); n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[2]); print('evicted', n)
