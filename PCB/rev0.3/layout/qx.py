import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1]); x0,y0,x1,y1=map(float,sys.argv[2:6])
N={pcbnew.F_Cu:'F',pcbnew.In1_Cu:'In1',pcbnew.In2_Cu:'In2',pcbnew.B_Cu:'B'}
f=lambda p:f"({p.x/1e6:.3f},{p.y/1e6:.3f})"
for t in b.GetTracks():
    bb=t.GetBoundingBox()
    if bb.GetRight()/1e6<x0 or bb.GetLeft()/1e6>x1 or bb.GetBottom()/1e6<y0 or bb.GetTop()/1e6>y1: continue
    if isinstance(t,pcbnew.PCB_VIA): print(t.GetNetname(),'VIA',f(t.GetPosition()),t.GetWidth(pcbnew.F_Cu)/1e6)
    else: print(t.GetNetname(),N[t.GetLayer()],f(t.GetStart()),f(t.GetEnd()),t.GetWidth()/1e6)
for z in b.Zones():
    bb=z.GetBoundingBox()
    if bb.GetRight()/1e6<x0 or bb.GetLeft()/1e6>x1 or bb.GetBottom()/1e6<y0 or bb.GetTop()/1e6>y1: continue
    print('ZONE',z.GetZoneName(),z.GetNetname(),[N.get(l,l) for l in z.GetLayerSet().Seq()])
