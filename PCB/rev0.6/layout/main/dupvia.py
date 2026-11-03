"""dupvia.py in out : of two overlapping vias of the same net, remove one (a Gerber-only DFM reports the pair as pad spacing
0 mm). Kept when removing it would add an unconnected pair."""
import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); gone = []
def unc():
    b.BuildConnectivity(); c = b.GetConnectivity(); c.RecalculateRatsnest(); return c.GetUnconnectedCount(True)
base = unc(); n = 0
vias = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA)]
dead = set()
for i, a in enumerate(vias):
    if a.m_Uuid.AsString() in dead: continue
    for c in vias[i + 1:]:
        if c.m_Uuid.AsString() in dead or c.GetNetCode() != a.GetNetCode(): continue
        if (a.GetPosition() - c.GetPosition()).EuclideanNorm() < (a.GetWidth(pcbnew.F_Cu) + c.GetWidth(pcbnew.F_Cu)) // 2 + MM(0.1):
            victim = c if not c.IsLocked() or a.IsLocked() else a
            b.Remove(victim)
            if unc() > base: b.Add(victim)
            else: gone.append(victim); dead.add(victim.m_Uuid.AsString()); n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('removed', n, 'unconnected', unc())
