"""prune3.py in drc.json out : finishing pass after prune2.py.
- copper on pins with no net function (nets named unconnected-(...)): the fan-out gave GPIO44-47 a stub and via
- zero-length tracks
- reported dangling track ends that overlap another track of the net without meeting its centreline: snapped onto it."""
import pcbnew, sys, json
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); d = json.load(open(sys.argv[2])); gone = []
def unc():
    b.BuildConnectivity(); c = b.GetConnectivity(); c.RecalculateRatsnest(); return c.GetUnconnectedCount(True)
base = unc(); n_unc = n_zero = n_snap = 0
for t in list(b.GetTracks()):
    if t.GetNetname().startswith('unconnected-') or t.GetNetCode() == 0: b.Remove(t); gone.append(t); n_unc += 1
    elif not isinstance(t, pcbnew.PCB_VIA) and t.GetLength() == 0: b.Remove(t); gone.append(t); n_zero += 1
for v in d['violations']:
    if v['type'] != 'track_dangling': continue
    i = v['items'][0]; net = i['description'].split('[')[1].split(']')[0]; p = pcbnew.VECTOR2I(MM(i['pos']['x']), MM(i['pos']['y']))
    ts = [t for t in b.GetTracks() if t.GetNetname() == net and not isinstance(t, pcbnew.PCB_VIA) and pcbnew.SEG(t.GetStart(), t.GetEnd()).Distance(p) < MM(0.02)]
    if not ts: continue
    t = ts[0]; tid = t.m_Uuid.AsString(); l = t.GetLayer()
    others = [o for o in b.GetTracks() if o.m_Uuid.AsString() != tid and o.GetNetCode() == t.GetNetCode() and not isinstance(o, pcbnew.PCB_VIA) and o.GetLayer() == l]
    for get, put in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
        e = pcbnew.VECTOR2I(get())
        # already anchored on another track's end or centreline?
        if any(pcbnew.SEG(o.GetStart(), o.GetEnd()).Distance(e) < MM(0.001) for o in others): continue
        cands = [o for o in others if pcbnew.SEG(o.GetStart(), o.GetEnd()).Distance(e) < (t.GetWidth() + o.GetWidth()) // 2]
        if not cands: continue
        o = min(cands, key=lambda o: pcbnew.SEG(o.GetStart(), o.GetEnd()).Distance(e))
        q = pcbnew.SEG(o.GetStart(), o.GetEnd()).NearestPoint(e); put(q)
        if unc() > base: put(e)
        else: n_snap += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[3])
print('no-net copper', n_unc, 'zero-length', n_zero, 'snapped', n_snap, 'unconnected', unc())
