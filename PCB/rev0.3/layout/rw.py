"""rw.py in.kicad_pcb out.kicad_pcb : TPS55288 rework after the TI layout review (SLVAER0C).
Net ties for ISP/ISN Kelvin sense and a separate AGND, control parts clustered at U12."""
import pcbnew, sys
MM = pcbnew.FromMM
P = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
FPDIR = '/usr/share/kicad/footprints'
NTS = {}
for ref in ('NT1', 'NT2', 'NT3'):
    NTS[ref] = pcbnew.FootprintLoad(f'{FPDIR}/NetTie.pretty', 'NetTie-2_SMD_Pad0.5mm')
b = pcbnew.LoadBoard(sys.argv[1])
TR = list(b.GetTracks()); FP = {f.GetReference(): f for f in b.GetFootprints()}; ZS = list(b.Zones())
L = {'F': pcbnew.F_Cu, 'In2': pcbnew.In2_Cu, 'B': pcbnew.B_Cu}

def net(name):
    n = b.FindNet(name)
    if n is None:
        n = pcbnew.NETINFO_ITEM(b, name); b.Add(n)
    return n
for nm in ('/BB_ISP', '/BB_ISN', '/BB_AGND'): net(nm)

# ---- pad nets (schematic change)
for ref, pad, nm in [('U12', '7', '/BB_AGND'), ('U12', '10', '/BB_AGND'), ('U12', '12', '/BB_ISP'), ('U12', '13', '/BB_ISN'),
                     ('R67', '2', '/BB_AGND'), ('R68', '2', '/BB_AGND'), ('R69', '2', '/BB_AGND'), ('R70', '2', '/BB_AGND'),
                     ('C54', '2', '/BB_AGND'), ('C55', '2', '/BB_AGND')]:
    p = [q for q in FP[ref].Pads() if q.GetNumber() == pad][0]; p.SetNet(net(nm))

# ---- remove old copper
inwin = lambda p, x0, y0, x1, y1: x0 <= p.x / 1e6 <= x1 and y0 <= p.y / 1e6 <= y1
def pts(t): return [t.GetPosition()] if isinstance(t, pcbnew.PCB_VIA) else [t.GetStart(), t.GetEnd()]
def near(p, x, y): return abs(p.x / 1e6 - x) < 0.012 and abs(p.y / 1e6 - y) < 0.012
kill = []
WHOLE = {'/BB_FSW', '/BB_COMP', '/BB_COMP_RC', '/BB_MODE', '/BB_CDC', '/BB_ILIM', '/BB_VCC', '/BB_BOOT1', '/BB_BOOT2'}
# (net, list of points identifying a track/via end) to delete
SPOT = {
    'GND': [(42.525, 63.75), (43.525, 63.75), (42.625, 66.0), (43.575, 66.0), (43.55, 60.225), (46.75, 64.925), (47.775, 64.925),
            (32.8, 70.75), (33.275, 70.75), (33.5, 71.45), (34.65, 69.569), (35.87, 68.67), (35.874, 68.983)],
    '/BB_VOUT': [(37.047, 68.724), (37.047, 69.054)],
    '/+5V_SYS': [(39.3, 69.25), (39.3, 69.35), (39.4, 69.45), (42.85, 72.85), (43.0, 73.05)],
    '/MCU_TEMP_ADC': [(41.1, 63.5), (41.2, 62.5), (41.319, 61.033), (41.319, 62.441)],
}
for t in TR:
    n = t.GetNetname()
    if n in WHOLE and all(inwin(p, 28, 54, 50, 78) for p in pts(t)): kill.append(t); continue
    if n in SPOT and any(near(p, x, y) for p in pts(t) for x, y in SPOT[n]):
        # keep R66's pad stub (32.325 -> 32.8) out of the GND list? it is removed and redrawn below
        kill.append(t); continue
    if n == '/RPP_G' and not t.IsLocked() and any(inwin(p, 30.9, 68.5, 34.5, 71.0) for p in pts(t)): kill.append(t); continue
    if n == '/LUX_SCL' and not t.IsLocked() and t.GetLayer() == pcbnew.B_Cu and any(inwin(p, 35, 69, 44, 73.5) for p in pts(t)): kill.append(t); continue
    if n == '/VIM3_PWR_EN' and not t.IsLocked() and any(near(p, 47.15, 63.4) for p in pts(t)): kill.append(t); continue
    if n == '/I2S_DOUT0' and not t.IsLocked() and not isinstance(t, pcbnew.PCB_VIA) and t.GetLayer() == pcbnew.F_Cu and any(inwin(p, 43.0, 55.0, 51.0, 63.0) for p in pts(t)): kill.append(t); continue
    if any(near(p, x, y) for p in pts(t) for x, y in [(43.275, 60.225), (47.775, 60.925)]): kill.append(t); continue
    if n == '/DAC_XSMT' and not t.IsLocked() and any(inwin(p, 40.4, 71.0, 47.0, 74.0) for p in pts(t)): kill.append(t); continue
