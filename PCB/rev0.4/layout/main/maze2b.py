"""Rip-up-and-reroute finisher. usage: maze2.py state.json out.json
Connects every non-GND net into one piece (pads + zones + copper), ripping autorouted tracks of other nets
when a connection has no free path. Layers F/In2/B on a 0.1 mm grid, clearances on a 0.05 mm raster."""
import json, sys, heapq, fnmatch, time, math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from collections import defaultdict
st = json.load(open(sys.argv[1]))
import os
W, H = float(os.environ.get("MW", 100)), float(os.environ.get("MH", 100))
RES = 0.05; NX, NY = int(W / RES) + 1, int(H / RES) + 1
import os
STEP = int(os.environ.get("STEP", 2)); GX, GY = (NX + STEP - 1) // STEP, (NY + STEP - 1) // STEP
LAYERS = os.environ.get('LAYERS', 'F,In2,B').split(','); LI = {l: i for i, l in enumerate(LAYERS)}
CLS = {'Default': (0.2, 0.13), 'HDMI': (0.2, 0.1), 'USB': (0.25, 0.15), 'Power': (0.3, 0.13), 'HighCurrent': (0.6, 0.15)}
PATTERNS = [('HDMI', '/HDMI_*'), ('USB', '*_DP'), ('USB', '*_DM'), ('USB', '*_DN'), ('USB', '*USBDP*'), ('USB', '*USBDM*'),
            ('HighCurrent', '/VSYS_IN'), ('HighCurrent', '/+5V_SYS'),
            ('Power', '/BATT_RAW'), ('Power', '/BATT_F2'), ('Power', '/BB_SW*'), ('Power', '/BB_VOUT'),
            ('Power', '/+5V_USB'), ('Power', '/EXT?_VBUS'), ('Power', '/SDR_VBUS'), ('Power', '/USBP_*'), ('Power', '/+5V_AON'),
            ('Power', '/+3V3_*'), ('Power', '/+1V1_MCU'), ('Power', '/BUCK_SW'), ('Power', '/VIM3_5V'), ('Power', '/BATT_F'),
            ('Power', '/HUB*_3V3'), ('Power', '/GNSS_VCCRF')]
CLS['Narrow'] = (0.3, 0.15)   # sense / low-current legs of high-current nets
NARROW = set(filter(None, os.environ.get('NARROW', '').split(',')))
def netclass(n):
    if n in NARROW: return 'Narrow'
    for c, p in PATTERNS:
        if fnmatch.fnmatchcase(n, p): return c
    return 'Default'
VIA_R, EDGE, M = 0.225, 0.3, 0.05
nets = sorted({it['net'] for it in st['items'] if it['net']}); NID = {n: i + 1 for i, n in enumerate(nets)}; NAME = {i: n for n, i in NID.items()}
GRP = np.zeros(len(nets) + 2, np.int8)
for n, i in NID.items(): GRP[i] = 0 if CLS[netclass(n)][1] <= 0.13 else 1
def px(pts): return [(x / RES, y / RES) for x, y in pts]
def draw(img, kind, data, val):
    d = ImageDraw.Draw(img)
    if kind == 'poly':
        for pts, hs in data:
            if len(pts) >= 3: d.polygon(px(pts), fill=val)
            for h in hs:
                if len(h) >= 3: d.polygon(px(h), fill=0)
    elif kind in ('circle', 'hole'):
        (x, y), r = data; d.ellipse([(x - r) / RES, (y - r) / RES, (x + r) / RES, (y + r) / RES], fill=val)
    elif kind == 'seg':
        a, c, r = data; g = LineString([a, c]).buffer(r, 8) if tuple(a) != tuple(c) else Point(a).buffer(r, 8)
        d.polygon(px(list(g.exterior.coords)), fill=val)
