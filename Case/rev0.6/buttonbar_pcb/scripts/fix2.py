import pcbnew
b=pcbnew.LoadBoard('buttonbar/buttonbar.kicad_pcb')
for fp in b.GetFootprints():
    if fp.GetReference().startswith('SW'):
        fp.Reference().SetLayer(pcbnew.F_Fab)
for d in b.GetDrawings():
    if isinstance(d,pcbnew.PCB_TEXT) and d.GetText() in("Play","Prev","Next","Home","Voice"):
        d.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8),pcbnew.FromMM(0.8)))
        p=d.GetPosition(); d.SetPosition(pcbnew.VECTOR2I(p.x,pcbnew.FromMM(100.7)))
pcbnew.SaveBoard('buttonbar/buttonbar.kicad_pcb',b)
pcbnew.WriteDRCReport(b,'buttonbar/drc.rpt',pcbnew.EDA_UNITS_MILLIMETRES,True)
