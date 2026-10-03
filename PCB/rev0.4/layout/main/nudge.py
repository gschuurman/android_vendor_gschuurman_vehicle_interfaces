"""nudge.py in out net x y dx dy: move the via of `net` at (x, y) by (dx, dy) mm, dragging the track ends that meet it."""
import pcbnew, sys
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); net = sys.argv[3]; x, y, dx, dy = map(float, sys.argv[4:8])
for v in b.GetTracks():
    if isinstance(v, pcbnew.PCB_VIA) and v.GetNetname() == net and abs(T(v.GetPosition().x) - x) < 0.02 and abs(T(v.GetPosition().y) - y) < 0.02:
        old = pcbnew.VECTOR2I(v.GetPosition()); new = pcbnew.VECTOR2I(old.x + MM(dx), old.y + MM(dy)); v.SetPosition(new); n = 0
        for t in b.GetTracks():
            if isinstance(t, pcbnew.PCB_VIA) or t.GetNetname() != net: continue
            if abs(t.GetStart().x - old.x) < 2000 and abs(t.GetStart().y - old.y) < 2000: t.SetStart(new); n += 1
            if abs(t.GetEnd().x - old.x) < 2000 and abs(t.GetEnd().y - old.y) < 2000: t.SetEnd(new); n += 1
        print('moved via, track ends', n); break
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
