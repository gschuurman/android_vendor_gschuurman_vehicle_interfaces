import pcbnew, sys
sys.path.insert(0, ".")
from design import *
OX, OY = 100.0, 100.0
def P(x, y): return pcbnew.VECTOR2I(pcbnew.FromMM(OX + L/2 + x), pcbnew.FromMM(OY + y))
b = pcbnew.BOARD()
b.SetCopperLayerCount(2)
ds = b.GetDesignSettings()
ds.SetBoardThickness(pcbnew.FromMM(1.6))
ds.m_TrackMinWidth = pcbnew.FromMM(0.3)
ds.m_MinClearance = pcbnew.FromMM(0.3)
ds.m_ViasMinSize = pcbnew.FromMM(0.8)
ds.m_MinThroughDrill = pcbnew.FromMM(0.4)
ds.m_CopperEdgeClearance = pcbnew.FromMM(0.4)
nc = ds.m_NetSettings.m_DefaultNetClass
nc.SetTrackWidth(pcbnew.FromMM(0.5)); nc.SetClearance(pcbnew.FromMM(0.35)); nc.SetViaDiameter(pcbnew.FromMM(1.0)); nc.SetViaDrill(pcbnew.FromMM(0.5))
# outline
pts = [(-L/2, 0), (L/2, 0), (L/2, H), (-L/2, H)]
for i in range(4):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1))
    s.SetStart(P(*pts[i])); s.SetEnd(P(*pts[(i+1) % 4])); b.Add(s)
nets = {}
def net(n):
    if n not in nets:
        ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
    return nets[n]
SYS = "/usr/share/kicad/footprints/"
def place(lib, name, ref, val, x, y, rot=0, padnets={}):
    fp = pcbnew.FootprintLoad(lib, name)
    fp.SetFPID(pcbnew.LIB_ID(lib.rstrip("/").split("/")[-1].replace(".pretty", ""), name))
    fp.SetReference(ref); fp.SetValue(val); fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(rot)
    fp.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8))); fp.Reference().SetTextThickness(pcbnew.FromMM(0.12))
    b.Add(fp)
    for p in fp.Pads():
        if p.GetNumber() in padnets: p.SetNet(net(padnets[p.GetNumber()]))
    return fp
for ref, lab, x, ls in BTNS:
    sig = LINES[ls] if len(ls) == 1 else node(ref)
    fp = place("buttonbar/buttonbar.pretty", "SW_Tactile_6x3.5mm_2pin_P5.08mm", ref, lab, x, SW_Y, 0, {"1": "GND", "2": sig})
    fp.Reference().SetPosition(P(x, SW_Y - 2.6 if True else 0))
for ref, x, y, line, nd, lab in diodes():
    # KiCad DO-34 horizontal: pad 1 = cathode at origin, pad 2 = anode +7.62 in X
    fp = place("buttonbar/buttonbar.pretty", "D_DO-34_SOD68_P7.62mm_Horizontal", ref, "BAT85", x - 3.81, y, 0, {"1": nd, "2": line})
    fp.Reference().SetPosition(P(x + 5.6, y))
jn = {str(i+1): (LINES[p] if p in LINES else "GND") for i, p in enumerate(J1_PINS)}
fp = place("buttonbar/buttonbar.pretty", "PinHeader_1x05_P2.54mm_Vertical", "J1", "to J12", J1_X - 5.08, SW_Y, 90, jn)
# silkscreen labels
def silk(txt, x, y, size=0.8, layer=pcbnew.F_SilkS):
    t = pcbnew.PCB_TEXT(b); t.SetText(txt); t.SetPosition(P(x, y)); t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size))); t.SetTextThickness(pcbnew.FromMM(0.12)); b.Add(t)
for ref, lab, x, ls in BTNS:
    silk(lab, x, 10.5 if len(ls) == 1 else 0.75, 0.8)
silk("J12: 1 2 3 4 5(GND)", J1_X, 9.0, 0.8)
silk("Button bar rev 0.6 - front side (seen from the front of the radio)", -45, 0.85 if False else 10.6, 0.7) if False else None
silk("BUTTON BAR v1", 16.5, 1.0, 0.8)
silk("BAT85 Schottky only", 16.5, 10.5, 0.8)
pcbnew.SaveBoard("buttonbar/buttonbar.kicad_pcb", b)
print("nets", len(nets), "footprints", len(b.GetFootprints()))
