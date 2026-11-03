"""Add maze-router results to a board and refill zones. usage: addtracks.py in.kicad_pcb maze.json out.kicad_pcb"""
import pcbnew, sys, json
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); r = json.load(open(sys.argv[2]))
L = {'F': pcbnew.F_Cu, 'In2': pcbnew.In2_Cu, 'B': pcbnew.B_Cu}
n = 0
for res in r['results']:
    net = b.FindNet(res['net'])
    for l, a, c, w in res['tracks']:
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1]))); t.SetEnd(pcbnew.VECTOR2I(MM(c[0]), MM(c[1])))
        t.SetWidth(MM(w)); t.SetLayer(L[l]); t.SetNet(net); b.Add(t); n += 1
    for x, y in res['vias']:
        v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetWidth(MM(0.45)); v.SetDrill(MM(0.2)); v.SetNet(net); b.Add(v)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(sys.argv[3]); print('added', n, 'tracks')
