"""prune.py in out : remove dangling tracks and vias (locked or not: the routers lock their own output), repeating
until none are left, and putting back any item whose removal would add an unconnected pair."""
import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1]); gone = []
def unc():
    b.BuildConnectivity(); c = b.GetConnectivity(); c.RecalculateRatsnest(); return c.GetUnconnectedCount(True)
base = unc(); total = 0
for rnd in range(40):
    c = b.GetConnectivity(); cand = []
    for t in b.GetTracks():
        if t.GetNetname().startswith(('/HDMI_', '/USB_UP')): continue   # the hand-built pairs stay as they are
        if isinstance(t, pcbnew.PCB_VIA):
            # a via is dangling when fewer than two copper items (tracks, pads, zone fills) meet it
            if len([i for i in c.GetConnectedItems(t) if i.m_Uuid.AsString() != t.m_Uuid.AsString()]) < 2: cand.append(t)
        elif c.TestTrackEndpointDangling(t, False): cand.append(t)
    n = 0
    for t in cand:
        b.Remove(t)
        if unc() > base: b.Add(t)
        else: gone.append(t); n += 1
    total += n
    if not n: break
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('removed', total, 'unconnected', unc())
