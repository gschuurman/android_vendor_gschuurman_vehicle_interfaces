"""Host-side grid maze router for the connections the autorouter left open.
usage: maze.py state.json out.json [W H]
Layers F, In2, B (In1 is the GND plane). Grid 0.1 mm for routing, 0.05 mm raster for clearances."""
import json, sys, heapq, math, fnmatch, time
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely.geometry import Polygon, Point, LineString
st = json.load(open(sys.argv[1]))
W, H = (float(sys.argv[3]), float(sys.argv[4])) if len(sys.argv) > 4 else (109.0, 92.0)
RES = 0.05; NX, NY = int(W / RES) + 1, int(H / RES) + 1
LAYERS = ['F', 'In2', 'B']
CLS = {'Default': (0.2, 0.13), 'HDMI': (0.2, 0.1), 'USB': (0.25, 0.15), 'Power': (0.3, 0.13), 'HighCurrent': (0.6, 0.15)}
PATTERNS = [('HDMI', '/HDMI_*'), ('USB', '*_DP'), ('USB', '*_DM'), ('USB', '*_DN'), ('USB', '*USBDP*'), ('USB', '*USBDM*'),
            ('HighCurrent', '/VSYS_IN'), ('HighCurrent', '/+5V_SYS'),
            ('Power', '/BATT_RAW'), ('Power', '/BATT_F2'), ('Power', '/BB_SW*'), ('Power', '/BB_VOUT'),
            ('Power', '/+5V_USB'), ('Power', '/EXT?_VBUS'), ('Power', '/SDR_VBUS'), ('Power', '/USBP_*'), ('Power', '/+5V_AON'),
            ('Power', '/+3V3_*'), ('Power', '/+1V1_MCU'), ('Power', '/BUCK_SW'), ('Power', '/VIM3_5V'), ('Power', '/BATT_F'),
            ('Power', '/HUB*_3V3'), ('Power', '/GNSS_VCCRF')]
def netclass(n):
    for c, p in PATTERNS:
        if fnmatch.fnmatchcase(n, p): return c
    return 'Default'
VIA_R, MAXCL, EDGE = 0.225, 0.2, 0.3
nets = sorted({it['net'] for it in st['items'] if it['net']}); NID = {n: i + 1 for i, n in enumerate(nets)}
lab = {l: Image.new('I', (NX, NY), 0) for l in LAYERS}
holes = Image.new('I', (NX, NY), 0)
keep_tr = {l: Image.new('1', (NX, NY), 0) for l in LAYERS}
def px(pts): return [(x / RES, y / RES) for x, y in pts]
def draw(img, kind, data, val):
    d = ImageDraw.Draw(img)
    if kind == 'poly':
        for pts, hs in data:
            if len(pts) >= 3: d.polygon(px(pts), fill=val)
            for h in hs:
                if len(h) >= 3: d.polygon(px(h), fill=0)
    elif kind == 'circle':
        (x, y), r = data; d.ellipse([(x - r) / RES, (y - r) / RES, (x + r) / RES, (y + r) / RES], fill=val)
    elif kind == 'seg':
        a, c, r = data; g = LineString([a, c]).buffer(r, 8) if a != c else Point(a).buffer(r, 8)
        d.polygon(px(list(g.exterior.coords)), fill=val)
    elif kind == 'hole':
        (x, y), r = data; d.ellipse([(x - r) / RES, (y - r) / RES, (x + r) / RES, (y + r) / RES], fill=val)
def add_item(it):
    v = NID.get(it['net'], 0) or -1          # no-net copper: foreign to everyone
    for ln, kind, data in it['g']:
        if it['ref'] == 'keepout':
            if it['keepout']['tracks']:
                for l in it['layers']:
                    if l in keep_tr: draw(keep_tr[l], kind, data, 1)
            continue
        if kind == 'hole': draw(holes, kind, data, v); continue
        if it['ref'] == 'via' and kind == 'circle' and ln == 'F': draw(holes, 'circle', (data[0], 0.1), v)
        if ln in lab: draw(lab[ln], kind, data, v)
