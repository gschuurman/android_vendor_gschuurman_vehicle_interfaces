"""klinepcb.py in out : rev 0.6 PCB side of the K-line module socket.
J10 (1x8 male header under the USB module) is replaced by a 2x4 female socket at (82, 29), in the free strip between the
HDMI pairs and the USB module; F6 (PTC, VBAT_P -> VBAT_KLINE) sits under the USB module at (76, 34); H8 (M2 standoff for
the module) goes left of the HDMI corridor at (69.6, 18.5). The K-line module (about 25 x 17 mm, x 67-91, y 15-32) stacks
over the HDMI runs, clear of J13, J14 and the USB module. Copper of the remapped nets is removed for re-routing."""
import pcbnew, sys, uuid
MM = pcbnew.FromMM
FPLIB = 'C:/Program Files/KiCad/10.0/share/kicad/footprints'
b = pcbnew.LoadBoard(sys.argv[1])
def uid(tag): return str(uuid.uuid5(uuid.NAMESPACE_URL, f'carradio-rev06-{tag}'))
def net(n):
    ni = b.FindNet(n)
    if not ni: ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni)
    return ni
def place(lib, name, ref, value, x, y, rot, path, nets, fields=(), attrs=None):
    f = pcbnew.FootprintLoad(f'{FPLIB}/{lib}.pretty', name); f.SetFPID(pcbnew.LIB_ID(lib, name))
    f.SetReference(ref); f.SetValue(value); f.SetOrientationDegrees(rot)
    f.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    if path: f.SetPath(pcbnew.KIID_PATH(f'/{path}'))
    for k, v in fields:
        f.SetField(k, v)
        for fl in f.GetFields():
            if fl.GetName() == k: fl.SetVisible(False)
    if attrs is not None: f.SetAttributes(attrs)
    for p in f.Pads():
        n = nets.get(p.GetNumber()) if isinstance(nets, dict) else nets
        if n: p.SetNet(net(n))
    f.Value().SetVisible(False)
    r = f.Reference(); r.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0))); r.SetTextThickness(MM(0.15))
    b.Add(f); return f
old = b.FindFootprintByReference('J10'); oldpos = old.GetPosition()
gone = []   # keep removed items referenced: freeing them corrupts the SWIG bindings
b.Remove(old); gone.append(old)
for t in list(b.GetTracks()):
    # routes of the remapped nets go; their locked RP2350B escape stubs stay
    if t.GetNetname() in ('/EXP_GP32', '/EXP_GP33', '/EXP_GP28') and not t.IsLocked(): b.Remove(t); gone.append(t)
J = place('Connector_PinSocket_2.54mm', 'PinSocket_2x04_P2.54mm_Vertical', 'J10', 'K-line module socket', 82, 29, 90, uid('J10-1'),
          {'1': '/+3V3_MCU', '2': 'GND', '3': '/EXP_GP32', '4': '/EXP_GP33', '5': '/EXP_GP28', '6': 'GND', '7': '/VBAT_KLINE', '8': '/+5V_AON'},
          fields=(('LCSC', ''), ('MPN', '2x4 2.54mm female socket, 8.5mm body (same family as J23/J25/J27)')))
# centre the courtyard on (82, 29)
bb = J.GetCourtyard(pcbnew.F_CrtYd).BBox(); c = bb.GetCenter()
J.SetPosition(pcbnew.VECTOR2I(J.GetPosition().x + MM(82) - c.x, J.GetPosition().y + MM(28.9) - c.y))   # 0.1 mm up: clears the In1 +5V_SYS strip
place('Fuse', 'Fuse_1206_3216Metric', 'F6', 'PTC 0.2A hold 30V', 76, 34, 0, uid('F6-1'), {'1': '/VBAT_P', '2': '/VBAT_KLINE'},
      fields=(('LCSC', 'C883118'), ('MPN', 'BHFUSE BSMD1206-020-30V')))
h7 = b.FindFootprintByReference('H7')
place('MountingHole', 'MountingHole_2.2mm_M2_Pad_Via', 'H8', 'M2 standoff, K-line module', 69.6, 18.5, 0, None, 'GND', attrs=h7.GetAttributes())
# unlocked copper of other nets that the new pads hit is ripped for re-routing
new = [b.FindFootprintByReference(r) for r in ('J10', 'F6', 'H8')]
pads = [p for f in new for p in f.Pads()]
for t in list(b.GetTracks()):
    if t.IsLocked(): continue
    for p in pads:
        if t.GetNetCode() == p.GetNetCode(): continue
        if any(t.IsOnLayer(l) and p.IsOnLayer(l) and t.GetEffectiveShape(l).Collide(p.GetEffectiveShape(l), MM(0.2))
               for l in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu)):
            b.Remove(t); gone.append(t); break
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2])
bb = J.GetCourtyard(pcbnew.F_CrtYd).BBox()
print('J10 courtyard x %.2f-%.2f y %.2f-%.2f' % (pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetY()), pcbnew.ToMM(bb.GetBottom())),
      'pin1', [(round(pcbnew.ToMM(p.GetPosition().x), 2), round(pcbnew.ToMM(p.GetPosition().y), 2)) for p in J.Pads() if p.GetNumber() == '1'])
