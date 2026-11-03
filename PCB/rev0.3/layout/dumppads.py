"""Dump copper pad outlines (+ existing tracks/vias) as JSON for the host-side polygon builder."""
import pcbnew, sys, json
b = pcbnew.LoadBoard(sys.argv[1]); out = []
LAY = {'F': pcbnew.F_Cu, 'B': pcbnew.B_Cu, 'In1': pcbnew.In1_Cu, 'In2': pcbnew.In2_Cu}
def poly(ps):
    res = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i); res.append([(o.CPoint(k).x / 1e6, o.CPoint(k).y / 1e6) for k in range(o.PointCount())])
    return res
for f in b.GetFootprints():
    for p in f.Pads():
        for ln, l in LAY.items():
            if not p.IsOnLayer(l) or not p.IsOnCopperLayer(): continue
            try: ps = p.GetEffectivePolygon(l, pcbnew.ERROR_INSIDE)
            except TypeError: ps = p.GetEffectivePolygon(pcbnew.ERROR_INSIDE)
            out.append(dict(ref=f.GetReference(), num=p.GetNumber(), net=p.GetNetname(), layer=ln, poly=poly(ps),
                            hole=p.GetDrillSizeX() / 1e6 if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else 0,
                            pos=(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)))
        # NPTH holes on all layers
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            for ln in LAY:
                out.append(dict(ref=f.GetReference(), num='NPTH', net='', layer=ln, poly=[], hole=p.GetDrillSizeX() / 1e6,
                                pos=(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)))
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA):
        for ln in LAY:
            out.append(dict(ref='via', num='', net=t.GetNetname(), layer=ln, poly=[], hole=t.GetWidth(pcbnew.F_Cu) / 1e6 / 2,
                            pos=(t.GetPosition().x / 1e6, t.GetPosition().y / 1e6), via=1))
    else:
        ln = {pcbnew.F_Cu: 'F', pcbnew.B_Cu: 'B', pcbnew.In1_Cu: 'In1', pcbnew.In2_Cu: 'In2'}[t.GetLayer()]
        out.append(dict(ref='track', num='', net=t.GetNetname(), layer=ln, poly=[], hole=0, w=t.GetWidth() / 1e6,
                        seg=[(t.GetStart().x / 1e6, t.GetStart().y / 1e6), (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)]))
json.dump(out, open(sys.argv[2], 'w'))
print('pads', len(out))