for it in st['items']: add_item(it)
# no routing under fine-pitch IC bodies (between the pin rows and the exposed pad)
from shapely.ops import unary_union
from collections import defaultdict
fp = defaultdict(list)
for it in st['items']:
    if '.' in it['ref'] and it['ref'][0] == 'U':
        for ln, kind, data in it['g']:
            if ln == 'F' and kind == 'poly':
                for pts, hs in data:
                    if len(pts) >= 3: fp[it['ref'].split('.')[0]].append(Polygon(pts))
UNDER = Image.new('1', (NX, NY), 0)
for ref, ps in fp.items():
    if len(ps) < 16: continue
    hull = unary_union(ps).convex_hull.buffer(-0.45)
    if hull.is_empty or hull.geom_type != 'Polygon': continue
    ImageDraw.Draw(UNDER).polygon(px(list(hull.exterior.coords)), fill=1)
A = {l: np.array(lab[l], dtype=np.int32) for l in LAYERS}
HO = np.array(holes, dtype=np.int32)
KT = {l: np.array(keep_tr[l], dtype=bool) for l in LAYERS}
UNDERA = np.array(UNDER, dtype=bool); KT['F'] = KT['F'] | UNDERA
yy, xx = np.mgrid[0:NY, 0:NX]
edge = np.minimum.reduce([xx * RES, (NX - 1 - xx) * RES, yy * RES, (NY - 1 - yy) * RES])
STEP = 2   # routing grid = 2 raster px = 0.1 mm
GX, GY = (NX + STEP - 1) // STEP, (NY + STEP - 1) // STEP
GRP = {}       # net id -> clearance group: 0 = 0.13, 1 = 0.15, 2 = 0.2 (power zones)
for n, i in NID.items():
    c = CLS[netclass(n)][1]; GRP[i] = 0 if c <= 0.13 else 1
ZONEPX = {l: np.zeros((NY, NX), bool) for l in LAYERS}
for it in st['items']:
    if it['ref'] == 'zone':
        for ln, kind, data in it['g']:
            if ln in ZONEPX:
                im = Image.new('1', (NX, NY), 0); draw(im, kind, data, 1); ZONEPX[ln] |= np.array(im, dtype=bool)
M = 0.05
def blocked_for(net, w):
    """per layer: track-centre forbidden mask (coarse), and via-centre forbidden mask (coarse)."""
    nid = NID[net]; tr = {}; anyfor = None
    own = CLS[netclass(net)][1]
    g1 = np.vectorize(lambda v: GRP.get(v, 0) == 1, otypes=[bool])
    for l in LAYERS:
        foreign = (A[l] != 0) & (A[l] != nid)
        zf = foreign & ZONEPX[l]
        grp1 = foreign & ~zf & np.isin(A[l], [i for i, g in GRP.items() if g == 1])
        grp0 = foreign & ~zf & ~grp1
        d0 = ndimage.distance_transform_edt(~grp0) * RES if grp0.any() else np.full(grp0.shape, 1e9)
        d1 = ndimage.distance_transform_edt(~grp1) * RES if grp1.any() else np.full(grp0.shape, 1e9)
        d2 = ndimage.distance_transform_edt(~zf) * RES if zf.any() else np.full(grp0.shape, 1e9)
        def blk(r):
            return (d0 < r + max(own, 0.13) + M) | (d1 < r + max(own, 0.15) + M) | (d2 < r + 0.2 + M)
        tr[l] = (blk(w / 2) | KT[l] | (edge < EDGE + w / 2 + 0.05))[::STEP, ::STEP]
        vb = blk(VIA_R + 0.03)
        anyfor = vb if anyfor is None else (anyfor | vb)
    hf = (HO != 0)
    hd = ndimage.distance_transform_edt(~hf) * RES
    via = (anyfor | UNDERA | (hd < 0.4) | (edge < EDGE + VIA_R + 0.1))[::STEP, ::STEP]
    return tr, via