# ---------------- fixed copper
FIXI = {l: Image.new('I', (NX, NY), 0) for l in LAYERS}
ZONI = {l: Image.new('1', (NX, NY), 0) for l in LAYERS}
KTI = {l: Image.new('1', (NX, NY), 0) for l in LAYERS}
HOI = Image.new('I', (NX, NY), 0)
links = defaultdict(list)          # net id -> [(x,y)] where layers are joined (THT pads, fixed vias)
RT = {}                            # routable items: id -> dict(net, kind, layer, data)
for it in st['items']:
    v = NID.get(it['net'], 0) or -1
    if it['ref'] == 'keepout':
        if it['keepout']['tracks']:
            for ln, kind, data in it['g']:
                for l in it['layers']:
                    if l in KTI: draw(KTI[l], kind, data, 1)
        continue
    if it['ref'] in ('track', 'via') and not it.get('locked') and it['net'] and it['net'] != 'GND':
        for ln, kind, data in it['g']:
            if kind == 'seg': RT[it['id']] = dict(net=v, kind='seg', layer=ln, data=data)
            elif kind == 'circle': RT[it['id']] = dict(net=v, kind='via', data=data); break
        continue
    for ln, kind, data in it['g']:
        if kind == 'hole':
            draw(HOI, kind, data, v)
            if v > 0: links[v].append(tuple(data[0]))
            continue
        if ln in FIXI: draw(FIXI[ln], kind, data, v)
        if it['ref'] == 'zone' and ln in ZONI: draw(ZONI[ln], kind, data, 1)
    if it['ref'] == 'via':
        draw(HOI, 'hole', (tuple(it['g'][0][2][0]), 0.15), v)
        if v > 0: links[v].append(tuple(it['g'][0][2][0]))
FIX = {l: np.array(FIXI[l], np.int32) for l in LAYERS}
ZON = {l: np.array(ZONI[l], bool) for l in LAYERS}
KT = {l: np.array(KTI[l], bool) for l in LAYERS}
HO = np.array(HOI, np.int32)
# no routing / vias under fine-pitch IC bodies
fp = defaultdict(list)
for it in st['items']:
    if '.' in it['ref'] and it['ref'][0] == 'U':
        for ln, kind, data in it['g']:
            if ln == 'F' and kind == 'poly':
                for pts, hs in data:
                    if len(pts) >= 3: fp[it['ref'].split('.')[0]].append(Polygon(pts))
UI = Image.new('1', (NX, NY), 0)
for ref, ps in fp.items():
    if len(ps) < 16: continue
    hull = unary_union(ps).convex_hull.buffer(-0.45)
    if not hull.is_empty and hull.geom_type == 'Polygon': ImageDraw.Draw(UI).polygon(px(list(hull.exterior.coords)), fill=1)
UNDER = np.array(UI, bool); KT['F'] |= UNDER
yy, xx = np.mgrid[0:NY, 0:NX]
EDGEM = np.minimum.reduce([xx * RES, (NX - 1 - xx) * RES, yy * RES, (NY - 1 - yy) * RES])
del yy, xx
# ---------------- routable copper raster (item index per pixel)
RTID = {l: np.zeros((NY, NX), np.int32) for l in LAYERS}
IDX = {}; KEYS = [None]; NETOF = [0]
def idx_of(k):
    if k not in IDX: IDX[k] = len(KEYS); KEYS.append(k); NETOF.append(RT[k]['net'])
    return IDX[k]