# old ISN stub and via (pin 13) keep their geometry but move to BB_ISN
for t in TR:
    if t.GetNetname() == '/+5V_SYS' and any(near(p, 38.5, 68.45) or near(p, 38.25, 68.45) for p in pts(t)):
        t.SetNet(net('/BB_ISN'))
seen = set()
for t in kill:
    if id(t) in seen: continue
    seen.add(id(t)); b.Remove(t)
# R66's GND stub (32.325,70.75)->(32.8,70.75) shares a point with the removed list; make sure it is gone too
print('removed', len(seen))

# ---- move parts
def move(ref, x, y, rot):
    f = FP[ref]; f.SetPosition(P(x, y)); f.SetOrientationDegrees(rot)
move('C58', 36.6, 70.7, 180); move('C59', 36.6, 72.8, 180); move('C56', 36.6, 74.9, 180); move('C57', 36.6, 77.0, 180)
move('C53', 38.85, 64.4, 90)
move('C52', 37.3, 63.58, 90)
move('C55', 40.4, 64.2, 90)
move('R71', 41.95, 64.2, 90)
move('C54', 41.95, 61.15, 90)
move('R69', 43.5, 64.2, 90)
move('R70', 45.05, 64.2, 90)
move('R67', 46.6, 64.2, 90)
move('R68', 33.88, 70.55, 270)
move('C103', 43.85, 57.5, 90)

# ---- net ties
for ref, uid, x, y, rot, n1, n2 in [('NT1', 'c69d1cd4-d0a7-5e20-b48e-a7c5bb8c2bd6', 42.5, 70.45, 90, '/BB_ISP', '/BB_VOUT'),
                                    ('NT2', '070f7149-8f4b-5c1a-9813-580a61387149', 41.0, 74.55, -90, '/BB_ISN', '/+5V_SYS'),
                                    ('NT3', 'c879361d-139d-5dfa-9403-313b3d79467a', 39.85, 63.625, 180, '/BB_AGND', 'GND')]:
    f = NTS[ref]; f.SetFPID(pcbnew.LIB_ID('NetTie', 'NetTie-2_SMD_Pad0.5mm'))
    f.SetReference(ref); f.SetValue('NetTie'); f.SetPath(pcbnew.KIID_PATH('/' + uid))
    f.SetField('MPN', 'net tie (copper only, not a part)')
    for fld in f.GetFields(): fld.SetVisible(False)
    b.Add(f); f.SetPosition(P(x, y)); f.SetOrientationDegrees(rot)
    for p in f.Pads(): p.SetNet(net(n1 if p.GetNumber() == '1' else n2))
    print(ref, [(p.GetNumber(), p.GetNetname(), round(p.GetPosition().x / 1e6, 3), round(p.GetPosition().y / 1e6, 3)) for p in f.Pads()])

# ---- new copper
def seg(nm, ly, path, w=0.2):
    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(x1, y1)); t.SetEnd(P(x2, y2)); t.SetWidth(MM(w)); t.SetLayer(L[ly]); t.SetNet(net(nm)); t.SetLocked(True); b.Add(t)
