"""hdmipairs.py in out [W G] : rebuild the four HDMI TMDS pairs (J13 HDMI receptacle -> J14 screen FPC) as edge-coupled
100 ohm pairs on F.Cu over In1. JLCPCB's calculator gives 0.2187 mm / 0.20 mm for JLC04161H-7628, L1 over L2.

Both connectors have P, GND, N at 0.5 mm pitch, so each pair's centreline runs over its GND pin: P and N jog 0.29 mm
inward right after the pads (45 degrees), run coupled along the same nested L path as before (vertical from J13, one
45 degree bend, horizontal into J14) and jog out again at J14. The old loosely coupled tracks (0.2 mm, 0.8 mm gap) go."""
import pcbnew, sys, math
from shapely.geometry import LineString
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
W = float(sys.argv[3]) if len(sys.argv) > 3 else 0.2187
G = float(sys.argv[4]) if len(sys.argv) > 4 else 0.20
OFF = W / 2 + G / 2
PAIRS = [('D2', 'J13'), ('D1', 'J13'), ('D0', 'J13'), ('CLK', 'J13')]
J13 = b.FindFootprintByReference('J13'); J14 = b.FindFootprintByReference('J14')
def pad(fp, net): return [p for p in fp.Pads() if p.GetNetname() == net][0]
gone = []   # keep removed items referenced: freeing them corrupts the SWIG bindings
nets = [f'/HDMI_{n}{s}' for n, _ in PAIRS for s in 'PN']
for t in list(b.GetTracks()):
    if t.GetNetname() in nets: b.Remove(t); gone.append(t)
def P(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))
def add(pts, net):
    L = 0
    for a, c in zip(pts, pts[1:]):
        if math.dist(a, c) < 1e-6: continue
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(MM(W)); t.SetLayer(pcbnew.F_Cu)
        t.SetNet(b.FindNet(net)); t.SetLocked(True); b.Add(t); L += math.dist(a, c)
    return L
YS = 12.2     # J13 side: coupled section starts here (pads end at y 11.49)
XE = 93.3     # J14 side: coupled section ends here (pads start at x 93.91)
for name, _ in PAIRS:
    pP, pN = pad(J13, f'/HDMI_{name}P'), pad(J13, f'/HDMI_{name}N')
    qP, qN = pad(J14, f'/HDMI_{name}P'), pad(J14, f'/HDMI_{name}N')
    xP, xN = T(pP.GetPosition().x), T(pN.GetPosition().x); y13 = T(pP.GetPosition().y)
    yP, yN = T(qP.GetPosition().y), T(qN.GetPosition().y); x14 = T(qP.GetPosition().x)
    xc, yc = (xP + xN) / 2, (yP + yN) / 2
    centre = LineString([(xc, YS), (xc, yc - 1.0), (xc + 1.0, yc), (XE, yc)])
    # heading down then right: P (smaller x at J13, larger y at J14) is on the right-hand side of travel
    lineP = centre.offset_curve(-OFF, join_style=2, mitre_limit=5); lineN = centre.offset_curve(OFF, join_style=2, mitre_limit=5)
    cP, cN = list(lineP.coords), list(lineN.coords)
    if math.dist(cP[0], (xP, YS)) > math.dist(cP[0], (xN, YS)): cP, cN = cN, cP
    dj = 0.5 - OFF   # lateral jog at each end
    LP = add([(xP, y13), (xP, YS - dj)] + cP + [(XE + dj, yP), (x14, yP)], f'/HDMI_{name}P')
    LN = add([(xN, y13), (xN, YS - dj)] + cN + [(XE + dj, yN), (x14, yN)], f'/HDMI_{name}N')
    print(f'{name}: P {LP:.3f} mm, N {LN:.3f} mm, skew {abs(LP - LN):.3f} mm')
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