def paint(k, val=None):
    it = RT[k]; i = idx_of(k) if val is None else val
    if it['kind'] == 'seg':
        a, c, r = it['data']; l = it['layer']
        g = LineString([a, c]).buffer(r, 8) if tuple(a) != tuple(c) else Point(a).buffer(r, 8)
        x0, y0, x1, y1 = [int(v / RES) for v in g.bounds]; x0 -= 2; y0 -= 2; x1 += 3; y1 += 3
        x0, y0 = max(x0, 0), max(y0, 0)
        im = Image.new('1', (x1 - x0, y1 - y0), 0)
        ImageDraw.Draw(im).polygon([((x - x0 * RES) / RES, (y - y0 * RES) / RES) for x, y in g.exterior.coords], fill=1)
        m = np.array(im, bool); sub = RTID[l][y0:y0 + m.shape[0], x0:x0 + m.shape[1]]; m = m[:sub.shape[0], :sub.shape[1]]
        sub[m] = i
    else:
        (x, y), r = it['data']
        x0, y0 = int((x - r) / RES) - 1, int((y - r) / RES) - 1; n = int(2 * r / RES) + 4
        im = Image.new('1', (n, n), 0); ImageDraw.Draw(im).ellipse([(x - r) / RES - x0, (y - r) / RES - y0, (x + r) / RES - x0, (y + r) / RES - y0], fill=1)
        m = np.array(im, bool)
        for l in LAYERS:
            sub = RTID[l][y0:y0 + n, x0:x0 + n]; sub[m[:sub.shape[0], :sub.shape[1]]] = i
def bbox_px(it):
    if it['kind'] == 'seg':
        a, c, r = it['data']; return min(a[0], c[0]) - r, min(a[1], c[1]) - r, max(a[0], c[0]) + r, max(a[1], c[1]) + r
    (x, y), r = it['data']; return x - r, y - r, x + r, y + r
for k in list(RT): paint(k)
NETARR = lambda: np.array(NETOF, np.int32)
def remove(k):
    it = RT[k]; i = IDX[k]
    for l in (LAYERS if it['kind'] == 'via' else [it['layer']]):
        RTID[l][RTID[l] == i] = 0
    del RT[k]
    # repaint same-net neighbours that may have lost shared pixels
    b0 = bbox_px(it)
    for k2, it2 in RT.items():
        if it2['net'] != it['net']: continue
        b = bbox_px(it2)
        if b[0] <= b0[2] and b[2] >= b0[0] and b[1] <= b0[3] and b[3] >= b0[1]: paint(k2)
