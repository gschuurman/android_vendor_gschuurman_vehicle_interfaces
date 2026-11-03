"""clean.py in out : repeatedly remove dangling unlocked tracks/vias, keeping any whose removal adds an unconnected item."""
import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1]); ZS = list(b.Zones()); TR = list(b.GetTracks()); gone = set()
def unc():
    b.BuildConnectivity(); c = b.GetConnectivity(); c.RecalculateRatsnest(); return c.GetUnconnectedCount(True)
base = unc(); print('unconnected start', base)
total = 0
for rnd in range(30):
    c = b.GetConnectivity(); cand = []
    for t in TR:
        if id(t) in gone or t.IsLocked(): continue
        if isinstance(t, pcbnew.PCB_VIA):
            if c.TestTrackEndpointDangling(t, False) if hasattr(c, 'TestTrackEndpointDangling') else False: cand.append(t)
        elif c.TestTrackEndpointDangling(t, False):
            cand.append(t)
    n = 0
    for t in cand:
        b.Remove(t)
        if unc() > base: b.Add(t)
        else: gone.add(id(t)); n += 1
    total += n
    if not n: break
print('removed', total, 'unconnected end', unc())
pcbnew.ZONE_FILLER(b).Fill(ZS); b.Save(sys.argv[2])
