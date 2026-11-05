import pcbnew
from design import *
b=pcbnew.LoadBoard('buttonbar/buttonbar.kicad_pcb')
P=lambda x,y: pcbnew.VECTOR2I(pcbnew.FromMM(100+L/2+x),pcbnew.FromMM(100+y))
for fp in b.GetFootprints():
    if fp.GetReference().startswith('SW'):
        fp.Reference().SetPosition(fp.GetPosition())
for d in b.GetDrawings():
    if isinstance(d,pcbnew.PCB_TEXT) and d.GetText()=="Play/Pause":
        d.SetText("Play")
pcbnew.SaveBoard('buttonbar/buttonbar.kicad_pcb',b)
pcbnew.WriteDRCReport(b,'buttonbar/drc.rpt',pcbnew.EDA_UNITS_MILLIMETRES,True)