# ---------------- connectivity
def components(nid):
    na = NETARR()
    labs = {}; offs = {}; tot = 0
    for l in LAYERS:
        own = (FIX[l] == nid) | (na[RTID[l]] == nid)
        lab, n = ndimage.label(own, structure=np.ones((3, 3)))
        labs[l] = lab; offs[l] = tot; tot += n
    parent = list(range(tot + 1))
    def find(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    def union(a, b): parent[find(a)] = find(b)
    pts = list(links[nid]) + [RT[k]['data'][0] for k in RT if RT[k]['net'] == nid and RT[k]['kind'] == 'via']
    for (x, y) in pts:
        ix, iy = int(round(x / RES)), int(round(y / RES))
        ls = [offs[l] + labs[l][iy, ix] for l in LAYERS if labs[l][iy, ix]]
        for a in ls[1:]: union(ls[0], a)
    term = set()
    for l in LAYERS:
        m = (FIX[l] == nid) & (labs[l] > 0)
        for v in np.unique(labs[l][m]): term.add(find(offs[l] + v))
    comps = defaultdict(list)
    for l in LAYERS:
        sub = labs[l][::STEP, ::STEP]
        ys, xs = np.nonzero(sub)
        roots = [find(offs[l] + v) for v in sub[ys, xs]]
        for r, y, x in zip(roots, ys, xs): comps[r].append((LI[l], y, x))
    good = {r: c for r, c in comps.items() if r in term}
    dangling = {r for r in comps if r not in term}
    return list(good.values()), labs, offs, find, dangling
# ---------------- costs in a window
def masks(nid, w, win):
    x0, y0, x1, y1 = win          # coarse-grid window
    X0, Y0, X1, Y1 = x0 * STEP, y0 * STEP, x1 * STEP, y1 * STEP
    pad = 30                       # raster px of context for the distance transforms
    a0, b0, a1, b1 = max(X0 - pad, 0), max(Y0 - pad, 0), min(X1 + pad, NX), min(Y1 + pad, NY)
    na = NETARR(); own = CLS[netclass(NAME[nid])][1]
    hard_tr, soft_tr, hard_v, soft_v = {}, {}, None, None
    r = w / 2
    def dt(m): return ndimage.distance_transform_edt(~m) * RES if m.any() else np.full(m.shape, 1e9)
    for l in LAYERS:
        F = FIX[l][b0:b1, a0:a1]; Z = ZON[l][b0:b1, a0:a1]; Rn = na[RTID[l][b0:b1, a0:a1]]
        ff = (F != 0) & (F != nid); fz = ff & Z; fh = ff & ~Z
        fr = (Rn != 0) & (Rn != nid)
        g1h = fh & (GRP[np.clip(F, 0, None)] == 1); g0h = fh & ~g1h
        g1r = fr & (GRP[Rn] == 1); g0r = fr & ~g1r
        dh0, dh1, dz, dr0, dr1 = dt(g0h), dt(g1h), dt(fz), dt(g0r), dt(g1r)
        c0, c1 = max(own, 0.13) + M, max(own, 0.15) + M
        def hard(rr): return (dh0 < rr + c0) | (dh1 < rr + c1) | (dz < rr + 0.2 + M)
        def soft(rr): return (dr0 < rr + c0) | (dr1 < rr + c1)
        e = EDGEM[b0:b1, a0:a1]
        ht = hard(r) | KT[l][b0:b1, a0:a1] | (e < EDGE + r + 0.05)
        sl = (slice(Y0 - b0, Y1 - b0, STEP), slice(X0 - a0, X1 - a0, STEP))
        hard_tr[l] = ht[sl]; soft_tr[l] = soft(r)[sl]
        hv, sv = hard(VIA_R + 0.03), soft(VIA_R + 0.03)
        hard_v = hv[sl] if hard_v is None else hard_v | hv[sl]
        soft_v = sv[sl] if soft_v is None else soft_v | sv[sl]
    hf = (HO[b0:b1, a0:a1] != 0).copy()
    for k, itv in RT.items():          # every via hole, own net included (hole-to-hole spacing)
        if itv['kind'] != 'via': continue
        (vx, vy), _ = itv['data']; cx, cy = vx / RES - a0, vy / RES - b0
        if -20 < cx < a1 - a0 + 20 and -20 < cy < b1 - b0 + 20:
            iy0, iy1 = int(max(cy - 3, 0)), int(min(cy + 4, b1 - b0)); ix0, ix1 = int(max(cx - 3, 0)), int(min(cx + 4, a1 - a0))
            hf[iy0:iy1, ix0:ix1] = True
    sl = (slice(Y0 - b0, Y1 - b0, STEP), slice(X0 - a0, X1 - a0, STEP))
    hard_v = hard_v | (dt(hf) < 0.4)[sl] | UNDER[b0:b1, a0:a1][sl] | (EDGEM[b0:b1, a0:a1] < EDGE + VIA_R + 0.1)[sl]
    return hard_tr, soft_tr, hard_v, soft_v
DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
VIACOST = 20.0
VMAX = int(os.environ.get("VMAX", 10))
def astar(src, dst, mk, win, pen):
    hard_tr, soft_tr, hard_v, soft_v = mk; x0, y0, x1, y1 = win
    HT = [hard_tr[l] for l in LAYERS]; ST = [soft_tr[l] for l in LAYERS]
    tset = set(dst)
    d = np.array([(c[1], c[2]) for c in dst]); tree = cKDTree(d)
    def h(y, x): return tree.query((y, x))[0] * 0.999
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
            return path[::-1], gc
        n += 1
        if n > 1_500_000: return None, None
        l, y, x = cur; ly, lx = y - y0, x - x0
        for dx, dy, c in DIRS:
            nx_, ny_ = lx + dx, ly + dy
            if not (0 <= nx_ < x1 - x0 and 0 <= ny_ < y1 - y0): continue
            nb = (l, ny_ + y0, nx_ + x0); tgt = nb in tset
            if not tgt:
                if HT[l][ny_, nx_]: continue
                if dx and dy and (HT[l][ly, nx_] or HT[l][ny_, lx]): continue
            cc = c + (pen if (not tgt and ST[l][ny_, nx_]) else 0)
            ng = gc + cc
            if ng < g.get(nb, 1e18):
                g[nb] = ng; prev[nb] = cur; heapq.heappush(pq, (ng + h(nb[1], nb[2]), ng, nb))
        if not hard_v[ly, lx]:
            for l2 in range(len(LAYERS)):
                if l2 == l: continue
                nb = (l2, y, x)
                if HT[l2][ly, lx] and nb not in tset: continue
                ng = gc + VIACOST + (pen if soft_v[ly, lx] else 0)
                if ng < g.get(nb, 1e18):
                    g[nb] = ng; prev[nb] = cur; heapq.heappush(pq, (ng + h(y, x), ng, nb))
    return None, None
def to_items(path, w, nid):
    out = []
    def xy(c): return (round(c[2] * STEP * RES, 3), round(c[1] * STEP * RES, 3))
    s0 = path[0]; pd = None
    for a, b in zip(path, path[1:]):
        if a[0] != b[0]:
            if s0 != a: out.append(dict(net=nid, kind='seg', layer=LAYERS[a[0]], data=(xy(s0), xy(a), w / 2)))
            out.append(dict(net=nid, kind='via', data=(xy(a), VIA_R))); s0 = b; pd = None; continue
        dd = (b[1] - a[1], b[2] - a[2])
        if pd is not None and dd != pd:
            out.append(dict(net=nid, kind='seg', layer=LAYERS[a[0]], data=(xy(s0), xy(a), w / 2))); s0 = a
        pd = dd
    if s0 != path[-1]: out.append(dict(net=nid, kind='seg', layer=LAYERS[path[-1][0]], data=(xy(s0), xy(path[-1]), w / 2)))
    return out
def victims(new, nid):
    """routable items of other nets that the new copper would violate"""
    na = NETARR(); hit = set(); own = CLS[netclass(NAME[nid])][1]
    for it in new:
        cl = max(own, 0.15) + M
        if it['kind'] == 'seg':
            a, c, r = it['data']; ls = [it['layer']]; g = LineString([a, c]).buffer(r + cl) if a != c else Point(a).buffer(r + cl)
        else:
            (x, y), r = it['data']; ls = LAYERS; g = Point(x, y).buffer(r + cl)
        im = Image.new('1', (NX, NY), 0); ImageDraw.Draw(im).polygon(px(list(g.exterior.coords)), fill=1)
        m = np.array(im, bool)
        for l in ls:
            ids = np.unique(RTID[l][m]); hit |= {int(i) for i in ids if i and na[i] != nid and na[i] != 0}
        if it['kind'] == 'via':   # hole spacing to other vias is checked on all layers already
            pass
    return {KEYS[i] for i in hit if KEYS[i] in RT}
newk = [0]
def add(it):
    newk[0] += 1; k = f'n{newk[0]}'; RT[k] = it; paint(k); return k
removed_orig = set()
work = [NID[n] for n in nets if n != 'GND']
hist = defaultdict(int); tries = defaultdict(int); failed = []
t0 = time.time(); it_n = 0
PRIO = os.environ.get('PRIO', '')
if PRIO:
    pn = {NID[it['net']] for it in st['items'] if it['net'] in NID and it['ref'].split('.')[0] in PRIO.split(',')}
    work.sort(key=lambda n: 0 if n in pn else 1)
queue = list(work)
while queue and it_n < 1500 and time.time() - t0 < 3000:
    nid = queue.pop(0)
    comps, labs, offs, find, dang = components(nid)
    if len(comps) <= 1: continue
    it_n += 1; tries[nid] += 1
    if tries[nid] > 25: failed.append(NAME[nid]); continue
    # biggest component vs its nearest other component
    comps.sort(key=len, reverse=True)
    A_ = comps[0]; ta = cKDTree(np.array([(c[1], c[2]) for c in A_]))
    best = None
    for C in comps[1:]:
        dd, ii = ta.query(np.array([(c[1], c[2]) for c in C]))
        j = int(np.argmin(dd))
        if best is None or dd[j] < best[0]: best = (dd[j], C, j, int(ii[j]))
    _, B_, j, i = best
    pa, pb = A_[i], B_[j]
    w = CLS[netclass(NAME[nid])][0]
    path = None
    for marg, pen in ((60, None), (140, None), (140, 'soft')) + tuple((int(m), None) for m in os.environ.get('WINX', '').split(',') if m):
        x0 = max(min(pa[2], pb[2]) - marg, 0); x1 = min(max(pa[2], pb[2]) + marg, GX - 1)
        y0 = max(min(pa[1], pb[1]) - marg, 0); y1 = min(max(pa[1], pb[1]) + marg, GY - 1)
        win = (x0, y0, x1, y1)
        src = [c for c in A_ if x0 <= c[2] < x1 and y0 <= c[1] < y1]
        dst = [c for c in B_ if x0 <= c[2] < x1 and y0 <= c[1] < y1]
        mk = masks(nid, w, win)
        if pen is None:
            mk2 = ({l: mk[0][l] | mk[1][l] for l in LAYERS}, mk[1], mk[2] | mk[3], mk[3])
            path, cost = astar(src, dst, mk2, win, 0)
        else:
            path, cost = astar(src, dst, mk, win, 80.0 * (1 + hist[nid]))
        if path: break
    if not path:
        failed.append(NAME[nid]); print('FAIL', NAME[nid], flush=True); continue
    new = to_items(path, w, nid)
    vic = victims(new, nid)
    if len(vic) > VMAX:
        failed.append(NAME[nid]); print('FAIL too many victims', NAME[nid], len(vic), flush=True); continue
    for k in vic:
        vn = RT[k]['net']; hist[vn] += 1
        if not k.startswith('n'): removed_orig.add(k)
        remove(k)
        if vn not in queue: queue.append(vn)
    for itm in new: add(itm)
    queue.insert(0, nid)          # finish this net first
    print(f'{it_n} {NAME[nid]} comps={len(comps)} segs={len(new)} ripped={len(vic)} t={time.time()-t0:.0f}', flush=True)
# remove dangling routable islands (no pad/zone)
for n in nets:
    if n == 'GND': continue
    nid = NID[n]; comps, labs, offs, find, dang = components(nid)
    if not dang: continue
    for k in [k for k in RT if RT[k]['net'] == nid]:
        itm = RT[k]
        if itm['kind'] == 'seg':
            (x, y) = itm['data'][0]; l = itm['layer']
        else:
            (x, y) = itm['data'][0]; l = 'F'
        ix, iy = int(round(x / RES)), int(round(y / RES))
        lab = labs[l][iy, ix]
        if lab and find(offs[l] + lab) in dang:
            if not k.startswith('n'): removed_orig.add(k)
            remove(k)
left = [n for n in nets if n != 'GND' and len(components(NID[n])[0]) > 1]
out = dict(removed=sorted(removed_orig), added=[dict(net=NAME[v['net']], kind=v['kind'], layer=v.get('layer'), data=v['data']) for k, v in RT.items() if k.startswith('n')],
           left=left)
json.dump(out, open(sys.argv[2], 'w'))
print('iterations', it_n, 'removed', len(removed_orig), 'added', len(out['added']), 'nets still split', left)
