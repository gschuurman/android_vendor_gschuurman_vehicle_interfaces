"""dropavdd.py in out: remove the RP2350B pin 61 (VREG_AVDD) inner escape stub + via when nothing else uses the via
(AVDD leaves on F.Cu outward); it closes the via ring around the exposed pad, cutting the EP GND off from the planes."""
import pcbnew, sys
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); P = pcbnew.VECTOR2I(MM(44.8), MM(26.0))
v = [t for t in b.GetTracks() if isinstance(t, pcbnew.PCB_VIA) and t.GetPosition() == P and t.GetNetname() == '/MCU_VREG_AVDD']
users = [t for t in b.GetTracks() if not isinstance(t, pcbnew.PCB_VIA) and t.GetNetname() == '/MCU_VREG_AVDD' and P in (t.GetStart(), t.GetEnd())]
if v and len(users) == 1 and users[0].GetLayer() == pcbnew.F_Cu:
    b.Remove(v[0]); b.Remove(users[0]); print('dropped AVDD inner via')
else: print('AVDD via kept', len(v), len(users))
b.Save(sys.argv[2])
