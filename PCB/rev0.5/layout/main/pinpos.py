import pcbnew, json, sys
b = pcbnew.LoadBoard(sys.argv[1]); T = pcbnew.ToMM
out = {'u20': {}, 'nets': {}}
for p in b.FindFootprintByReference('U20').Pads(): out['u20'][p.GetNumber()] = (T(p.GetPosition().x), T(p.GetPosition().y))
for f in b.GetFootprints():
    for p in f.Pads():
        n = p.GetNetname()
        if not n: continue
        others = [q.GetNetname() for q in f.Pads() if q.GetNumber() != p.GetNumber()]
        out['nets'].setdefault(n, []).append((f.GetReference(), p.GetNumber(), T(p.GetPosition().x), T(p.GetPosition().y), others))
json.dump(out, open(sys.argv[2], 'w'))
