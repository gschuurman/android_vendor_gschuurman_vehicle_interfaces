"""fixc3.py in out: the VSYS_IN feed from the B.Cu bus via at (18.45, 61.87) up into the PWR VSYS_IN pour ran on past
the via to y=59.0, through C3 pad 1 (BUCK_CB). Cut it back to run only from the via to the pour."""
import pcbnew, sys
MM = pcbnew.FromMM; T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1])
for t in list(b.GetTracks()):
    if isinstance(t, pcbnew.PCB_VIA) or t.GetNetname() != '/VSYS_IN' or t.GetLayer() != pcbnew.F_Cu: continue
    if abs(T(t.GetStart().x) - 18.525) < 0.01 and abs(T(t.GetEnd().x) - 18.525) < 0.01 and min(T(t.GetStart().y), T(t.GetEnd().y)) < 59.1:
        t.SetStart(pcbnew.VECTOR2I(MM(18.45), MM(61.87))); t.SetEnd(pcbnew.VECTOR2I(MM(18.45), MM(64.3))); t.SetLocked(True)
        print('cut back', t.GetNetname())
b.Save(sys.argv[2])