def via(nm, x, y, d=0.45, h=0.2):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(x, y)); v.SetWidth(MM(d)); v.SetDrill(MM(h)); v.SetNet(net(nm)); v.SetLocked(True); b.Add(v)
# PGND pin 9 straight to the first output cap; AGND pin 10 and DITH pin 7 drop to vias
seg('GND', 'F', [(35.38, 68.98), (35.38, 70.0)], 0.25)
seg('/BB_AGND', 'F', [(35.87, 68.98), (35.87, 69.45)]); via('/BB_AGND', 35.87, 69.45)
seg('/BB_AGND', 'F', [(33.8, 68.5), (33.55, 68.5)]); via('/BB_AGND', 33.55, 68.5)
# FSW to R68 (bottom left), R68's AGND end to a via
seg('/BB_FSW', 'F', [(34.87, 68.98), (34.87, 69.15), (34.6, 69.42), (33.88, 69.42)])
seg('/BB_AGND', 'F', [(33.88, 71.375), (33.88, 72.35)]); via('/BB_AGND', 33.88, 72.35)
# R66 GND moved down to make room for R68
seg('GND', 'F', [(32.325, 70.75), (32.325, 71.75)], 0.3); via('GND', 32.325, 71.75)
# Kelvin sense: ISP and ISN as a pair on In2, crossing over to F at R74
seg('/BB_ISP', 'F', [(37.1, 68.98), (37.1, 69.3), (37.35, 69.55)]); via('/BB_ISP', 37.35, 69.55)
seg('/BB_ISP', 'In2', [(37.35, 69.55), (38.893, 69.55), (41.793, 72.45), (42.5, 72.45)]); via('/BB_ISP', 42.5, 72.45)
seg('/BB_ISP', 'F', [(42.5, 72.45), (42.5, 70.95)])
seg('/BB_ISN', 'In2', [(38.5, 68.45), (41.0, 70.95)]); via('/BB_ISN', 41.0, 70.95)
seg('/BB_ISN', 'F', [(41.0, 70.95), (41.0, 74.05)])
# bootstrap caps on F, no vias
seg('/BB_BOOT2', 'F', [(37.05, 65.02), (37.05, 64.7)], 0.25)
seg('/BB_BOOT1', 'F', [(35.75, 65.02), (35.75, 63.6), (35.5, 63.35), (33.05, 63.35)], 0.25)
# VCC cap right at pin 19, its ground straight to the plane
seg('/BB_VCC', 'F', [(38.0, 65.5), (38.85, 65.3)], 0.3)
seg('GND', 'F', [(38.85, 62.7), (38.85, 63.5)], 0.3); via('GND', 38.85, 62.7)
# control pins fan out to the row of parts above the traces
seg('/BB_COMP', 'F', [(38.2, 66.0), (40.1, 66.0), (40.4, 65.7), (40.4, 64.975)])
seg('/BB_COMP', 'F', [(40.4, 65.0), (41.95, 65.0)])
seg('/BB_ILIM', 'F', [(38.2, 66.5), (43.1, 66.5), (43.5, 66.1), (43.5, 65.025)])
seg('/BB_CDC', 'F', [(38.2, 67.0), (44.65, 67.0), (45.05, 66.6), (45.05, 65.025)])
seg('/BB_MODE', 'F', [(38.2, 67.5), (46.2, 67.5), (46.6, 67.1), (46.6, 65.025)])
seg('/BB_COMP_RC', 'F', [(41.95, 63.375), (41.95, 61.925)])
# board thermistor filter cap beside TH1
seg('/MCU_TEMP_ADC', 'F', [(42.25, 58.3), (43.85, 58.3)])
seg('GND', 'F', [(42.25, 56.7), (43.85, 56.7)])

# ---- zones
def setpoly(z, pts):
    o = z.Outline(); o.RemoveAllContours(); o.NewOutline()
    for x, y in pts: o.Append(MM(x), MM(y))
for z in ZS:
    nm = z.GetZoneName()
    if nm == 'PWR BB_SW2':
        setpoly(z, [(34.7, 63.0), (36.05, 63.0), (36.05, 64.802), (36.122, 64.888), (36.155, 65.02), (36.154, 65.647), (36.122, 65.752),
                    (36.05, 65.838), (36.05, 66.4), (36.152, 66.4), (36.158, 66.228), (36.2, 66.127), (36.301, 66.036), (36.42, 66.003),
                    (36.42, 64.15), (36.65, 64.15), (36.65, 63.4), (38.1, 63.4), (38.1, 57.0), (34.7, 57.0)])
    if nm == 'PWR BB_VOUT':
        o = z.Outline(); old = [(o.CVertex(k).x / 1e6, o.CVertex(k).y / 1e6) for k in range(o.TotalVertices())]
        new = []
        for x, y in old:
            if abs(x - 48.7) < 1e-3 and abs(y - 71.6) < 1e-3:
                new += [(48.7, 71.6), (44.0, 71.6), (44.0, 70.0), (40.0, 70.0), (40.0, 71.6)]
            else: new.append((x, y))
        setpoly(z, new)
# AGND island under the control parts, joined to GND only through NT3
src = [z for z in ZS if z.GetZoneName() == 'PWR GND'][0]
za = pcbnew.ZONE(b); za.SetLayer(pcbnew.F_Cu); za.SetNet(net('/BB_AGND')); za.SetZoneName('AGND')
za.SetAssignedPriority(10); za.SetLocalClearance(MM(0.2)); za.SetMinThickness(MM(0.2))
za.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
setpoly(za, [(39.65, 64.0), (47.4, 64.0), (47.4, 62.55), (43.3, 62.55), (43.3, 59.75), (40.9, 59.75), (40.9, 62.55), (39.65, 62.55)])
b.Add(za)

filler = pcbnew.ZONE_FILLER(b); filler.Fill(b.Zones())
b.Save(sys.argv[2]); print('ok')
