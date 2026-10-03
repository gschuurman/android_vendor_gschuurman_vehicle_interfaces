"""fanmcu.py in drc.json out : escape the unconnected RP2350B (U20) pads with a short stub and a via.
Even pins go outward (via just outside the pad row), odd pins inward (via between the pad row and the EP),
so no stub ever passes a neighbour's via. Unlocked copper of other nets in the way is ripped (maze reconnects)."""
import pcbnew, sys, json, re
MM = pcbnew.FromMM; T = pcbnew.ToMM; V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
b = pcbnew.LoadBoard(sys.argv[1]); d = {'unconnected_items': []} if sys.argv[2] == 'ALL' else json.load(open(sys.argv[2]))
U = b.FindFootprintByReference('U20'); c = U.GetPosition(); cx, cy = T(c.x), T(c.y)
want = set()
if sys.argv[2] == 'ALL': want = {p.GetNumber() for p in U.Pads() if p.GetNumber().isdigit() and int(p.GetNumber()) <= 80 and p.GetNetname() not in ('GND', '')}
for u in d['unconnected_items']:
    for i in u['items']:
        m = re.match(r'Pad (\d+) \[[^\]]+\] of U20', i['description'])
        if m: want.add(m.group(1))
VD, VH, CL, TW = 0.45, 0.2, 0.15, 0.2
pads_all = [(p, T(p.GetPosition().x), T(p.GetPosition().y)) for f in b.GetFootprints() for p in f.Pads()]
def clear_of_pads(x, y, net):
    for p, px, py in pads_all:
        if p.GetNetCode() == net: continue
        if abs(px - x) > 3 or abs(py - y) > 3: continue
        if p.HitTest(V(x, y), MM(VD / 2 + CL)): return False
    return True
newvias = []
def clear_of_new(x, y):
    return all((x - a) ** 2 + (y - c_) ** 2 >= (VD + CL) ** 2 for a, c_ in newvias)
ripped = 0; made = 0; skipped = []
tracks = list(b.GetTracks())
gone = set()
def rip_near(seg_or_pt, net, rad):
    global ripped
    for t in tracks:
        if id(t) in gone or t.IsLocked() or t.GetNetCode() == net: continue
        if isinstance(t, pcbnew.PCB_VIA):
            dd = seg_or_pt.Distance(t.GetPosition()) / 1e6 if isinstance(seg_or_pt, pcbnew.SEG) else None
            hit = dd is not None and dd < rad + T(t.GetWidth(pcbnew.F_Cu)) / 2
        else:
            s2 = pcbnew.SEG(t.GetStart(), t.GetEnd())
            hit = seg_or_pt.Distance(s2) / 1e6 < rad + T(t.GetWidth()) / 2
        if hit: b.Remove(t); gone.add(id(t)); ripped += 1
for p in sorted(U.Pads(), key=lambda p: int(p.GetNumber()) if p.GetNumber().isdigit() else 999):
    n = p.GetNumber()
    if n not in want: continue
    px, py = T(p.GetPosition().x), T(p.GetPosition().y); dx, dy = px - cx, py - cy
    if abs(dx) > abs(dy): ux, uy = (1 if dx > 0 else -1), 0
    else: ux, uy = 0, (1 if dy > 0 else -1)
    out = int(n) % 2 == 0
    sx, sy = T(p.GetSize().x), T(p.GetSize().y); half = max(sx, sy) / 2
    perp = abs(dx) if ux else abs(dy)
    order = [5.35 + 0.6, 4.55 - 0.55] if out else [4.55 - 0.55, 5.35 + 0.6]
    done = False
    for D in order + [5.35 + 1.3]:
        vx = cx + ux * D if ux else px; vy = cy + uy * D if uy else py
        if not (clear_of_pads(vx, vy, p.GetNetCode()) and clear_of_new(vx, vy)): continue
        if D < 4.55 and (abs(vx - cx) < 1.7 + VD / 2 + CL + 0.1 and abs(vy - cy) < 1.7 + VD / 2 + CL + 0.1): continue
        seg = pcbnew.SEG(p.GetPosition(), V(vx, vy))
        rip_near(seg, p.GetNetCode(), TW / 2 + CL)
        rip_near(pcbnew.SEG(V(vx, vy), V(vx, vy)), p.GetNetCode(), VD / 2 + CL)
        t = pcbnew.PCB_TRACK(b); t.SetStart(p.GetPosition()); t.SetEnd(V(vx, vy)); t.SetWidth(MM(TW)); t.SetLayer(pcbnew.F_Cu); t.SetNet(p.GetNet()); t.SetLocked(True); b.Add(t)
        v = pcbnew.PCB_VIA(b); v.SetPosition(V(vx, vy)); v.SetWidth(MM(VD)); v.SetDrill(MM(VH)); v.SetNet(p.GetNet()); v.SetLocked(True); b.Add(v)
        newvias.append((vx, vy)); made += 1; done = True; break
    if not done: skipped.append(n)
print('fanned', made, 'ripped', ripped, 'skipped', skipped, 'of', sorted(want, key=int))
b.Save(sys.argv[3])
