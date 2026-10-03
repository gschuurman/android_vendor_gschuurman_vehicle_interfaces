"""rmshort.py in drc.json out : delete unlocked tracks/vias named in shorting_items / via_dangling / annular_width violations."""
import pcbnew, sys, json
b = pcbnew.LoadBoard(sys.argv[1]); d = json.load(open(sys.argv[2]))
MM = pcbnew.FromMM; pts = []
for v in d['violations']:
    if v['type'] in ('shorting_items', 'via_dangling', 'annular_width', 'solder_mask_bridge'):
        for i in v['items']:
            if i['description'].startswith(('Track', 'Via')): pts.append((i['pos']['x'], i['pos']['y'], i['description'].split('[')[1].split(']')[0]))
n = 0
for t in list(b.GetTracks()):
    if t.IsLocked(): continue
    for x, y, net in pts:
        if t.GetNetname() != net: continue
        if isinstance(t, pcbnew.PCB_VIA):
            hit = abs(pcbnew.ToMM(t.GetPosition().x) - x) < 0.02 and abs(pcbnew.ToMM(t.GetPosition().y) - y) < 0.02
        else:
            hit = pcbnew.SEG(t.GetStart(), t.GetEnd()).Distance(pcbnew.VECTOR2I(MM(x), MM(y))) < MM(0.02)
        if hit: b.Remove(t); n += 1; break
print('removed', n); b.Save(sys.argv[3])
