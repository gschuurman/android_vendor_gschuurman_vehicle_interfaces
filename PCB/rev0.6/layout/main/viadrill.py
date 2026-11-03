"""viadrill.py in out [drill] : enlarge the drill of all 0.2 mm vias to `drill` (0.3 mm) keeping their 0.45 mm pads, so the
main board fits JLCPCB's standard via option (0.3 mm hole / 0.4-0.45 mm pad, no surcharge)."""
import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1]); d = MM(float(sys.argv[3]) if len(sys.argv) > 3 else 0.3); n = 0
for v in b.GetTracks():
    if isinstance(v, pcbnew.PCB_VIA) and v.GetDrill() < d: v.SetDrill(d); n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('vias re-drilled', n)
