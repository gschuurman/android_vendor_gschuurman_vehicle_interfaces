"""Give every SMD GND pad its own via to the In1 ground plane (short stub), so the autorouter never routes GND.
usage: fanout.py in.kicad_pcb out.kicad_pcb"""
import pcbnew, sys, math, re
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
W, H = 100.0, 100.0
VD, VH, CL = 0.45, 0.2, 0.2
gnd = b.FindNet('GND')
obst = []   # (x0,y0,x1,y1, netcode)
for f in b.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox()
        obst.append((bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6, p.GetNetCode()))
for t in b.GetTracks():
    bb = t.GetBoundingBox()
    obst.append((bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6, t.GetNetCode()))
zones = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() != 'GND' and z.GetLayer() == pcbnew.F_Cu]
def in_zone(x, y, r):
    for z in zones:
        bb = z.GetBoundingBox()
        if bb.GetX() / 1e6 - r - 0.3 < x < bb.GetRight() / 1e6 + r + 0.3 and bb.GetY() / 1e6 - r - 0.3 < y < bb.GetBottom() / 1e6 + r + 0.3:
            if z.Outline().Collide(pcbnew.VECTOR2I(MM(x), MM(y)), MM(r + 0.3)): return True
    return False
def free(x, y, r, ignore=None):
    if in_zone(x, y, r): return False
    if x < 0.8 or y < 0.8 or x > W - 0.8 or y > H - 0.8: return False
    for (x0, y0, x1, y1, nc) in obst:
        if nc == gnd.GetNetCode() and nc != 0: m = 0.05
        else: m = CL
        dx = max(x0 - x, 0, x - x1); dy = max(y0 - y, 0, y - y1)
        if math.hypot(dx, dy) < r + m: return False
    return True
def seg_free(x0, y0, x1, y1, w, pad_bb):
    # sample along the stub, ignore our own pad
    n = 6
    for i in range(1, n + 1):
        x = x0 + (x1 - x0) * i / n; y = y0 + (y1 - y0) * i / n
        for (a0, b0, a1, b1, nc) in obst:
            if (a0, b0, a1, b1) == pad_bb or nc == gnd.GetNetCode(): continue
            dx = max(a0 - x, 0, x - a1); dy = max(b0 - y, 0, y - b1)
            if math.hypot(dx, dy) < w / 2 + CL: return False
    return True
added = fails = 0
for f in b.GetFootprints():
    for p in f.Pads():
        if p.GetNetCode() != gnd.GetNetCode(): continue
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH): continue
        LAY = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
        c = p.GetPosition(); cx, cy = c.x / 1e6, c.y / 1e6
        bb = p.GetBoundingBox(); pb = (bb.GetX() / 1e6, bb.GetY() / 1e6, bb.GetRight() / 1e6, bb.GetBottom() / 1e6)
        # already has a via on the pad or touching it (HDMI connector GNDs)?
        if any(isinstance(t, pcbnew.PCB_VIA) and t.GetNetCode() == gnd.GetNetCode() and
               pb[0] - 1.2 < t.GetPosition().x / 1e6 < pb[2] + 1.2 and pb[1] - 1.2 < t.GetPosition().y / 1e6 < pb[3] + 1.2
               for t in b.GetTracks()):
            continue
        hw, hh = (pb[2] - pb[0]) / 2, (pb[3] - pb[1]) / 2
        # big pads (exposed pads, thermal pads): vias inside the pad
        if hw > 1.0 and hh > 1.0:
            for dx, dy in [(-0.6, -0.6), (0.6, -0.6), (-0.6, 0.6), (0.6, 0.6)] if min(hw, hh) > 1.3 else [(0, 0)]:
                v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(cx + dx), MM(cy + dy)))
                v.SetWidth(MM(VD)); v.SetDrill(MM(VH)); v.SetNet(gnd); b.Add(v); added += 1
            continue
        done = False
        for dist in (0.55, 0.8, 1.1, 1.5, 2.0):
            for ang in range(0, 360, 30):
                a = math.radians(ang)
                ex = cx + (hw + dist) * math.cos(a); ey = cy + (hh + dist) * math.sin(a)
                if free(ex, ey, VD / 2) and seg_free(cx, cy, ex, ey, 0.3, pb):
                    t = pcbnew.PCB_TRACK(b); t.SetStart(c); t.SetEnd(pcbnew.VECTOR2I(MM(ex), MM(ey)))
                    t.SetWidth(MM(0.3)); t.SetLayer(LAY); t.SetNet(gnd); b.Add(t)
                    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(ex), MM(ey)))
                    v.SetWidth(MM(VD)); v.SetDrill(MM(VH)); v.SetNet(gnd); b.Add(v)
                    obst.append((ex - VD / 2, ey - VD / 2, ex + VD / 2, ey + VD / 2, gnd.GetNetCode()))
                    obst.append((min(cx, ex) - 0.15, min(cy, ey) - 0.15, max(cx, ex) + 0.15, max(cy, ey) + 0.15, gnd.GetNetCode()))
                    added += 1; done = True; break
            if done: break
        if not done: fails += 1; print('no via for', f.GetReference(), p.GetNumber())
b.Save(sys.argv[2])
print('GND vias added', added, 'failed', fails)
