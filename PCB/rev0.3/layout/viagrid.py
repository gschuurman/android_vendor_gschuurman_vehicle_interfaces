"""Host side: stitching via positions inside chosen power polygons. usage: viagrid.py pads.json ppoly.json out.json"""
import json, sys
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
pads = json.load(open(sys.argv[1])); polys = json.load(open(sys.argv[2]))
STITCH = {('GND', 'F'): 0.8, ('/+5V_SYS', 'F'): 1.2, ('/BATT_RAW', 'F'): 1.3}
VR = 0.3
smd = unary_union([unary_union([Polygon(o) for o in p['poly'] if len(o) >= 3]) for p in pads if p['poly'] and p['layer'] == 'F'])
holes = unary_union([Point(p['pos']).buffer(p['hole'] / 2) for p in pads if p['hole'] and not p.get('via')])
vias = []
for z in polys:
    pitch = STITCH.get((z['net'], z['layer']))
    if not pitch: continue
    g = Polygon(z['pts'], z['holes']).buffer(-(VR + 0.08))
    if g.is_empty: continue
    x0, y0, x1, y1 = g.bounds
    y = y0
    while y <= y1:
        x = x0
        while x <= x1:
            pt = Point(x, y)
            if g.contains(pt) and pt.distance(smd) > VR + 0.15 and pt.distance(holes) > VR + 0.35 and all(pt.distance(Point(v[1], v[2])) >= pitch - 1e-6 for v in vias):
                vias.append((z['net'], round(x, 2), round(y, 2)))
            x += 0.25
        y += 0.25
print(len(vias), 'vias'); json.dump(vias, open(sys.argv[3], 'w'))
