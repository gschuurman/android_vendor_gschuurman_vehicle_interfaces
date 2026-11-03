"""Delete unlocked tracks/vias of other nets that cut through the power zones. usage: evict.py in out"""
import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
zones = [z for z in b.Zones() if z.GetZoneName().startswith('PWR ')]
n = 0
for t in list(b.GetTracks()):
    if t.IsLocked(): continue
    for z in zones:
        if t.GetNetCode() == z.GetNetCode(): continue
        if not (t.IsOnLayer(z.GetLayer())): continue
        if isinstance(t, pcbnew.PCB_VIA):
            hit = z.Outline().Collide(t.GetPosition(), MM(0.3 + 0.2))
        else:
            seg = pcbnew.SEG(t.GetStart(), t.GetEnd())
            hit = z.Outline().Collide(seg, int(t.GetWidth() / 2 + MM(0.2)))
        if hit: b.Remove(t); n += 1; break
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[2]); print('evicted', n)
