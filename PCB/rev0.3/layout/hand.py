"""hand.py in.kicad_pcb ops.txt out.kicad_pcb
ops lines:  del NET LAYER x1 y1 x2 y2   (track whose endpoints match within 0.01, either order)
            delvia NET x y
            seg NET LAYER x1 y1 x2 y2 [w=0.2]
            via NET x y [d=0.45 h=0.2]
            nofill   (skip zone refill)"""
import pcbnew, sys
MM = pcbnew.FromMM; b = pcbnew.LoadBoard(sys.argv[1])
L = {'F': pcbnew.F_Cu, 'In2': pcbnew.In2_Cu, 'B': pcbnew.B_Cu}
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
near = lambda p, x, y: abs(p.x / 1e6 - x) < 0.011 and abs(p.y / 1e6 - y) < 0.011
fill = True
TR = list(b.GetTracks()); GONE = set(); FP = {f.GetReference(): f for f in b.GetFootprints()}; ZS = list(b.Zones())
def rm(t): b.Remove(t); GONE.add(id(t))
for ln in open(sys.argv[2]):
    w = ln.split('#')[0].split()
    if not w: continue
    op = w[0]; lock = op.endswith('L') and op != 'del'; op = op[:-1] if lock else op
    if op == 'nofill': fill = False; continue
    net = w[1]
    if op == 'del':
        ly = L[w[2]]; x1, y1, x2, y2 = map(float, w[3:7]); hit = 0
        for t in TR:
            if id(t) in GONE: continue
           
            if isinstance(t, pcbnew.PCB_VIA) or t.GetNetname() != net or t.GetLayer() != ly: continue
            s, e = t.GetStart(), t.GetEnd()
            if (near(s, x1, y1) and near(e, x2, y2)) or (near(s, x2, y2) and near(e, x1, y1)): rm(t); hit += 1
        if not hit: print('NOT FOUND', ln.strip())
    elif op == 'evict':
        ns = set(net.split(',')); x0, y0, x1, y1 = map(float, w[2:6]); hit = 0
        box = pcbnew.BOX2I(P(x0, y0), pcbnew.VECTOR2L(MM(x1 - x0), MM(y1 - y0)))
        for t in TR:
            if id(t) in GONE or t.IsLocked() or t.GetNetname() not in ns: continue
            if t.HitTest(box, False): rm(t); hit += 1
        print('evicted', hit)
    elif op == 'move':
        f = FP[net]; x, y, r = map(float, w[2:5]); f.SetPosition(P(x, y)); f.SetOrientationDegrees(r)
    elif op == 'delnet':   # all unlocked tracks/vias of a net
        hit = 0
        for t in TR:
            if id(t) in GONE or t.IsLocked() or t.GetNetname() != net: continue
            rm(t); hit += 1
        print('delnet', net, hit)
    elif op == 'delvia':
        x, y = map(float, w[2:4]); hit = 0
        for t in TR:
            if id(t) in GONE: continue
           
            if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == net and near(t.GetPosition(), x, y): rm(t); hit += 1
        if not hit: print('NOT FOUND', ln.strip())
    elif op == 'seg':
        x1, y1, x2, y2 = map(float, w[3:7]); wd = float(w[7]) if len(w) > 7 else 0.2
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(MM(wd)); t.SetLayer(L[w[2]]); t.SetNet(b.FindNet(net)); t.SetLocked(lock); b.Add(t)
    elif op == 'via':
        x, y = map(float, w[2:4]); d = float(w[4]) if len(w) > 4 else 0.45; h = float(w[5]) if len(w) > 5 else 0.2
        v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(MM(d)); v.SetDrill(MM(h)); v.SetNet(b.FindNet(net)); v.SetLocked(lock); b.Add(v)
if fill: pcbnew.ZONE_FILLER(b).Fill(ZS)
b.Save(sys.argv[3]); print('ok')
