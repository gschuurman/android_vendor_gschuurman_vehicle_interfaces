"""gm.py out.kicad_pcb : GNSS module rev 0.4 (NEO-M9N + U.FL), 2 layers, 26.5 x 31.5 mm, header J28 on the bottom side."""
import pcbnew, sys, math
sys.path.insert(0, '/w/gm')
from netparse import load, comps
MM = pcbnew.FromMM; V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
FPDIR = '/usr/share/kicad/footprints'
W, H = 26.5, 31.5
NET = '/w/gm/net_carradio_gnss_rev04.net'
nets, pads = load(NET); comp = comps(NET)
FPL = {}
for r, c in comp.items():
    lib, nm = c['fp'].split(':'); FPL[r] = pcbnew.FootprintLoad(f'{FPDIR}/{lib}.pretty', nm)
HOLE = pcbnew.FootprintLoad(f'{FPDIR}/MountingHole.pretty', 'MountingHole_2.7mm_M2.5_Pad_Via')
b = pcbnew.BOARD(); b.SetCopperLayerCount(2)
NI = {}
for nm in nets: NI[nm] = pcbnew.NETINFO_ITEM(b, nm); b.Add(NI[nm])
FP = {}
for r, c in comp.items():
    f = FPL[r]; lib, nm = c['fp'].split(':'); f.SetFPID(pcbnew.LIB_ID(lib, nm)); f.SetReference(r); f.SetValue(c['val'])
    f.SetPath(pcbnew.KIID_PATH('/' + c['uuid'])); b.Add(f); FP[r] = f
    for p in f.Pads():
        n = pads[r].get(p.GetNumber())
        if n: p.SetNet(NI[n])
def crt(f):
    c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd); bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return (bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)
def at(ref, x, y, rot=0):
    f = FP[ref]; f.SetOrientationDegrees(rot); f.SetPosition(V(x, y))
CX, CY = 16.5, 19.2                    # NEO-M9N centre; RF_IN (pin 11) at y CY+5.9
YS = CY + 5.9
at('U7', CX, CY)
at('J11', 3.3, YS, 180)                # U.FL receptacle, pad 1 (signal) faces the NEO
J = FP['J28']; J.Flip(J.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)   # header on the top edge (bottom side of the module)
J.SetOrientationDegrees(90); J.SetPosition(V(0, 0))
x0, y0, x1, y1 = crt(J)
J.SetPosition(V((W - (x1 - x0)) / 2 - x0, 0.7 - y0))
# left column between the standoff/SMA and the module: USB series resistors, RF feed
at('R102', 7.6, 9.4, 90); at('R103', 7.6, 12.6, 90); at('C17', 7.6, 16.0, 90)
at('R41', 7.7, YS - 3.5, 90)           # 10R ANT_FEED <- VCC_RF
at('L2', 7.7, YS - 1.0, 90)            # 27nH: bottom pad on the RF line, top pad ANT_FEED
# decoupling: 10u under the header, 100n by VCC (pin 23) and V_BCKP (pin 22) in the right corridor
at('C14', 20.5, 8.9, 0); at('C15', 24.9, 12.0, 90); at('C16', 24.9, 15.2, 90)
def padpos(ref, n): return [(p.GetPosition().x / 1e6, p.GetPosition().y / 1e6) for p in FP[ref].Pads() if p.GetNumber() == n][0]
if padpos('L2', '2')[1] < padpos('L2', '1')[1]: at('L2', 7.7, YS - 1.0, 270)        # pad 2 (RF) onto the line
if padpos('R41', '2')[1] < padpos('R41', '1')[1]: at('R41', 7.7, YS - 3.5, 270)    # pad 2 (ANT_FEED) towards L2
# RF line: 1.0 mm CPWG from the SMA pin to RF_IN, necked to the pad width at the module
GRF = NI['/GNSS_RF']; GND = NI['GND']
def trk(p, q, w, net, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(b); t.SetStart(V(*p)); t.SetEnd(V(*q)); t.SetWidth(MM(w)); t.SetLayer(layer); t.SetNet(net); t.SetLocked(True); b.Add(t)
xs, xp = padpos('J11', '1')[0], padpos('U7', '11')[0]
trk((xs, YS), (CX - 7.6, YS), 1.0, GRF); trk((CX - 7.6, YS), (xp, YS), 0.8, GRF)
l2 = padpos('L2', '1'); r41 = padpos('R41', '2'); trk(l2, r41, 0.3, NI['/ANT_FEED'])
for x, y in [(6.0, YS - 1.5), (6.0, YS + 1.5), (7.7, YS + 1.5), (CX - 7.7, YS + 1.6), (1.0, YS - 2.6), (1.0, YS + 2.6)]:
    v = pcbnew.PCB_VIA(b); v.SetPosition(V(x, y)); v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3)); v.SetNet(GND); v.SetLocked(True); b.Add(v)
