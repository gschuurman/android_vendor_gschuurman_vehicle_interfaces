"""padtrim.py in out : open the three SMD pad gaps below JLCPCB's 0.15 mm pad-to-pad minimum (standard land patterns:
CSD18543Q3A Q11/Q12 pins 3-4 0.141 mm, TPS55288 U12 pins 7-8 0.145 mm) by trimming the pads 0.01 mm."""
import pcbnew, sys
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
for ref in ('Q11', 'Q12'):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() in ('3', '4'):
            s = p.GetSize(pcbnew.F_Cu); p.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(s.x, s.y - MM(0.01)))   # 0.50 -> 0.49 across the gap
u = b.FindFootprintByReference('U12')
p8 = [p for p in u.Pads() if p.GetNumber() == '8'][0]
s = p8.GetSize(pcbnew.F_Cu); p8.SetSize(pcbnew.F_Cu, pcbnew.VECTOR2I(s.x - MM(0.01), s.y))           # 0.25 -> 0.24 wide
p8.SetPosition(pcbnew.VECTOR2I(p8.GetPosition().x + MM(0.005), p8.GetPosition().y))                  # away from pin 7
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('ok')
