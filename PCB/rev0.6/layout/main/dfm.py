"""dfm.py board : JLC-style spacing report: via-to-pad, THT-to-SMD pad, pad-to-pad, track-to-track (edge distances)."""
import pcbnew, sys, collections
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
pads = [(f.GetReference(), p) for f in b.GetFootprints() for p in f.Pads() if p.IsOnCopperLayer()]
vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
trk = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA)]
def dist(a, la, bb, lb, l):
    return T(a.GetEffectiveShape(l).GetClearance(bb.GetEffectiveShape(l))) if hasattr(a.GetEffectiveShape(l), 'GetClearance') else None
def edge(a, bshape_item, l):
    sa = a.GetEffectiveShape(l); sb = bshape_item.GetEffectiveShape(l)
    lo, hi = 0, MM(3)
    if not sa.Collide(sb, hi): return None
    while hi - lo > MM(0.002):
        m = (lo + hi) // 2
        if sa.Collide(sb, m): hi = m
        else: lo = m
    return T(hi)
def near(a, bb, r=3):
    A, B = a.GetBoundingBox(), bb.GetBoundingBox(); A.Inflate(MM(r)); return A.Intersects(B)
out = collections.defaultdict(list)
for v in vias:
    for ref, p in pads:
        if not near(v, p, 1): continue
        for l in (pcbnew.F_Cu, pcbnew.B_Cu):
            if p.IsOnLayer(l):
                d = edge(v, p, l)
                if d is not None and d < 0.25:
                    out['via-pad'].append((d, f'via {v.GetNetname()} @({T(v.GetPosition().x):.2f},{T(v.GetPosition().y):.2f}) - {ref}:{p.GetNumber()} {p.GetNetname()}' + (' SAME NET' if p.GetNetCode() == v.GetNetCode() else '')))
                break
tht = [(r, p) for r, p in pads if p.HasHole()]; smd = [(r, p) for r, p in pads if not p.HasHole()]
for r1, a in tht:
    for r2, c in smd:
        if not near(a, c, 1.5): continue
        l = c.GetLayer() if c.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        d = edge(a, c, l)
        if d is not None and d < 1.0: out['tht-smd'].append((d, f'{r1}:{a.GetNumber()} - {r2}:{c.GetNumber()}'))
for i, (r1, a) in enumerate(pads):
    for r2, c in pads[i + 1:]:
        if a.GetNetCode() == c.GetNetCode() and a.GetNetCode() != 0: continue
        if not near(a, c, 0.5): continue
        for l in CU:
            if a.IsOnLayer(l) and c.IsOnLayer(l):
                d = edge(a, c, l)
                if d is not None and d < 0.15: out['pad-pad'].append((d, f'{r1}:{a.GetNumber()} - {r2}:{c.GetNumber()} on {b.GetLayerName(l)}'))
                break
for i, a in enumerate(trk):
    for c in trk[i + 1:]:
        if a.GetLayer() != c.GetLayer() or a.GetNetCode() == c.GetNetCode() or not near(a, c, 0.3): continue
        d = edge(a, c, a.GetLayer())
        if d is not None and d < 0.11: out['trk-trk'].append((d, f'{a.GetNetname()} - {c.GetNetname()} on {a.GetLayerName()} @({T(a.GetStart().x):.2f},{T(a.GetStart().y):.2f})'))
for k in ('via-pad', 'tht-smd', 'pad-pad', 'trk-trk'):
    v = sorted(set(out[k]))
    print(f'== {k}: {len(v)}')
    for d, s in v[:15]: print(f'   {d:.3f}  {s}')
