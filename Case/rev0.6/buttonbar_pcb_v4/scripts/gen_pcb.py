import pcbnew, sys
sys.path.insert(0, ".")
from design import *
OX, OY = 100.0, 100.0
def P(x, y): return pcbnew.VECTOR2I(pcbnew.FromMM(OX + L/2 + x), pcbnew.FromMM(OY + y))
b = pcbnew.BOARD(); b.SetCopperLayerCount(2)
ds = b.GetDesignSettings()
ds.SetBoardThickness(pcbnew.FromMM(1.6))
ds.m_TrackMinWidth = pcbnew.FromMM(0.25); ds.m_MinClearance = pcbnew.FromMM(0.25)
ds.m_ViasMinSize = pcbnew.FromMM(0.6); ds.m_MinThroughDrill = pcbnew.FromMM(0.3)
ds.m_CopperEdgeClearance = pcbnew.FromMM(0.25)
nc = ds.m_NetSettings.m_DefaultNetClass
nc.SetTrackWidth(pcbnew.FromMM(0.4)); nc.SetClearance(pcbnew.FromMM(0.25)); nc.SetViaDiameter(pcbnew.FromMM(0.8)); nc.SetViaDrill(pcbnew.FromMM(0.4))
pts = [(-L/2, 0), (L/2, 0), (L/2, H), (-L/2, H)]
for i in range(4):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1))
    s.SetStart(P(*pts[i])); s.SetEnd(P(*pts[(i+1) % 4])); b.Add(s)
nets = {}
def net(n):
    if n not in nets:
        ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
    return nets[n]
LIB = "buttonbar_v4/buttonbar_v4.pretty"
def place(name, ref, val, x, y, rot=0, padnets={}, back=False):
    fp = pcbnew.FootprintLoad(LIB, name)
    fp.SetFPID(pcbnew.LIB_ID("buttonbar_v4", name))
    fp.SetReference(ref); fp.SetValue(val)
    b.Add(fp)
    fp.SetPosition(P(x, y))
    if back: fp.Flip(P(x, y), False)
    fp.SetOrientationDegrees(rot)
    fp.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8))); fp.Reference().SetTextThickness(pcbnew.FromMM(0.12))
    for p in fp.Pads():
        n = padnets.get(p.GetNumber())
        if n: p.SetNet(net(n))
    return fp
for ref, lab, x, ls in BTNS:
    sig = LINES[ls] if len(ls) == 1 else node(ref)
    place("SW_TC-0120_2pin_P7.4mm", ref, lab, x, SW_Y, 0, {"1": "GND", "2": sig})
for ref, x, y, line, nd, lab in diodes():
    # pad 1 = cathode (switch node), pad 2 = anode (J12 line); on the back
    fp = place("D_SMA_Handsoldering", ref, "SS14", x, y, 180, {"1": nd, "2": line}, back=True)
place("BH1750_szfydosh_castellated", "U1", "BH1750 module (szfydosh)", BH_X, YC, 0, BH_PINS)
place("JST_PH_B5B-PH-K_1x05_P2.00mm_Vertical", "J1", "to J12 (B5B-PH-K-S)", J1_X, J_Y, 0, {str(i+1): n for i, n in enumerate(J1_PINS)}, back=True)
place("JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical", "J2", "to J7 (B4B-PH-K-S)", J2_X, J_Y, 0, {str(i+1): n for i, n in enumerate(J2_PINS)}, back=True)
for i, (hx, hy) in enumerate(HOLES):
    place("MountingHole_3.4mm_M3_NPTH", "H%d" % (i+1), "M3", hx, hy)
for i, (hx, hy) in enumerate(HEAD_HOLES):
    place("Hole_6.6mm_plate_ear_NPTH", "H%d" % (i+4), "plate ear", hx, hy)
def silk(txt, x, y, size=0.8, layer=pcbnew.F_SilkS, mirror=False):
    t = pcbnew.PCB_TEXT(b); t.SetText(txt); t.SetPosition(P(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size))); t.SetTextThickness(pcbnew.FromMM(0.12))
    if mirror: t.SetMirrored(True)
    b.Add(t)
silk("J12", J1_X + 4, H - 0.7, 0.8, pcbnew.B_SilkS, True)
silk("J7", J2_X + 3, H - 0.7, 0.8, pcbnew.B_SilkS, True)
silk("BUTTON BAR v4", BH_X, YC - 1.2, 0.8, pcbnew.B_SilkS, True); silk("D = SS14, J12 + J7 PH", BH_X, YC + 1.2, 0.8, pcbnew.B_SilkS, True)
pcbnew.SaveBoard("buttonbar_v4/buttonbar_v4.kicad_pcb", b)
print("nets", len(nets), "fps", len(b.GetFootprints()))
