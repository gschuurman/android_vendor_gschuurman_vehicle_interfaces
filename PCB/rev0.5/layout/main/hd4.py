"""Rev 0.4 HDMI: J13 (top edge, pads facing down) -> J14 (right edge, pads facing left), all on F.Cu over the
In1 GND plane, no vias. The traces nest as chamfered L shapes; J13 pitch steps equal J14 pitch steps, so the
spacing stays constant through the corners. P/N of each pair differ by 2.0 mm; the shorter N trace gets two
bumps into the 1 mm gap between P and N (where the GND pin sits). All tracks locked.
GND pins: J13 via above the pad (under the socket body), J14 via right of the pad (under the FPC socket)."""
import pcbnew, sys, math
MM = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))
b = pcbnew.LoadBoard(sys.argv[1])
def N(n): return b.FindNet(n)
L = {}
def trk(p, q, net, w=0.2, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(b); t.SetStart(V(*p)); t.SetEnd(V(*q)); t.SetLayer(layer); t.SetWidth(MM(w))
    t.SetNet(N(net)); t.SetLocked(True); b.Add(t); L[net] = L.get(net, 0) + math.dist(p, q)
def via(x, y, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(V(x, y)); v.SetWidth(MM(0.45)); v.SetDrill(MM(0.2)); v.SetNet(N(net)); v.SetLocked(True); b.Add(v)
def pads(ref): return b.FindFootprintByReference(ref).Pads()
def pxy(p): q = p.GetPosition(); return q.x / 1e6, q.y / 1e6
for t in list(b.GetTracks()):
    if 'HDMI' in t.GetNetname(): b.Remove(t)
a13 = {p.GetNetname(): p for p in pads('J13') if 'HDMI' in p.GetNetname()}
a14 = {p.GetNetname(): p for p in pads('J14') if 'HDMI' in p.GetNetname()}
C = 1.0
paths = {}
for net in a13:
    (xa, ya), (xc, yc) = pxy(a13[net]), pxy(a14[net])
    paths[net] = [(xa, ya), (xa, yc - C), (xa + C, yc), (xc, yc)]
def plen(pts): return sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
for nm in ('D0', 'D1', 'D2', 'CLK'):
    P, Nn = f'/HDMI_{nm}P', f'/HDMI_{nm}N'
    d = plen(paths[P]) - plen(paths[Nn]); h = d / 4          # two square bumps, each adds 2h
    (x0, y), x1 = paths[Nn][2], paths[Nn][3][0]
    pts = paths[Nn][:3]
    for k in (1, 2):                                          # bumps at 1/3 and 2/3 of the horizontal leg
        xm = x0 + (x1 - x0) * k / 3
        pts += [(xm - 0.6, y), (xm - 0.6, y + h), (xm + 0.6, y + h), (xm + 0.6, y)]
    pts.append(paths[Nn][3]); paths[Nn] = pts
for net, pts in paths.items():
    w = 0.25 if net == '/HDMI_5V' else 0.2
    for i in range(len(pts) - 1): trk(pts[i], pts[i + 1], net, w)
# GND pins
for ref, dx, dy in (('J13', 0, -1), ('J14', 1, 0)):
    g = sorted([p for p in pads(ref) if p.GetNetname() == 'GND' and p.GetNumber().isdigit()], key=lambda p: pxy(p)[0] + pxy(p)[1])
    prev = None; stag = False
    for p in g:
        x, y = pxy(p); bbp = p.GetBoundingBox(); half = (bbp.GetHeight() if ref == 'J13' else bbp.GetWidth()) / 2e6
        stag = (prev is not None and abs((x + y) - prev) < 0.6 and not stag)
        off = half + (0.45 if not stag else 1.1)
        q = (x + dx * off, y + dy * off); trk((x, y), q, 'GND', 0.25); via(*q, 'GND'); prev = x + y
# In1 keep-out (no vias) under the HDMI runs, kept on the board
z = pcbnew.ZONE(b); z.SetIsRuleArea(True); z.SetZoneName('HDMI reference'); z.SetLayer(pcbnew.In1_Cu)
z.SetDoNotAllowVias(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowPads(False); z.SetDoNotAllowZoneFills(False); z.SetDoNotAllowFootprints(False)
o = z.Outline(); o.NewOutline()
for p in [(72.4, 11.6), (82.6, 11.6), (82.6, 16.1), (93.8, 16.1), (93.8, 25.7), (72.4, 25.7)]: o.Append(MM(p[0]), MM(p[1]))
b.Add(z)
for nm in ('D0', 'D1', 'D2', 'CLK'):
    print(nm, 'P %.3f N %.3f' % (L[f'/HDMI_{nm}P'], L[f'/HDMI_{nm}N']))
b.Save(sys.argv[2]); print('saved')
