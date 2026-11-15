import pcbnew, sys
sys.path.insert(0, ".")
from design import *
F = NAME + "/" + NAME + ".kicad_pcb"
b = pcbnew.LoadBoard(F)
def V(x, y): return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
# references go to the fab layer (assembly drawing), centred on the part
for fp in b.GetFootprints():
    t = fp.Reference()
    t.SetLayer(pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab)
    p = fp.GetPosition()
    t.SetPosition(V(82.0, 28.9) if fp.GetReference() == 'J1' else pcbnew.VECTOR2I(p.x, p.y))
    t.SetTextSize(V(0.8, 0.8)); t.SetTextThickness(pcbnew.FromMM(0.12))
    t.SetTextAngleDegrees(0)
# drop the old free texts and write the silkscreen labels
dead = [d for d in b.GetDrawings() if d.GetClass() in ('PCB_TEXT', 'PTEXT')]
for d in dead: b.Remove(d)
def silk(txt, x, y, size=0.8, layer=pcbnew.F_SilkS, rot=0, mirror=False):
    t = pcbnew.PCB_TEXT(b); t.SetText(txt); t.SetPosition(V(x, y)); t.SetLayer(layer)
    t.SetTextSize(V(size, size)); t.SetTextThickness(pcbnew.FromMM(0.13)); t.SetTextAngleDegrees(rot)
    if mirror: t.SetMirrored(True)
    b.Add(t)
for args in SILK2: silk(*args)
pcbnew.SaveBoard(F, b)
