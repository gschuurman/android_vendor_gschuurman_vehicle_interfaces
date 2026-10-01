"""Host side: build power copper polygons = seed shapes minus foreign copper (buffered), joined to own pads.
usage: powerpoly.py pads.json out.json"""
import json, sys
from shapely.geometry import Polygon, Point, box, LineString
from shapely.ops import unary_union
pads = json.load(open(sys.argv[1]))
CL = 0.28          # copper-to-foreign clearance used when cutting (zone clearance 0.2 + margin)
def R(x0, y0, x1, y1): return box(x0, y0, x1, y1)
def shape(p):
    if p.get('seg'):
        return LineString(p['seg']).buffer(p['w'] / 2)
    if p.get('via'):
        return Point(p['pos']).buffer(p['hole'])
    if p['num'] == 'NPTH':
        return Point(p['pos']).buffer(p['hole'] / 2 + 0.1)
    g = unary_union([Polygon(o) for o in p['poly'] if len(o) >= 3])
    if p['hole']: g = g.union(Point(p['pos']).buffer(p['hole'] / 2))
    return g
SEEDS = [
    # net, layer, seed shapes
    ('/BB_SW1', 'F', [R(24.45, 57.0, 31.3, 65.15), R(27.5, 64.0, 31.3, 66.8), R(31.0, 64.2, 33.1, 65.3)]),
    ('/BB_SW2', 'F', [R(34.7, 57.0, 37.8, 64.15), R(36.05, 64.0, 36.42, 66.4), R(37.5, 62.6, 39.4, 63.6)]),
    ('/VSYS_IN', 'F', [R(18.0, 64.0, 26.25, 70.0), R(24.9, 69.0, 26.2, 73.2), R(18.0, 69.0, 19.4, 72.4)]),
    ('/BATT_F2', 'F', [R(19.0, 76.5, 25.0, 85.6)]),
    ('/BATT_RAW', 'F', [R(13.2, 83.7, 16.4, 85.5), R(15.2, 83.7, 16.3, 91.3), R(15.2, 89.6, 32.6, 91.3), R(30.4, 86.8, 32.6, 91.3)]),
    ('/BATT_RAW', 'B', [R(13.2, 83.7, 16.4, 85.5), R(15.2, 83.7, 16.3, 91.3), R(15.2, 89.6, 32.6, 91.3), R(30.4, 86.8, 32.6, 91.3)]),
    ('/BB_VOUT', 'F', [R(36.45, 67.7, 36.8, 69.3), R(36.45, 69.1, 48.7, 71.6), R(36.95, 69.0, 38.6, 77.5)]),
    ('/+5V_SYS', 'F', [R(40.0, 74.6, 43.2, 87.0)]),
    ('/+5V_SYS', 'B', [R(40.0, 74.6, 43.2, 87.0)]),
    ('GND', 'F', [R(35.2, 67.7, 35.55, 69.3), R(34.9, 68.9, 36.25, 77.5)]),          # boost PGND under the output caps
    ('GND', 'F', [R(27.3, 67.2, 30.2, 73.2)]),                                    # buck leg GND: Q12 source -> C50/C49
]
out = []
for net, layer, seeds in SEEDS:
    own = [shape(p) for p in pads if p['net'] == net and p['layer'] == layer and p['ref'] not in ('track',)]
    foreign = [shape(p) for p in pads if p['layer'] == layer and (p['net'] != net or p['num'] == 'NPTH')]
    seed = unary_union(seeds)
    fz = unary_union([f.buffer(CL) for f in foreign if f.intersects(seed.buffer(1.0))])
    g = seed.difference(fz)
    ownu = unary_union([o for o in own if o.intersects(seed.buffer(0.3))])
    g = g.union(ownu.intersection(seed.buffer(0.01)) if False else g)
    parts = list(g.geoms) if g.geom_type == 'MultiPolygon' else [g]
    keep = [q for q in parts if q.area > 0.05 and q.buffer(0.05).intersects(ownu)]
    for q in keep:
        q = q.simplify(0.01)
        out.append(dict(net=net, layer=layer, pts=[(round(x, 3), round(y, 3)) for x, y in q.exterior.coords][:-1],
                        holes=[[(round(x, 3), round(y, 3)) for x, y in h.coords][:-1] for h in q.interiors]))
        touched = sorted({f"{p['ref']}.{p['num']}" for p in pads if p['net'] == net and p['layer'] == layer and p['ref'] not in ('track','via') and shape(p).intersects(q.buffer(0.05))})
        print(net, layer, f'area {q.area:.1f}', touched)
    dropped = [round(q.area, 2) for q in parts if q not in keep]
    if dropped: print('   dropped islands', dropped)
json.dump(out, open(sys.argv[2], 'w'))
