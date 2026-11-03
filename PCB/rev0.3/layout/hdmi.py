"""Route HDMI J13 (20P FFC in) -> J14 (display FPC). Legs on F.Cu, runs on B.Cu (over the In2 GND pour),
intra-pair lengths matched exactly with a small bump on the shorter trace. All tracks are locked."""
import pcbnew, sys, math
MM = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))
b = pcbnew.LoadBoard(sys.argv[1])
out = sys.argv[2]
nets = {n: b.FindNet(n) for n in []}
def N(name): return b.FindNet(name)
W_SIG = 0.2
VIA_D, VIA_H = 0.6, 0.3
tracks = []
def trk(x0, y0, x1, y1, layer, net, w=W_SIG):
    t = pcbnew.PCB_TRACK(b); t.SetStart(V(x0, y0)); t.SetEnd(V(x1, y1)); t.SetLayer(layer); t.SetWidth(MM(w))
    t.SetNet(N(net)); t.SetLocked(True); b.Add(t); tracks.append((net, math.hypot(x1 - x0, y1 - y0)))
def via(x, y, net, d=VIA_D, h=VIA_H):
    v = pcbnew.PCB_VIA(b); v.SetPosition(V(x, y)); v.SetWidth(MM(d)); v.SetDrill(MM(h)); v.SetNet(N(net)); v.SetLocked(True); b.Add(v)
def pad(ref, num):
    f = b.FindFootprintByReference(ref)
    for p in f.Pads():
        if p.GetNumber() == num: return p
def pxy(p): q = p.GetPosition(); return q.x / 1e6, q.y / 1e6

# signal list: (J13 pin, J14 pin, net)
PAIRS = [(('1', '11'), ('3', '13'), 'D2'), (('4', '14'), ('6', '16'), 'D1'), (('7', '17'), ('9', '19'), 'D0'), (('10', '20'), ('12', '22'), 'CLK')]
SINGLES = [('13', '23'), ('15', '24'), ('16', '25'), ('18', '27'), ('19', '28')]
y13 = pxy(pad('J13', '1'))[1]; y14 = pxy(pad('J14', '11'))[1]
Y0 = y13 + 1.6              # first run depth, just below the HDMI socket pads
def route(p13, p14, y):
    a, c = pad('J13', p13), pad('J14', p14)
    net = a.GetNetname(); assert net == c.GetNetname(), (p13, p14)
    (xa, ya), (xc, yc) = pxy(a), pxy(c)
    trk(xa, ya, xa, y, pcbnew.F_Cu, net); via(xa, y, net)
    trk(xa, y, xc, y, pcbnew.B_Cu, net)
    via(xc, y, net); trk(xc, y, xc, yc, pcbnew.F_Cu, net)
# J13 pins run left->right, J14 right->left: the runs nest. Span shrinks 1 mm per pin step, so each trace sits
# 0.5 mm deeper per pin step: P/N (2 pins apart) 1.0 mm apart, pairs (3 pins apart) 1.5 mm apart -> all equal length.
for i, (P, Nn, name) in enumerate(PAIRS):
    route(P[0], P[1], Y0 + 1.5 * i)
    route(Nn[0], Nn[1], Y0 + 1.5 * i + 1.0)
y = Y0 + 6.0
for s_ in SINGLES:
    route(s_[0], s_[1], y); y += 0.5
depth_end = y
# GND pins of both connectors: via just above the pad (under the connector body, tented)
lastlow = set()
for ref in ('J13', 'J14'):
    for p in sorted(b.FindFootprintByReference(ref).Pads(), key=lambda q: q.GetPosition().x):
        if p.GetNetname() == 'GND' and p.GetNumber() != 'MP':
            x, yy = pxy(p); top = yy - p.GetSizeY() / 2e6
            off = 1.0 if (ref, round(x - 0.5, 3)) in lastlow else 0.35   # stagger vias on neighbouring GND pins
            if off == 0.35: lastlow.add((ref, round(x, 3)))
            trk(x, yy, x, top - off, pcbnew.F_Cu, 'GND', 0.25); via(x, top - off, 'GND')
L = {}
for n, l in tracks: L[n] = L.get(n, 0) + l
for P, Nn, name in PAIRS:
    lp, ln = L['/HDMI_%sP' % name], L['/HDMI_%sN' % name]
    print(f'{name}: P {lp:.3f}  N {ln:.3f}  skew {abs(lp-ln):.3f} mm')
tm = [L[k] for k in L if 'HDMI_D' in k or 'HDMI_CLK' in k]
print(f'TMDS spread {max(tm)-min(tm):.2f} mm; runs end at y={depth_end:.2f}')
b.Save(out)
