import pcbnew
F='buttonbar_v4/buttonbar_v4.kicad_pcb'
def key(p): return (round(pcbnew.ToMM(p.x),3), round(pcbnew.ToMM(p.y),3))
b=pcbnew.LoadBoard(F)
b.GetDesignSettings().m_CopperEdgeClearance = pcbnew.FromMM(0.25)
# Freerouting left back-and-forth stubs: segment pairs A->B / B->A whose far end touches nothing else
segs=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK']
cnt={}
for t in segs:
    for e in (t.GetStart(),t.GetEnd()): cnt[(key(e),t.GetLayer())]=cnt.get((key(e),t.GetLayer()),[])+[t]
vias={key(v.GetPosition()) for v in b.GetTracks() if v.GetClass()=='PCB_VIA'}
def onpad(p,L):
    return any(pad.IsOnLayer(L) and pad.HitTest(p) for fp in b.GetFootprints() for pad in fp.Pads())
dead=set()
for (k,L),ts in cnt.items():
    others={(key(t.GetStart()),key(t.GetEnd())) and frozenset((key(t.GetStart()),key(t.GetEnd()))) for t in ts}
    if len(others)==1 and k not in vias and not onpad(pcbnew.VECTOR2I(pcbnew.FromMM(k[0]),pcbnew.FromMM(k[1])),L):
        for t in ts: dead.add(t)
print('stubs removed', len(dead))
for t in dead: b.Remove(t)
pcbnew.SaveBoard(F,b)
b=pcbnew.LoadBoard(F)
pcbnew.WriteDRCReport(b,'buttonbar_v4/drc.rpt',pcbnew.EDA_UNITS_MILLIMETRES,True)
# lonely vias (track on one layer only)
b=pcbnew.LoadBoard(F)
segs=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK']
dead=[]
for v in b.GetTracks():
    if v.GetClass()!='PCB_VIA': continue
    k=key(v.GetPosition())
    layers={t.GetLayer() for t in segs if k in (key(t.GetStart()),key(t.GetEnd()))}
    if len(layers)<2: dead.append(v)
for v in dead: b.Remove(v)
print('lonely vias removed',len(dead))
pcbnew.SaveBoard(F,b)
b=pcbnew.LoadBoard(F)
pcbnew.WriteDRCReport(b,'buttonbar_v4/drc.rpt',pcbnew.EDA_UNITS_MILLIMETRES,True)
