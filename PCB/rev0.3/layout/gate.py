"""gate.py in.kicad_pcb out.kicad_pcb : gate resistors R97/R98 and SW1 snubber C104/R99 (TPS55288 review follow-up)."""
import pcbnew, sys
MM = pcbnew.FromMM
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
FPDIR = '/usr/share/kicad/footprints'
NEW = [  # ref, lib, fp, uuid, value, lcsc, mpn, x, y, rot
    ('R97', 'Resistor_SMD', 'R_0402_1005Metric', '6ea1a461-ada0-511d-a434-95693e1db8ad', '0Ω', 'C17168', 'UNI-ROYAL 0402WGF0000TCE 0402 0R', 24.6, 63.19, 90),
    ('R98', 'Resistor_SMD', 'R_0402_1005Metric', '6d2a78c7-675e-52b1-a835-d0ff576f3d16', '0Ω', 'C17168', 'UNI-ROYAL 0402WGF0000TCE 0402 0R', 30.97, 69.1, 0),
    ('C104', 'Capacitor_SMD', 'C_0603_1608Metric', '49cc9a70-c5c4-5dc4-9675-d40a224487ff', '1nF', 'C1588', 'Samsung CL10B102KB8NNNC 0603 1nF 50V X7R', 26.6, 63.1, 0),
    ('R99', 'Resistor_SMD', 'R_0805_2012Metric', '68c54875-fcf1-5720-b2d2-3754f14636a5', '2.2Ω 0805', 'C17521', 'UNI-ROYAL 0805W8F220KT5E 0805 2.2R 125mW', 29.85, 63.1, 0)]
FPS = {n[0]: pcbnew.FootprintLoad(f'{FPDIR}/{n[1]}.pretty', n[2]) for n in NEW}
b = pcbnew.LoadBoard(sys.argv[1])
TR = list(b.GetTracks()); FP = {f.GetReference(): f for f in b.GetFootprints()}
L = {'F': pcbnew.F_Cu, 'In2': pcbnew.In2_Cu, 'B': pcbnew.B_Cu}
def net(name):
    n = b.FindNet(name)
    if n is None:
        n = pcbnew.NETINFO_ITEM(b, name); b.Add(n)
    return n
def pad(ref, num): return [q for q in FP[ref].Pads() if q.GetNumber() == num][0]
pad('Q11', '4').SetNet(net('/BB_DR1H_G')); pad('Q12', '4').SetNet(net('/BB_DR1L_G'))

# remove old gate copper next to the FETs
def near(p, x, y): return abs(p.x / 1e6 - x) < 0.012 and abs(p.y / 1e6 - y) < 0.012
KILL = [('/BB_DR1H', 'B', (23.815, 63.655), (24.0, 63.655)), ('/BB_DR1H', 'F', (24.0, 63.655), (24.0, 64.76)),
        ('/BB_DR1L', 'F', (30.95, 67.15), (30.6, 67.64)), ('/BB_DR1L', 'In2', (32.7, 65.4), (30.95, 67.15))]
KILLV = [('/BB_DR1H', 24.0, 63.655), ('/BB_DR1L', 30.95, 67.15)]
n = 0
for t in TR:
    nm = t.GetNetname()
    if isinstance(t, pcbnew.PCB_VIA):
        if any(nm == k[0] and near(t.GetPosition(), k[1], k[2]) for k in KILLV): b.Remove(t); n += 1
    else:
        for k in KILL:
            if nm == k[0] and t.GetLayer() == L[k[1]] and {(round(t.GetStart().x / 1e6, 3), round(t.GetStart().y / 1e6, 3)), (round(t.GetEnd().x / 1e6, 3), round(t.GetEnd().y / 1e6, 3))} == {k[2], k[3]}:
                b.Remove(t); n += 1
print('removed', n)

PADS = {}
for ref, lib, fpn, uid, val, lcsc, mpn, x, y, rot in NEW:
    f = FPS[ref]; f.SetFPID(pcbnew.LIB_ID(lib, fpn)); f.SetReference(ref); f.SetValue(val)
    f.SetPath(pcbnew.KIID_PATH('/' + uid)); f.SetField('LCSC', lcsc); f.SetField('MPN', mpn)
    for fld in f.GetFields():
        if fld.GetName() not in ('Reference',): fld.SetVisible(False)
    b.Add(f); f.SetPosition(P(x, y)); f.SetOrientationDegrees(rot)
    PADS[ref] = sorted(((p.GetPosition().x / 1e6, p.GetPosition().y / 1e6), p) for p in f.Pads())
# R97 vertical: upper pad DR1H, lower pad gate
r97 = sorted(PADS['R97'], key=lambda e: e[0][1]); r97[0][1].SetNet(net('/BB_DR1H')); r97[1][1].SetNet(net('/BB_DR1H_G'))
r98 = PADS['R98']; r98[0][1].SetNet(net('/BB_DR1L_G')); r98[1][1].SetNet(net('/BB_DR1L'))
c = PADS['C104']; c[0][1].SetNet(net('/BB_SW1')); c[1][1].SetNet(net('/BB_SNUB'))
r = PADS['R99']; r[0][1].SetNet(net('/BB_SNUB')); r[1][1].SetNet(net('GND'))
for k, v in PADS.items(): print(k, [(round(p[0][0], 3), round(p[0][1], 3), p[1].GetNetname()) for p in v])

def seg(nm, ly, path, w=0.2):
    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(MM(w)); t.SetLayer(L[ly]); t.SetNet(net(nm)); t.SetLocked(True); b.Add(t)
def via(nm, x, y, d=0.45, h=0.2):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(MM(d)); v.SetDrill(MM(h)); v.SetNet(net(nm)); v.SetLocked(True); b.Add(v)
(ux, uy), (lx, ly) = r97[0][0], r97[1][0]
# DR1H: B route from U12 comes up to a via left of R97 (VSYS_IN runs on B at y 61.87 above, In2 diagonals to the right)
via('/BB_DR1H', 23.75, 62.9)
seg('/BB_DR1H', 'B', [(23.75, 62.9), (23.75, 63.25), (24.2, 63.7)])
seg('/BB_DR1H', 'F', [(23.75, 62.9), (ux, uy)])
seg('/BB_DR1H_G', 'F', [(lx, ly), (24.03, ly), (24.03, 64.76)])
(gx, gy), (dx, dy) = r98[0][0], r98[1][0]
seg('/BB_DR1L_G', 'F', [(30.57, 67.64), (30.57, 68.4), (gx, gy)])
via('/BB_DR1L', 31.9, 68.3)
seg('/BB_DR1L', 'In2', [(32.7, 65.4), (31.9, 66.2), (31.9, 68.3)])
seg('/BB_DR1L', 'F', [(31.9, 68.3), (dx, 68.72), (dx, dy)])
seg('/BB_SNUB', 'F', [c[1][0], r[0][0]], 0.4)
via('GND', 31.55, 63.6, 0.6, 0.3)
seg('GND', 'F', [r[1][0], (31.55, 63.6)], 0.5)
filler = pcbnew.ZONE_FILLER(b); filler.Fill(b.Zones())
b.Save(sys.argv[2]); print('ok')
