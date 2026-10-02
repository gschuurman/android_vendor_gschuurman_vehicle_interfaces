"""swapj11.py in out : replace the SMA J11 with a U.FL receptacle on the routed GNSS module."""
import pcbnew, sys
sys.path.insert(0, '/w/gm')
from netparse import comps
MM = pcbnew.FromMM; V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y)); T = pcbnew.ToMM
c = comps('/w/gm/net_carradio_gnss_rev04.net')['J11']
NEW = pcbnew.FootprintLoad('/usr/share/kicad/footprints/Connector_Coaxial.pretty', 'U.FL_Hirose_U.FL-R-SMT-1_Vertical')
b = pcbnew.LoadBoard(sys.argv[1])
old = b.FindFootprintByReference('J11'); p1 = [p for p in old.Pads() if p.GetNumber() == '1'][0]
YS = T(p1.GetPosition().y); oldx = T(p1.GetPosition().x); b.Remove(old)
f = NEW; f.SetFPID(pcbnew.LIB_ID('Connector_Coaxial', 'U.FL_Hirose_U.FL-R-SMT-1_Vertical')); f.SetReference('J11'); f.SetValue(c['val'])
f.SetPath(pcbnew.KIID_PATH('/' + c['uuid'])); b.Add(f); f.SetOrientationDegrees(180); f.SetPosition(V(3.3, YS))
for p in f.Pads(): p.SetNet(b.FindNet('/GNSS_RF' if p.GetNumber() == '1' else 'GND'))
np1 = [p for p in f.Pads() if p.GetNumber() == '1'][0].GetPosition()
n = 0
for t in b.GetTracks():
    if t.GetNetname() == '/GNSS_RF' and not isinstance(t, pcbnew.PCB_VIA):
        for get, setf in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
            if abs(T(get().x) - oldx) < 0.05 and abs(T(get().y) - YS) < 0.05: setf(np1); n += 1
print('RF ends moved', n, 'pad1 at', T(np1.x), T(np1.y), 'old', oldx)
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
