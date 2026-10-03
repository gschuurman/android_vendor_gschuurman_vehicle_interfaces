"""pairkeep.py in out netP netN name: In1 rule area (no tracks, no vias) under an F.Cu differential pair, so its ground
reference stays solid, like the HDMI one; other-net In1 tracks and vias inside it are removed for re-routing.
Env: BUF (0.6 mm each side of the pair), EXCLUDE_FP = refs whose courtyard (+0.5 mm) stays out of the keep-out, e.g.
the chip the pair ends at, so its pin escapes keep their vias; EXCLUDE_XY = 'x,y;x,y' leaves 0.5 mm openings for vias
beside (not under) the pair."""
import os
import pcbnew, sys
from shapely.geometry import LineString
from shapely.ops import unary_union
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); nets = {sys.argv[3], sys.argv[4]}
segs = [LineString([(T(t.GetStart().x), T(t.GetStart().y)), (T(t.GetEnd().x), T(t.GetEnd().y))])
        for t in b.GetTracks() if t.GetNetname() in nets and not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == pcbnew.F_Cu and t.GetLength() > 0]
poly = unary_union(segs).buffer(float(os.environ.get('BUF', 0.6)), join_style=2)
from shapely.geometry import box
for ref in filter(None, os.environ.get('EXCLUDE_FP', '').split(',')):
    f = b.FindFootprintByReference(ref); bb = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
    poly = poly.difference(box(T(bb.GetX()) - 0.5, T(bb.GetY()) - 0.5, T(bb.GetRight()) + 0.5, T(bb.GetBottom()) + 0.5))
own_vias = [LineString([(T(t.GetPosition().x), T(t.GetPosition().y))] * 2).buffer(0.8) for t in b.GetTracks() if t.GetNetname() in nets and isinstance(t, pcbnew.PCB_VIA)]
if own_vias: poly = poly.difference(unary_union(own_vias))   # leave the pair's own swap via out of the keep-out
for q in filter(None, os.environ.get('EXCLUDE_XY', '').split(';')):
    x, y = map(float, q.split(',')); poly = poly.difference(LineString([(x, y), (x, y)]).buffer(0.5))
poly = poly.simplify(0.05)
polys = list(poly.geoms) if poly.geom_type == 'MultiPolygon' else [poly]
for p in polys:
    z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetLayer(pcbnew.In1_Cu); z.SetZoneName(sys.argv[5])
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(False); z.SetDoNotAllowZoneFills(False); z.SetDoNotAllowFootprints(False)
    ol = z.Outline(); ol.NewOutline()
    for x, y in list(p.exterior.coords)[:-1]: ol.Append(MM(x), MM(y))
    b.Add(z)
gone = []
for t in list(b.GetTracks()):
    if t.GetNetname() in nets: continue
    if isinstance(t, pcbnew.PCB_VIA): g = LineString([(T(t.GetPosition().x), T(t.GetPosition().y))] * 2).buffer(0.225)
    elif t.GetLayer() == pcbnew.In1_Cu: g = LineString([(T(t.GetStart().x), T(t.GetStart().y)), (T(t.GetEnd().x), T(t.GetEnd().y))]).buffer(T(t.GetWidth()) / 2)
    else: continue
    if g.intersects(poly):
        b.Remove(t); gone.append(t)   # locked ones here are earlier router output, not fan-out/HDMI/power copper
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('rule areas', len(polys), 'removed', len(gone))
