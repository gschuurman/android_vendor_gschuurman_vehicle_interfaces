"""dang.py in drc.json out netlist: remove items DRC flags as dangling on the given nets, if connectivity holds."""
import pcbnew, sys, json
b = pcbnew.LoadBoard(sys.argv[1]); d = json.load(open(sys.argv[2])); nets = set(sys.argv[4].split(','))
TR = {t.m_Uuid.AsString(): t for t in b.GetTracks()}
def unc():
    b.BuildConnectivity(); c = b.GetConnectivity(); c.RecalculateRatsnest(); return c.GetUnconnectedCount(True)
u0 = unc(); n = 0
for v in d['violations']:
    if v['type'] not in ('track_dangling', 'via_dangling'): continue
    for it in v['items']:
        t = TR.get(it['uuid'])
        if t is None or t.GetNetname() not in nets: continue
        b.Remove(t)
        if unc() > u0: b.Add(t)
        else: n += 1
b.Save(sys.argv[3]); print('removed', n)
