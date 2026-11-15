import pcbnew, sys, itertools
sys.path.insert(0, ".")
from design import *
FPD = "/usr/share/kicad/footprints/"
def V(x, y): return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
b = pcbnew.BOARD(); b.SetCopperLayerCount(2)
ds = b.GetDesignSettings()
ds.SetBoardThickness(pcbnew.FromMM(1.6))
ds.m_TrackMinWidth = pcbnew.FromMM(0.2); ds.m_MinClearance = pcbnew.FromMM(0.2)
ds.m_ViasMinSize = pcbnew.FromMM(0.6); ds.m_MinThroughDrill = pcbnew.FromMM(0.3)
ds.m_CopperEdgeClearance = pcbnew.FromMM(0.3)
nc = ds.m_NetSettings.m_DefaultNetClass
nc.SetTrackWidth(pcbnew.FromMM(0.3)); nc.SetClearance(pcbnew.FromMM(0.2)); nc.SetViaDiameter(pcbnew.FromMM(0.7)); nc.SetViaDrill(pcbnew.FromMM(0.35))
# rounded-rectangle outline, r = 1 mm
r = 1.0
segs = [((BX0+r, BY0), (BX1-r, BY0)), ((BX1, BY0+r), (BX1, BY1-r)), ((BX1-r, BY1), (BX0+r, BY1)), ((BX0, BY1-r), (BX0, BY0+r))]
for a, c in segs:
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1))
    s.SetStart(V(*a)); s.SetEnd(V(*c)); b.Add(s)
for cx, cy, sx, sy in [(BX0+r, BY0+r, BX0, BY0+r), (BX1-r, BY0+r, BX1-r, BY0), (BX1-r, BY1-r, BX1, BY1-r), (BX0+r, BY1-r, BX0+r, BY1)]:
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(pcbnew.FromMM(0.1))
    s.SetCenter(V(cx, cy)); s.SetStart(V(sx, sy)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T)); b.Add(s)
nets = {}
def net(n):
    if n not in nets:
        ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
    return nets[n]
fps = {}
for ref, sym, val, fpn, x, y, rot, side, padnets, lcsc, mpn, note in PARTS:
    lib, name = fpn.split(":")
    fp = pcbnew.FootprintLoad(FPD + lib + ".pretty", name)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref); fp.SetValue(val)
    b.Add(fp)
    if ref == "J1":
        # find the placement that puts every pad on its J10 position
        best = None
        for rr in (0, 90, 180, 270):
            fp.SetPosition(V(*j10(1)))
            if not fp.IsFlipped(): fp.Flip(V(*j10(1)), False)
            fp.SetOrientationDegrees(rr)
            err = sum(abs(pcbnew.ToMM(p.GetPosition().x) - j10(int(p.GetNumber()))[0]) + abs(pcbnew.ToMM(p.GetPosition().y) - j10(int(p.GetNumber()))[1]) for p in fp.Pads())
            if best is None or err < best[0]: best = (err, rr)
        fp.SetOrientationDegrees(best[1]); print("J1 rot", best)
    else:
        fp.SetPosition(V(x, y))
        if side == "B": fp.Flip(V(x, y), False)
        fp.SetOrientationDegrees(rot)
    for t in (fp.Reference(),):
        t.SetTextSize(V(0.8, 0.8)); t.SetTextThickness(pcbnew.FromMM(0.12))
    fp.Value().SetVisible(False)
    for p in fp.Pads():
        n = padnets.get(p.GetNumber())
        if n: p.SetNet(net(n))
    fps[ref] = fp
for p in fps["J1"].Pads():
    print("J1 pad", p.GetNumber(), round(pcbnew.ToMM(p.GetPosition().x), 2), round(pcbnew.ToMM(p.GetPosition().y), 2), j10(int(p.GetNumber())))
def silk(txt, x, y, size=0.8, layer=pcbnew.F_SilkS, mirror=False, rot=0):
    t = pcbnew.PCB_TEXT(b); t.SetText(txt); t.SetPosition(V(x, y)); t.SetLayer(layer)
    t.SetTextSize(V(size, size)); t.SetTextThickness(pcbnew.FromMM(0.12)); t.SetTextAngleDegrees(rot)
    if mirror: t.SetMirrored(True)
    b.Add(t)
for t in SILK: silk(*t)
# keep copper away from the M2 screw head / spacer at H1 (6 mm circle)
for L in (pcbnew.F_Cu, pcbnew.B_Cu):
    k = pcbnew.ZONE(b); k.SetIsRuleArea(True); k.SetLayer(L)
    k.SetDoNotAllowCopperPour(True); k.SetDoNotAllowTracks(True); k.SetDoNotAllowVias(True)
    o = k.Outline(); o.NewOutline()
    import math
    for i in range(24):
        a = 2 * math.pi * i / 24; o.Append(V(69.6 + 2.6 * math.cos(a), 18.5 + 2.6 * math.sin(a)))
    b.Add(k)
pcbnew.SaveBoard(NAME + "/" + NAME + ".kicad_pcb", b)
# courtyard overlap / outline check
def bb(fp, layer):
    xs = []; ys = []
    for g in fp.GraphicalItems():
        if g.GetLayer() == layer:
            q = g.GetBoundingBox()
            xs += [q.GetX(), q.GetRight()]; ys += [q.GetY(), q.GetBottom()]
    if not xs: return None
    return min(xs), min(ys), max(xs), max(ys)
items = []
for ref, fp in fps.items():
    L = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    c = bb(fp, L)
    if c is None: continue
    x0, y0, x1, y1 = [pcbnew.ToMM(v) for v in c]
    items.append((ref, L, x0, y0, x1, y1))
    if x0 < BX0 - 0.01 or y0 < BY0 - 0.01 or x1 > BX1 + 0.01 or y1 > BY1 + 0.01:
        print("OUTSIDE", ref, round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))
for it in items: print("CY", it[0], [round(v,2) for v in it[2:]], "size", round(it[4]-it[2],2), round(it[5]-it[3],2))
for a, c in itertools.combinations(items, 2):
    if a[1] != c[1]: continue
    if a[2] < c[4] and c[2] < a[4] and a[3] < c[5] and c[3] < a[5]:
        print("OVERLAP", a[0], c[0])
print("nets", len(nets), "fps", len(fps))
