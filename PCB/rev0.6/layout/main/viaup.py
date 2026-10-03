"""viaup.py in out : grow via pads where there is room, for a larger annular ring around the 0.3 mm holes.
Each via tries 0.60, 0.55, then 0.50 mm and takes the largest that still clears other-net copper (tracks, vias, pads,
non-GND-pour zone fills) by 0.15 mm on every copper layer and stays out of no-via rule areas. Others keep 0.45 mm.
Vias inside the courtyard (+1 mm) of the footprints in EXCLUDE_FP (default U20) are left alone: there the GND pour
feeding the RP2350B exposed pad squeezes between the escape vias, and bigger pads cut it off."""
import os
import pcbnew, sys, collections
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]; CL = MM(0.15); POURS = ('F GND', 'GND plane', 'In2 GND', 'B GND')
items = list(b.GetTracks()) + [p for f in b.GetFootprints() for p in f.Pads()]
zones = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetZoneName() not in POURS]
keep = [z for z in b.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
done = collections.Counter()
excl = []
for ref in os.environ.get('EXCLUDE_FP', 'U20').split(','):
    bb = b.FindFootprintByReference(ref).GetCourtyard(pcbnew.F_CrtYd).BBox(); bb.Inflate(MM(1)); excl.append((bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom()))
for v in [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]:
    c = v.GetPosition(); vid = v.m_Uuid.AsString()
    if any(x0 <= c.x <= x1 and y0 <= c.y <= y1 for x0, y0, x1, y1 in excl): done['near U20, kept'] += 1; continue
    box = pcbnew.BOX2I(pcbnew.VECTOR2I(c.x - MM(1.5), c.y - MM(1.5)), pcbnew.VECTOR2I(MM(3), MM(3)))
    near = [o for o in items if o.GetNetCode() != v.GetNetCode() and o.GetBoundingBox().Intersects(box)]
    nz = [z for z in zones if z.GetNetCode() != v.GetNetCode() and z.GetBoundingBox().Intersects(box)]
    for w in (0.60, 0.55, 0.50):
        if MM(w) <= v.GetWidth(pcbnew.F_Cu): break
        s = pcbnew.SHAPE_CIRCLE(c, MM(w) // 2)
        ok = all(not (o.IsOnLayer(l) and o.GetEffectiveShape(l).Collide(s, CL)) for o in near for l in CU)
        ok = ok and all(not (z.IsOnLayer(l) and z.GetFilledPolysList(l).Collide(s, CL)) for z in nz for l in CU)
        ok = ok and all(not z.Outline().Collide(c, MM(w) // 2) for z in keep)
        if ok:
            v.SetWidth(MM(w)); done[w] += 1; break
    else:
        done['0.45 kept'] += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print(dict(done))