def cells_of(geoms):
    """coarse cells covered by an item's copper, per routable layer"""
    out = set()
    for ln, kind, data in geoms:
        if kind == 'hole': continue
        img = Image.new('1', (NX, NY), 0); draw(img, kind, data, 1)
        m = np.array(img, dtype=bool)[::STEP, ::STEP]
        ys, xs = np.nonzero(m)
        lays = LAYERS if ln == '*' else ([ln] if ln in LAYERS else [])
        for l in lays:
            li = LAYERS.index(l)
            for y, x in zip(ys, xs): out.add((li, y, x))
    return out
byid = {it['id']: it for it in st['items']}
DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
VIACOST = 25.0
def astar(src, dst, tr, via):
    dl = np.array([[d[1], d[2]] for d in dst]); 
    tset = set(dst)
    tx0, tx1, ty0, ty1 = dl[:, 1].min(), dl[:, 1].max(), dl[:, 0].min(), dl[:, 0].max()
    def h(y, x):
        dx = max(tx0 - x, 0, x - tx1); dy = max(ty0 - y, 0, y - ty1)
        return max(dx, dy) + 0.414 * min(dx, dy)
    g = {}; prev = {}; pq = []
    for s in src:
        g[s] = 0.0; heapq.heappush(pq, (h(s[1], s[2]), 0.0, s))
    n = 0
    while pq:
        f, gc, cur = heapq.heappop(pq)
        if gc > g.get(cur, 1e18): continue
        if cur in tset:
            path = [cur]
            while path[-1] in prev: path.append(prev[path[-1]])
            return path[::-1]
        n += 1
        if n > 3_000_000: return None
        l, y, x = cur
        for dx, dy, c in DIRS:
            nx_, ny_ = x + dx, y + dy
            if not (0 <= nx_ < GX and 0 <= ny_ < GY): continue
            nb = (l, ny_, nx_)
            if tr[LAYERS[l]][ny_, nx_] and nb not in tset: continue
            if dx and dy and (tr[LAYERS[l]][y, nx_] or tr[LAYERS[l]][ny_, x]) and nb not in tset: continue
            ng = gc + c
            if ng < g.get(nb, 1e18):
                g[nb] = ng; prev[nb] = cur; heapq.heappush(pq, (ng + h(ny_, nx_), ng, nb))
        if not via[y, x]:
            for l2 in range(3):
                if l2 == l: continue
                nb = (l2, y, x)
                if tr[LAYERS[l2]][y, x] and nb not in tset: continue
                ng = gc + VIACOST * abs(l2 - l) ** 0.5
                if ng < g.get(nb, 1e18):
                    g[nb] = ng; prev[nb] = cur; heapq.heappush(pq, (ng + h(y, x), ng, nb))
    return None
def to_geom(path, w):
    """path -> (tracks [(layer,(x0,y0),(x1,y1),w)], vias [(x,y)])"""
    tracks, vias = [], []
    def xy(c): return (round(c[2] * STEP * RES, 3), round(c[1] * STEP * RES, 3))
    seg_start = path[0]; prevd = None
    for a, b_ in zip(path, path[1:]):
        if a[0] != b_[0]:
            if seg_start != a: tracks.append((LAYERS[a[0]], xy(seg_start), xy(a), w))
            vias.append(xy(a)); seg_start = b_; prevd = None; continue
        d = (b_[1] - a[1], b_[2] - a[2])
        if prevd is not None and d != prevd:
            tracks.append((LAYERS[a[0]], xy(seg_start), xy(a), w)); seg_start = a
        prevd = d
    if seg_start != path[-1]: tracks.append((LAYERS[path[-1][0]], xy(seg_start), xy(path[-1]), w))
    return tracks, vias
