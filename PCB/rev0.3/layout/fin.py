"""fin.py in out : solid zone connection on pads that DRC calls thermally starved; drop the one-layer hub via."""
import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1]); ZS = list(b.Zones()); TR = list(b.GetTracks()); FP = {f.GetReference(): list(f.Pads()) for f in b.GetFootprints()}
for ref, num in (('U15', '9'), ('J7', '2')):
    for p in FP[ref]:
        if p.GetNumber() == num: p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
for t in TR:
    if isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == '/HUB2_3V3' and abs(t.GetPosition().x - 87950000) < 20000 and abs(t.GetPosition().y - 48400000) < 20000: b.Remove(t)
pcbnew.ZONE_FILLER(b).Fill(ZS); b.Save(sys.argv[2]); print('fin ok')
