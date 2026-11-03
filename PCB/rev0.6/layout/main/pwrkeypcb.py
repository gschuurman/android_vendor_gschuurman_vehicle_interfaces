"""pwrkeypcb.py in out : rev 0.6 PCB side of the PhotoMOS VIM3 power key (schematic: ../schematic/pwrkey_sch.py).
Q1 (AO3400A, bottom left) and R19 go with all copper of /VIM3_PWR_KEY and /PWR_KEY_G. U22 (AQY210S, SO-4) goes on the
bottom side right next to J5 at (19.2, 15.0), the nearest spot clear of bottom copper and through-hole pins, so the two
switched wires are a few mm long. J5 pin 2 leaves GND. R12 becomes the 390 ohm LED resistor; its LED net and the GND pin
are routed afterwards (bridge.py)."""
import pcbnew, sys, uuid
MM = pcbnew.FromMM; T = pcbnew.ToMM
FPLIB = 'C:/Program Files/KiCad/10.0/share/kicad/footprints'
b = pcbnew.LoadBoard(sys.argv[1]); gone = []   # keep removed items referenced: freeing them corrupts the SWIG bindings
def uid(tag): return str(uuid.uuid5(uuid.NAMESPACE_URL, f'carradio-rev06-{tag}'))
def net(n):
    ni = b.FindNet(n)
    if not ni: ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni)
    return ni
oldpads = []   # GND stubs that ended on Q1's source / R19's GND pad go with them
for r in ('Q1', 'R19'):
    f = b.FindFootprintByReference(r)
    oldpads += [p.GetEffectiveShape(pcbnew.F_Cu) for p in f.Pads() if p.GetNetname() == 'GND']
    b.Remove(f); gone.append(f)
J5 = b.FindFootprintByReference('J5')
j5pad2 = [p for p in J5.Pads() if p.GetNumber() == '2'][0]
for t in list(b.GetTracks()):
    if t.GetNetname() in ('/VIM3_PWR_KEY', '/PWR_KEY_G'): b.Remove(t); gone.append(t); continue
    # GND copper that ended on J5 pin 2
    if t.GetNetname() == 'GND' and not isinstance(t, pcbnew.PCB_VIA) and any(
            j5pad2.HitTest(pt) for pt in (t.GetStart(), t.GetEnd())):
        b.Remove(t); gone.append(t); continue
    if t.GetNetname() == 'GND' and not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == pcbnew.F_Cu and any(
            sh.Collide(pt) for sh in oldpads for pt in (t.GetStart(), t.GetEnd())):
        b.Remove(t); gone.append(t)
f = pcbnew.FootprintLoad(f'{FPLIB}/Package_SO.pretty', 'SO-4_4.4x4.3mm_P2.54mm'); f.SetFPID(pcbnew.LIB_ID('Package_SO', 'SO-4_4.4x4.3mm_P2.54mm'))
f.SetReference('U22'); f.SetValue('AQY210S'); f.SetPath(pcbnew.KIID_PATH(f'/{uid("U22")}'))
for k, v in (('LCSC', ''), ('MPN', 'Panasonic AQY210S PhotoMOS 350V 120mA 1 Form A, SOP-4 (own stock)')):
    f.SetField(k, v)
    for fl in f.GetFields():
        if fl.GetName() == k: fl.SetVisible(False)
b.Add(f); f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
f.SetPosition(pcbnew.VECTOR2I(MM(19.2), MM(15.0))); f.SetOrientationDegrees(90)
f.Value().SetVisible(False)
r = f.Reference(); r.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0))); r.SetTextThickness(MM(0.15))
pos = {p.GetNumber(): p.GetPosition() for p in f.Pads()}
# the output is a bidirectional switch: give J5 pin 1 the nearer output pad so the two short wires do not cross
d = lambda a, c: (a - c).EuclideanNorm()
j5 = {p.GetNumber(): p.GetPosition() for p in J5.Pads()}
a_pad = '4' if d(pos['4'], j5['1']) + d(pos['3'], j5['2']) <= d(pos['3'], j5['1']) + d(pos['4'], j5['2']) else '3'
NETS = {'1': '/PWR_KEY_LED', '2': 'GND', a_pad: '/VIM3_PWR_KEY_A', ('3' if a_pad == '4' else '4'): '/VIM3_PWR_KEY_B'}
for p in f.Pads(): p.SetNet(net(NETS[p.GetNumber()]))
for p in J5.Pads(): p.SetNet(net({'1': '/VIM3_PWR_KEY_A', '2': '/VIM3_PWR_KEY_B'}[p.GetNumber()]))
R12 = b.FindFootprintByReference('R12'); R12.SetValue('390Ω')
R12.SetField('LCSC', 'C23151'); R12.SetField('MPN', 'UNI-ROYAL 0603WAF3900T5E 390 1%')
for p in R12.Pads():
    if p.GetNumber() == '2': p.SetNet(net('/PWR_KEY_LED'))
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
print('U22 pads', {n: (round(T(v.x), 2), round(T(v.y), 2)) for n, v in pos.items()}, 'J5 pin 1 <- U22 pin', a_pad)
print('J5', {n: (round(T(v.x), 2), round(T(v.y), 2)) for n, v in j5.items()})