results = []; failed = []; done_gnd = set(); t0 = time.time()
pairs = st['pairs']
order = sorted(range(len(pairs)), key=lambda i: 0)
for i in order:
    (ua, da), (ub, db) = pairs[i]
    ia, ib = byid.get(ua), byid.get(ub)
    net = (ia or ib or {}).get('net')
    if net == 'GND':
        # isolated GND copper: run a short stub to a via into the In1 plane
        it = ia if (ia and ia['ref'] not in ('zone',)) else ib
        if not it or it['ref'] == 'zone': failed.append((da, db, 'GND zone-zone')); continue
        key = it['id']
        if key in done_gnd: continue
        done_gnd.add(key)
        w = 0.25; tr, via = blocked_for(net, w)
        src = cells_of(it['g'])
        ys = [c[1] for c in src]; xs = [c[2] for c in src]
        y0, y1, x0, x1 = max(min(ys) - 40, 0), min(max(ys) + 40, GY - 1), max(min(xs) - 40, 0), min(max(xs) + 40, GX - 1)
        dst = set()
        for l in range(3):
            if not any(c[0] == l for c in src): continue
            sub = ~via[y0:y1 + 1, x0:x1 + 1] & ~tr[LAYERS[l]][y0:y1 + 1, x0:x1 + 1]
            for yy_, xx_ in zip(*np.nonzero(sub)): dst.add((l, yy_ + y0, xx_ + x0))
        dst -= src
        if not dst: failed.append((da, db, 'GND no via spot')); continue
        path = astar(src, dst, tr, via)
        if not path: failed.append((da, db, 'GND no path')); continue
        tracks, vias = to_geom(path, w)
        e = path[-1]; vias.append((round(e[2] * STEP * RES, 3), round(e[1] * STEP * RES, 3)))
    else:
        if not ia or not ib: failed.append((da, db, 'missing item')); continue
        w = CLS[netclass(net)][0]
        t0 = time.time()
        tr, via = blocked_for(net, w)
        src, dst = cells_of(ia['g']), cells_of(ib['g'])
        if not src or not dst: failed.append((da, db, 'no cells')); continue
        path = astar(src, dst, tr, via)
        if not path: failed.append((da, db, 'no path')); print('FAIL', net, da[:50], '|', db[:50]); continue
        tracks, vias = to_geom(path, w)
    if net == 'GND':
        results.append(dict(net=net, tracks=tracks, vias=vias))
        nid = NID[net]
        for l, a, c, ww in tracks:
            im = Image.fromarray(A[l]); draw(im, 'seg', (a, c, ww / 2), nid); A[l] = np.array(im, dtype=np.int32)
        for (x, y) in vias:
            for l in LAYERS:
                im = Image.fromarray(A[l]); draw(im, 'circle', ((x, y), VIA_R), nid); A[l] = np.array(im, dtype=np.int32)
            im = Image.fromarray(HO); draw(im, 'circle', ((x, y), 0.1), nid); HO = np.array(im, dtype=np.int32)
        print('ok GND stub', da[:40]); continue
    tracks, vias = to_geom(path, w)
    results.append(dict(net=net, tracks=tracks, vias=vias))
    # new copper becomes an obstacle for the following nets
    nid = NID[net]
    for l, a, c, ww in tracks:
        im = Image.fromarray(A[l]); draw(im, 'seg', (a, c, ww / 2), nid); A[l] = np.array(im, dtype=np.int32)
    for (x, y) in vias:
        for l in LAYERS:
            im = Image.fromarray(A[l]); draw(im, 'circle', ((x, y), VIA_R), nid); A[l] = np.array(im, dtype=np.int32)
        im = Image.fromarray(HO); draw(im, 'circle', ((x, y), 0.1), nid); HO = np.array(im, dtype=np.int32)
    print(f'ok {net} {len(tracks)} segs {len(vias)} vias {time.time()-t0:.1f}s', flush=True)
json.dump(dict(results=results, failed=failed), open(sys.argv[2], 'w'))
print('routed', len(results), 'failed', len(failed))
for f in failed: print('  ', f)
