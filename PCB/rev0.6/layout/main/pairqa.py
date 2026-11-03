"""pairqa.py board: USB_UP pair lengths/widths/layers/vias, In1 tracks crossing under it, +5V_AON widths."""
import pcbnew, collections, sys
from shapely.geometry import LineString
from shapely.ops import unary_union
T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
L = collections.defaultdict(float); W = collections.defaultdict(set); lay = collections.defaultdict(set); segs = []; v = collections.Counter()
for t in b.GetTracks():
    n = t.GetNetname()
    if n in ('/USB_UP_DP', '/USB_UP_DM'):
        if isinstance(t, pcbnew.PCB_VIA): v[n] += 1; continue
        L[n] += T(t.GetLength()); W[n].add(round(T(t.GetWidth()), 2)); lay[n].add(t.GetLayerName())
        if t.GetLayer() == pcbnew.F_Cu: segs.append(LineString([(T(t.GetStart().x), T(t.GetStart().y)), (T(t.GetEnd().x), T(t.GetEnd().y))]))
for n in L: print(n, round(L[n], 2), W[n], lay[n], 'vias', v[n])
corr = unary_union(segs).buffer(0.6)
cross = collections.Counter()
for t in b.GetTracks():
    if isinstance(t, pcbnew.PCB_VIA) or t.GetLayer() != pcbnew.In1_Cu: continue
    g = LineString([(T(t.GetStart().x), T(t.GetStart().y)), (T(t.GetEnd().x), T(t.GetEnd().y))])
    if g.length > 0 and g.intersects(corr): cross[t.GetNetname()] += 1
print('In1 tracks under the pair:', dict(cross))
w = collections.Counter()
for t in b.GetTracks():
    if t.GetNetname() == '/+5V_AON' and not isinstance(t, pcbnew.PCB_VIA): w[round(T(t.GetWidth()), 2)] += T(t.GetLength())
print('+5V_AON widths (mm: length)', {k: round(x, 1) for k, x in sorted(w.items())})
