"""viafind.py board net x y [r]: list legal through-via spots (0.45/0.2) for net near (x,y), nearest first, plus whether
a straight 0.2 F.Cu track from (x,y) reaches it cleanly."""
import pcbnew, sys, math
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); net = sys.argv[2]; x0, y0 = float(sys.argv[3]), float(sys.argv[4]); R = float(sys.argv[5]) if len(sys.argv) > 5 else 1.5
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]; CL = MM(0.16)
items = []
for t in b.GetTracks():
    if t.GetNetname() != net: items.append(t)
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetname() != net or p.GetNetname() == '': items.append(p)
box = pcbnew.BOX2I(pcbnew.VECTOR2I(MM(x0 - R - 2), MM(y0 - R - 2)), pcbnew.VECTOR2I(MM(2 * R + 4), MM(2 * R + 4)))
items = [i for i in items if i.GetBoundingBox().Intersects(box)]
def ok_shape(shape, layers, extra=0):
    for i in items:
        for l in layers:
            if not i.IsOnLayer(l): continue
            if i.GetEffectiveShape(l).Collide(shape, CL + extra): return False
        if isinstance(i, pcbnew.PAD) and i.HasHole() and i.GetEffectiveHoleShape().Collide(shape, MM(0.25)): return False
    return True
res = []
st = 0.05
n = int(R / st)
for ix in range(-n, n + 1):
    for iy in range(-n, n + 1):
        x, y = x0 + ix * st, y0 + iy * st
        d = math.hypot(x - x0, y - y0)
        if d > R: continue
        c = pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(MM(x), MM(y)), MM(0.225))
        if not ok_shape(c, CU): continue
        hole = pcbnew.SHAPE_CIRCLE(pcbnew.VECTOR2I(MM(x), MM(y)), MM(0.1))
        if not ok_shape(hole, CU, MM(0.1)): continue
        seg = pcbnew.SHAPE_SEGMENT(pcbnew.VECTOR2I(MM(x0), MM(y0)), pcbnew.VECTOR2I(MM(x), MM(y)), MM(0.2))
        res.append((d, round(x, 3), round(y, 3), ok_shape(seg, [pcbnew.F_Cu])))
res.sort()
MIN = float(sys.argv[6]) if len(sys.argv) > 6 else 0
for r in [r for r in res if r[0] >= MIN][:12]: print(r)