b.Add(HOLE); HOLE.SetFPID(pcbnew.LIB_ID('MountingHole', 'MountingHole_2.7mm_M2.5_Pad_Via')); HOLE.SetReference('H1'); HOLE.SetValue('M2.5 standoff')
HOLE.SetBoardOnly(True); HOLE.SetExcludedFromBOM(True); HOLE.SetExcludedFromPosFiles(True)
for p in HOLE.Pads(): p.SetNet(NI['GND'])
HOLE.SetPosition(V(3.2, 15.3))
# ---- 3V3 feed pre-routed: header pins 1/2 -> right corridor -> C14, C15, pin 23; V_BCKP pin 22 -> C16
for ref, up in (('C14', '1'), ('C15', '1'), ('C16', '1')):
    f = FP[ref]; c = f.GetPosition()
    if ref == 'C14':
        if padpos(ref, up)[0] < c.x / 1e6: f.SetOrientationDegrees(f.GetOrientationDegrees() + 180)
    elif padpos(ref, up)[1] > c.y / 1e6: f.SetOrientationDegrees(f.GetOrientationDegrees() + 180)
def path(net, layer, pts, w=0.3):
    for p, q in zip(pts, pts[1:]): trk(p, q, w, NI[net], layer)
G3 = '/+3V3_GNSS'; XC = 23.95
j1, c14, c15, p23 = padpos('J28', '1'), padpos('C14', '1'), padpos('C15', '1'), padpos('U7', '23')
path(G3, pcbnew.F_Cu, [j1, (XC, j1[1] + 1.81), (XC, p23[1]), p23])
path(G3, pcbnew.F_Cu, [c14, (XC, c14[1])]); path(G3, pcbnew.F_Cu, [(XC, c15[1]), c15])
path('/+3V3_MCU', pcbnew.F_Cu, [padpos('U7', '22'), padpos('C16', '1')])
def via(x, y, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(V(x, y)); v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3)); v.SetNet(NI[net]); v.SetLocked(True); b.Add(v)
B_ = pcbnew.B_Cu
j4, c16 = padpos('J28', '4'), padpos('C16', '1'); xm = (j1[0] + j4[0]) / 2
path('/+3V3_MCU', B_, [j4, (xm, j4[1] + 1.27), (xm, 7.0), (24.6, 10.73), (24.6, c16[1] - 0.8), (c16[0] + 0.65, c16[1])]); via(c16[0] + 0.65, c16[1], '/+3V3_MCU')
p7 = padpos('U7', '7')
path(G3, pcbnew.F_Cu, [p7, (p7[0] - 1.6, p7[1])]); via(p7[0] - 1.6, p7[1], G3)
path(G3, B_, [(p7[0] - 1.6, p7[1]), (p7[0] + 3.5, p7[1]), (XC - 4.45, p23[1]), (XC, p23[1])]); via(XC, p23[1], G3)
g15 = padpos('C15', '2'); v = pcbnew.PCB_VIA(b); v.SetPosition(V(g15[0] + 0.6, g15[1])); v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3)); v.SetNet(NI['GND']); v.SetLocked(True); b.Add(v)
ko = pcbnew.ZONE(b); ko.SetIsRuleArea(True); ko.SetDoNotAllowTracks(True); ko.SetDoNotAllowVias(True); ko.SetDoNotAllowZoneFills(False)
ko.SetDoNotAllowPads(False); ko.SetDoNotAllowFootprints(False); ko.SetLayer(pcbnew.F_Cu); ko.SetZoneName('under NEO')
o = ko.Outline(); o.NewOutline()
for x, y in [(CX - 4.9, CY - 8.0), (CX + 4.9, CY - 8.0), (CX + 4.9, CY + 8.0), (CX - 4.9, CY + 8.0)]: o.Append(MM(x), MM(y))
b.Add(ko)
rk = pcbnew.ZONE(b); rk.SetIsRuleArea(True); rk.SetDoNotAllowTracks(True); rk.SetDoNotAllowVias(False); rk.SetDoNotAllowZoneFills(False)
rk.SetDoNotAllowPads(False); rk.SetDoNotAllowFootprints(False); rk.SetLayer(pcbnew.B_Cu); rk.SetZoneName('RF ground reference')
o = rk.Outline(); o.NewOutline()      # solid B.Cu ground under the RF line, the feed parts and the SMA pins
for x, y in [(0, YS - 2.6), (CX - 4.9, YS - 2.6), (CX - 4.9, YS + 2.4), (0, YS + 2.4)]: o.Append(MM(x), MM(y))
b.Add(rk)
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):      # 0.6 mm band along the outline: keeps the autorouter off the edge
    for (x0, y0, x1, y1) in [(0, 0, W, 0.6), (0, H - 0.6, W, H), (W - 0.6, 0, W, H), (0, 0, 0.6, H)]:
        kz = pcbnew.ZONE(b); kz.SetIsRuleArea(True); kz.SetDoNotAllowTracks(True); kz.SetDoNotAllowVias(True); kz.SetDoNotAllowZoneFills(False)
        kz.SetDoNotAllowPads(False); kz.SetDoNotAllowFootprints(False); kz.SetLayer(layer); kz.SetZoneName('edge band')
        o = kz.Outline(); o.NewOutline()
        for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]: o.Append(MM(x), MM(y))
        b.Add(kz)
def seg(p, q):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(*p)); s.SetEnd(V(*q)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
for p, q in [((0, 0), (W, 0)), ((W, 0), (W, H)), ((W, H), (0, H)), ((0, H), (0, 0))]: seg(p, q)
for r in sorted(FP): print(r, [round(v, 2) for v in crt(FP[r])], FP[r].GetOrientationDegrees())
pp = {p.GetNumber(): (round(p.GetPosition().x / 1e6, 3), round(p.GetPosition().y / 1e6, 3)) for p in J.Pads()}
print('J28 pins', pp['1'], pp['2'], pp['3'])
b.Save(sys.argv[1])
