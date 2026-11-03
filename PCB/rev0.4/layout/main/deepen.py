"""deepen.py in out [step]: stagger the RP2350B (U20) inner escape-via ring. The fan-out puts every second pin's via 0.95 mm
inside the pad row at 0.8 mm pitch, leaving 0.35 mm gaps that no track or pour can pass at 0.13 mm clearance, so the
EP region and the pins escaping inward are walled in on In1/In2/B. Every other inner via moves `step` (0.8) mm further in:
its F.Cu stub is extended, and on each inner layer where a track met the old position a short jog joins it to the new
one. Only moves a via when the new spot clears other-net copper by 0.15 mm on every layer."""
import pcbnew, sys, math
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); STEP = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
U = b.FindFootprintByReference('U20'); C = U.GetPosition(); cx, cy = T(C.x), T(C.y)
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
tracks = list(b.GetTracks())
def at(p, q): return abs(p.x - q.x) < 1000 and abs(p.y - q.y) < 1000
inner = []
for pad in U.Pads():
    if not pad.GetNumber().isdigit() or int(pad.GetNumber()) > 80 or pad.GetNetname() in ('GND', ''): continue
    pp = pad.GetPosition(); px_, py_ = T(pp.x), T(pp.y)
    # inward unit vector: perpendicular to the pad's row, towards the centre
    if abs(px_ - cx) > abs(py_ - cy): d = (-math.copysign(1, px_ - cx), 0)
    else: d = (0, -math.copysign(1, py_ - cy))
    for v in tracks:
        if not isinstance(v, pcbnew.PCB_VIA) or v.GetNetCode() != pad.GetNetCode(): continue
        q = v.GetPosition(); dx, dy = T(q.x) - px_, T(q.y) - py_
        if abs(dx * d[0] + dy * d[1] - 0.95) < 0.02 and abs(dx * d[1] - dy * d[0]) < 0.02:
            inner.append((pad, v, d)); break
# order along each side, deepen every other one
sides = {}
for pad, v, d in inner:
    key = d; along = T(v.GetPosition().x) if d[0] == 0 else T(v.GetPosition().y)
    sides.setdefault(key, []).append((along, pad, v))
others = [t for t in tracks] + [p for f in b.GetFootprints() for p in f.Pads()]
moved = 0
for d, lst in sides.items():
    lst.sort(key=lambda e: e[0])
    for k, (along, pad, v) in enumerate(lst):
        if k % 2 == 0: continue
        old = pcbnew.VECTOR2I(v.GetPosition()); new = pcbnew.VECTOR2I(old.x + MM(STEP * d[0]), old.y + MM(STEP * d[1]))
        shape = pcbnew.SHAPE_CIRCLE(new, MM(0.225)); ok = True
        for o in others:
            if o is v or o.GetNetCode() == v.GetNetCode() or not o.GetBoundingBox().Intersects(pcbnew.BOX2I(pcbnew.VECTOR2I(new.x - MM(1), new.y - MM(1)), pcbnew.VECTOR2I(MM(2), MM(2)))): continue
            for l in CU:
                if o.IsOnLayer(l) and o.GetEffectiveShape(l).Collide(shape, MM(0.15)): ok = False; break
            if not ok: break
        if not ok: print('skip', pad.GetNumber()); continue
        v.SetPosition(new)
        for t in tracks:
            if isinstance(t, pcbnew.PCB_VIA) or t.GetNetCode() != v.GetNetCode(): continue
            for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
                if at(get(), old):
                    if t.GetLayer() == pcbnew.F_Cu and t.IsLocked(): put(new)   # the fan-out stub
                    else:
                        j = pcbnew.PCB_TRACK(b); j.SetStart(old); j.SetEnd(new); j.SetWidth(t.GetWidth()); j.SetLayer(t.GetLayer())
                        j.SetNet(t.GetNet()); j.SetLocked(t.IsLocked()); b.Add(j)
        moved += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('inner vias', len(inner), 'moved', moved)
