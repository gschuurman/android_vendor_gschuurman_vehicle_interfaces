"""Apply maze2 output: delete ripped tracks (by uuid), add new copper, refill. usage: apply2.py in.kicad_pcb m2.json out.kicad_pcb"""
import pcbnew, sys, json
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); r = json.load(open(sys.argv[2])); ZS = list(b.Zones()); TR = list(b.GetTracks())
rm = set(r['removed']); n_rm = 0
for t in TR:
    if t.m_Uuid.AsString() in rm: b.Remove(t); n_rm += 1
L = {'F': pcbnew.F_Cu, 'In2': pcbnew.In2_Cu, 'B': pcbnew.B_Cu}
for it in r['added']:
    net = b.FindNet(it['net'])
    if it['kind'] == 'seg':
        a, c, hw = it['data']
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1]))); t.SetEnd(pcbnew.VECTOR2I(MM(c[0]), MM(c[1])))
        t.SetWidth(MM(2 * hw)); t.SetLayer(L[it['layer']]); t.SetNet(net); b.Add(t)
    else:
        (x, y), r_ = it['data']
        v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetWidth(MM(0.45)); v.SetDrill(MM(0.2)); v.SetNet(net); b.Add(v)
pcbnew.ZONE_FILLER(b).Fill(ZS)
b.Save(sys.argv[3]); print('removed', n_rm, 'added', len(r['added']))
