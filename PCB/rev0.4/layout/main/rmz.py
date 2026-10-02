"""rmz.py in out: drop the full-board GND pours on F/In2/B before export (Freerouting would see them as planes
blocking those layers); post_route4.py adds them back."""
import pcbnew, sys
b = pcbnew.LoadBoard(sys.argv[1])
for z in [z for z in b.Zones() if z.GetNetname() == 'GND' and z.GetZoneName() in ('In2 GND', 'B GND', 'F GND') + (('GND plane',) if len(sys.argv) > 3 else ())]: b.Remove(z)
b.Save(sys.argv[2]); print('ok')
