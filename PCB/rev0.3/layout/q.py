import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1]); nets=sys.argv[2].split(','); x0,y0,x1,y1=map(float,sys.argv[3:7])
N={pcbnew.F_Cu:'F',pcbnew.In1_Cu:'In1',pcbnew.In2_Cu:'In2',pcbnew.B_Cu:'B'}
f=lambda p:f"({p.x/1e6:.3f},{p.y/1e6:.3f})"
inb=lambda p:x0<=p.x/1e6<=x1 and y0<=p.y/1e6<=y1
for t in b.GetTracks():
    n=t.GetNetname()
    if nets!=['*'] and n not in nets: continue
    if isinstance(t,pcbnew.PCB_VIA):
        if inb(t.GetPosition()): print(n,'VIA',f(t.GetPosition()),t.GetWidth(pcbnew.F_Cu)/1e6,'L' if t.IsLocked() else '')
    elif inb(t.GetStart()) or inb(t.GetEnd()):
        print(n,N[t.GetLayer()],f(t.GetStart()),f(t.GetEnd()),t.GetWidth()/1e6,'L' if t.IsLocked() else '')
