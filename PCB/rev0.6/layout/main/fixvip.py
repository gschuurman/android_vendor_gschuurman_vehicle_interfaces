"""fixvip.py in out : move vias off SMD pins (via-in-pad / via on the pad edge) so solder cannot wick into them.
Exposed / thermal pads (both sides > 1.5 mm) keep their vias. Each offending via moves along one of 8 directions from
the pad centre until it clears the pad by 0.15 mm; the tracks that ended at the via follow it, and a short track on the
pad's layer joins pad centre and via. The first direction that clears all other-net copper (0.15 mm) wins."""
import pcbnew, sys, math
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); gone = []
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]; CL = MM(0.15); POURS = ('F GND', 'GND plane', 'In2 GND', 'B GND')
def unc():
    b.BuildConnectivity(); c = b.GetConnectivity(); c.RecalculateRatsnest(); return c.GetUnconnectedCount(True)
base = unc()
pads = [(f.GetReference(), p) for f in b.GetFootprints() for p in f.Pads() if not p.HasHole() and p.IsOnCopperLayer()]
def small(p, l): s = p.GetSize(l); return not (s.x > MM(1.5) and s.y > MM(1.5))
moved = failed = 0; report = []
for v in [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]:
    vid = v.m_Uuid.AsString(); c0 = pcbnew.VECTOR2I(v.GetPosition()); r = v.GetWidth(pcbnew.F_Cu) // 2
    hit = None
    for ref, p in pads:
        l = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        if p.GetNetCode() == v.GetNetCode() and small(p, l) and p.GetEffectiveShape(l).Collide(pcbnew.SHAPE_CIRCLE(c0, r), 0):
            hit = (ref, p, l); break
    if not hit: continue
    ref, p, l = hit; pc = p.GetPosition()
    att = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetNetCode() == v.GetNetCode()
           and ((t.GetStart() - c0).EuclideanNorm() < r or (t.GetEnd() - c0).EuclideanNorm() < r)]
    near = pcbnew.BOX2I(pcbnew.VECTOR2I(c0.x - MM(3), c0.y - MM(3)), pcbnew.VECTOR2I(MM(6), MM(6)))
    others = [o for o in b.GetTracks() if o.GetNetCode() != v.GetNetCode() and o.GetBoundingBox().Intersects(near)] + \
             [q for _, q in pads if q.GetNetCode() != v.GetNetCode() and q.GetBoundingBox().Intersects(near)] + \
             [q for f in b.GetFootprints() for q in f.Pads() if q.HasHole() and q.GetNetCode() != v.GetNetCode() and q.GetBoundingBox().Intersects(near)]
    zones = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetCode() != v.GetNetCode() and z.GetZoneName() not in POURS]
    keep = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
    best = None
    base_ang = math.atan2(c0.y - pc.y, c0.x - pc.x) if c0 != pc else 0.0
    for k in range(8):
        ang = base_ang + [0, 1, -1, 2, -2, 3, -3, 4][k] * math.pi / 4
        for dmm in [x * 0.05 for x in range(2, 40)]:
            q = pcbnew.VECTOR2I(int(pc.x + MM(dmm) * math.cos(ang)), int(pc.y + MM(dmm) * math.sin(ang)))
            vs = pcbnew.SHAPE_CIRCLE(q, r)
            if p.GetEffectiveShape(l).Collide(vs, MM(0.15)): continue
            stub = pcbnew.SHAPE_SEGMENT(pc, q, MM(0.2))
            ok = all(not (o.IsOnLayer(ll) and o.GetEffectiveShape(ll).Collide(vs, CL)) for o in others for ll in CU)
            ok = ok and all(not (o.IsOnLayer(l) and o.GetEffectiveShape(l).Collide(stub, CL)) for o in others)
            ok = ok and all(not (z.IsOnLayer(ll) and z.GetFilledPolysList(ll).Collide(vs, CL)) for z in zones for ll in CU)
            ok = ok and all(not z.Outline().Collide(q, r) for z in keep)
            if ok:
                # the dragged tracks must stay clear as well
                for t in att:
                    if t.GetLayer() == l: continue
                    a = t.GetEnd() if (t.GetStart() - c0).EuclideanNorm() < r else t.GetStart()
                    sg = pcbnew.SHAPE_SEGMENT(a, q, t.GetWidth())
                    if any(o.IsOnLayer(t.GetLayer()) and o.GetEffectiveShape(t.GetLayer()).Collide(sg, CL) for o in others): ok = False; break
            if ok: best = (dmm, q); break
        if best: break
    if not best: failed += 1; report.append(f'kept {ref}:{p.GetNumber()} {v.GetNetname()}'); continue
    _, q = best
    for t in att:
        if (t.GetStart() - c0).EuclideanNorm() < r: t.SetStart(q)
        if (t.GetEnd() - c0).EuclideanNorm() < r: t.SetEnd(q)
    v.SetPosition(q)
    s = pcbnew.PCB_TRACK(b); s.SetStart(pc); s.SetEnd(q); s.SetWidth(MM(0.2)); s.SetLayer(l); s.SetNet(v.GetNet()); s.SetLocked(True); b.Add(s)
    moved += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
print('moved', moved, 'kept', failed, 'unconnected', unc(), '(was', base, ')'); print('\n'.join(report))
