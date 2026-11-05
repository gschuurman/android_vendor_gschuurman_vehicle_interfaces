import pcbnew, re, sys
b = pcbnew.LoadBoard("buttonbar/buttonbar.kicad_pcb")
for t in list(b.GetTracks()): b.Remove(t)
s = open("buttonbar/buttonbar.ses").read()
s = s[s.index("(network_out"):]
nets = {n.GetNetname(): n for n in b.GetNetInfo().NetsByName().values()} if False else None
ni = b.GetNetInfo()
def mm(v): return pcbnew.FromMM(int(v) / 10000.0)
cnt = [0, 0]
for m in re.finditer(r'\(net\s+("?)([^"\s)]+)\1(.*?)(?=\n\s*\(net\s|\Z)', s, re.S):
    name, body = m.group(2), m.group(3)
    net = b.FindNet(name)
    for w in re.finditer(r'\(wire\s*\(path\s+(\S+)\s+(\d+)\s+([-\d\s]+)\)', body):
        lay = pcbnew.F_Cu if w.group(1) == "F.Cu" else pcbnew.B_Cu
        wd = mm(w.group(2)); c = list(map(int, w.group(3).split()))
        pts = [(c[i], c[i+1]) for i in range(0, len(c), 2)]
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(b); t.SetLayer(lay); t.SetWidth(wd)
            t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(-y1))); t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(-y2))); t.SetNet(net); b.Add(t); cnt[0] += 1
    for v in re.finditer(r'\(via\s+"[^"]*"\s+(-?\d+)\s+(-?\d+)', body):
        via = pcbnew.PCB_VIA(b); via.SetPosition(pcbnew.VECTOR2I(mm(v.group(1)), mm(-int(v.group(2)))))
        via.SetWidth(pcbnew.FromMM(1.0)); via.SetDrill(pcbnew.FromMM(0.5)); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); via.SetNet(net); b.Add(via); cnt[1] += 1
print("segments", cnt[0], "vias", cnt[1])
pcbnew.SaveBoard("buttonbar/buttonbar.kicad_pcb", b)
