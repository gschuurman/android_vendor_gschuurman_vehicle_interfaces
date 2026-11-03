"""fixclear.py in drc.json out : delete the unlocked track segments / vias named in clearance violations (grid-router
rounding leaves a few 0.001-0.01 mm misses); re-bridge the opened nets afterwards with a larger clearance."""
import pcbnew, sys, json
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); d = json.load(open(sys.argv[2]))
hits = []
for v in d['violations']:
    if v['type'] != 'clearance': continue
    for i in v['items']:
        if i['description'].startswith(('Track', 'Via')): hits.append((i['pos']['x'], i['pos']['y'], i['description'].split('[')[1].split(']')[0]))
gone = []; nets = set()
for t in list(b.GetTracks()):
    if t.IsLocked() and (isinstance(t, pcbnew.PCB_VIA) or T(t.GetLength()) > 0.5): continue   # tiny locked bits are router output
    for x, y, n in hits:
        if t.GetNetname() != n: continue
        if isinstance(t, pcbnew.PCB_VIA): hit = abs(T(t.GetPosition().x) - x) < 0.02 and abs(T(t.GetPosition().y) - y) < 0.02
        else: hit = pcbnew.SEG(t.GetStart(), t.GetEnd()).Distance(pcbnew.VECTOR2I(MM(x), MM(y))) < MM(0.02)
        if hit: b.Remove(t); gone.append(t); nets.add(n); break
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[3]); print(','.join(sorted(nets)))
