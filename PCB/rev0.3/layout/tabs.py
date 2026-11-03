"""tabs.py in.kicad_pcb out.kicad_pcb : corner mounting tabs (Glenn chose corner tabs, 2026-10-01).
Four 8 x 9 mm tabs on the left and right edges at the corners, each with a plated M3 hole on GND."""
import pcbnew, sys, math
MM = pcbnew.FromMM; V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
FPDIR = '/usr/share/kicad/footprints'
HF = [pcbnew.FootprintLoad(f'{FPDIR}/MountingHole.pretty', 'MountingHole_3.2mm_M3_Pad_Via') for _ in range(4)]   # load before LoadBoard (SWIG quirk)
b = pcbnew.LoadBoard(sys.argv[1])
HP = [list(h.Pads()) for h in HF]; ZS = list(b.Zones()); DR = list(b.GetDrawings())   # snapshot before any Remove (SWIG quirk)
W, H, T, TH, R = 109.0, 92.0, 8.0, 9.0, 2.0
for d in DR:
    if d.GetLayer() == pcbnew.Edge_Cuts: b.Remove(d)
def seg(p, q):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(V(*p)); s.SetEnd(V(*q))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
def arc(c, a0):   # 90 deg clockwise-on-screen arc of radius R starting at angle a0
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetCenter(V(*c))
    s.SetStart(V(c[0] + R * math.cos(math.radians(a0)), c[1] + R * math.sin(math.radians(a0))))
    s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T), True); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); b.Add(s)
L, Rt = -T, W + T
# outer corners rounded, the four inner corners where tabs meet the board stay square
seg((L + R, 0), (Rt - R, 0)); arc((Rt - R, R), 270)
seg((Rt, R), (Rt, TH)); seg((Rt, TH), (W, TH)); seg((W, TH), (W, H - TH)); seg((W, H - TH), (Rt, H - TH))
seg((Rt, H - TH), (Rt, H - R)); arc((Rt - R, H - R), 0)
seg((Rt - R, H), (L + R, H)); arc((L + R, H - R), 90)
seg((L, H - R), (L, H - TH)); seg((L, H - TH), (0, H - TH)); seg((0, H - TH), (0, TH)); seg((0, TH), (L, TH))
seg((L, TH), (L, R)); arc((L + R, R), 180)
HOLES = [(L / 2, 4.5), (L / 2, H - 4.5), (W + T / 2, 4.5), (W + T / 2, H - 4.5)]
gnd = b.FindNet('GND')
for i, (x, y) in enumerate(HOLES):
    h = HF[i]; h.SetFPID(pcbnew.LIB_ID('MountingHole', 'MountingHole_3.2mm_M3_Pad_Via'))
    h.SetReference(f'H{i+1}'); h.SetValue('M3'); h.SetPosition(V(x, y))
    h.SetBoardOnly(True); h.SetExcludedFromBOM(True); h.SetExcludedFromPosFiles(True)
    for pad in HP[i]: pad.SetNet(gnd)
    h.Reference().SetVisible(False); b.Add(h)
# GND pours follow the new outline (0.3 mm inside the edge)
e = 0.3
poly = [(L + e, e), (Rt - e, e), (Rt - e, TH - e), (W - e, TH - e), (W - e, H - TH + e), (Rt - e, H - TH + e), (Rt - e, H - e),
        (L + e, H - e), (L + e, H - TH + e), (e, H - TH + e), (e, TH - e), (L + e, TH - e)]
for z in ZS:
    if z.GetNetname() == 'GND' and z.GetZoneName() in ('F GND', 'In2 GND', 'B GND', 'GND plane'):
        o = z.Outline(); o.RemoveAllContours(); o.NewOutline()
        for p in poly: o.Append(MM(p[0]), MM(p[1]))
pcbnew.ZONE_FILLER(b).Fill(ZS)
b.Save(sys.argv[2]); print('tabs ok', HOLES)
