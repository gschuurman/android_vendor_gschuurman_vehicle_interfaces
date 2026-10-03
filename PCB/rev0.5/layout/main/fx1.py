"""fx1.py in out: rev 0.4 fixes after Freerouting. R97/R98 pad nets match the schematic again (rotate 180),
drop Freerouting's extra GND vias at the J14 pad ends, and move R44/R81 off kept power-stage copper.
All geometry is read before anything is removed (pcbnew 10 SWIG quirk)."""
import pcbnew, sys, math
MM = pcbnew.FromMM; V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
b = pcbnew.LoadBoard(sys.argv[1])
TR = list(b.GetTracks()); FPS = list(b.GetFootprints())
def bbx(q): return (q.GetX() / 1e6, q.GetY() / 1e6, q.GetRight() / 1e6, q.GetBottom() / 1e6)
MOVE = ('R44', 'R81')
mpads = [p for r in MOVE for p in b.FindFootprintByReference(r).Pads()]
drop, obs = [], []
for t in TR:
    isv = isinstance(t, pcbnew.PCB_VIA)
    x, y = t.GetPosition().x / 1e6, t.GetPosition().y / 1e6
    if isv and t.GetNetname() == 'GND' and not t.IsLocked() and 94.8 < x < 95.4 and 10 < y < 31: drop.append(t); continue
    pts = [t.GetPosition()] if isv else [t.GetStart(), t.GetEnd()]
    if not t.IsLocked() and any(p.GetNetCode() == t.GetNetCode() and any(p.HitTest(q) for q in pts) for p in mpads): drop.append(t); continue
    obs.append(bbx(t.GetBoundingBox()))
obs += [bbx(p.GetBoundingBox()) for g in FPS if g.GetReference() not in MOVE for p in g.Pads()]
cyb = []
for g in FPS:
    if g.GetReference() in MOVE: continue
    c = g.GetCourtyard(pcbnew.F_CrtYd)
    if c.OutlineCount(): cyb.append(bbx(c.BBox()))
for r in ('R97', 'R98'):
    f = b.FindFootprintByReference(r); f.SetOrientationDegrees(f.GetOrientationDegrees() + 180)
def hit(a, lst, m): return any(a[0] < c[2] + m and a[2] > c[0] - m and a[1] < c[3] + m and a[3] > c[1] - m for c in lst)
for r in MOVE:
    f = b.FindFootprintByReference(r); x0, y0 = f.GetPosition().x / 1e6, f.GetPosition().y / 1e6; done = False
    for rad in [i * 0.25 for i in range(1, 100)]:
        k = max(1, int(2 * math.pi * rad / 0.5))
        for j in range(k):
            a = 2 * math.pi * j / k; x, y = round((x0 + rad * math.cos(a)) * 4) / 4, round((y0 + rad * math.sin(a)) * 4) / 4
            for rot in (0, 90):
                f.SetOrientationDegrees(rot); f.SetPosition(V(x, y)); cb = bbx(f.GetCourtyard(pcbnew.F_CrtYd).BBox())
                if cb[0] < 1 or cb[1] < 1 or cb[2] > 99 or cb[3] > 99 or hit(cb, cyb, 0.5) or hit(cb, obs, 0.25): continue
                done = True; break
            if done: break
        if done: break
    cyb.append(cb); print(r, 'moved to', x, y, rot, done)
for t in drop: b.Remove(t)
print('removed', len(drop))
b.Save(sys.argv[2])
