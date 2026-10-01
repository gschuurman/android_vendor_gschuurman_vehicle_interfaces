"""Design rules, net classes, planes; export a Specctra DSN for Freerouting.
usage: prep_route.py in.kicad_pcb out_base   (writes out_base.kicad_pcb/.kicad_pro/.dsn)"""
import pcbnew, sys, json, shutil, re
src, base = sys.argv[1], sys.argv[2]
MM = pcbnew.FromMM
def V(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))

CLASSES = {
    # name: (track, clearance, via_d, via_drill, dp_w, dp_gap)
    'Default':     (0.2, 0.13, 0.45, 0.2, 0.2, 0.15),
    'HDMI':        (0.2, 0.1, 0.45, 0.2, 0.2, 0.15),
    'USB':         (0.25, 0.15, 0.45, 0.2, 0.25, 0.15),
    # routed thin for connectivity; the high-current paths get copper pours afterwards
    'Power':       (0.3, 0.13, 0.45, 0.2, 0.3, 0.15),
    'HighCurrent': (0.6, 0.15, 0.6, 0.3, 0.6, 0.15),
}
PATTERNS = [
    ('HDMI', '/HDMI_*'),
    ('USB', '*_DP'), ('USB', '*_DM'), ('USB', '*_DN'), ('USB', '*USBDP*'), ('USB', '*USBDM*'),
    ('HighCurrent', '/VSYS_IN'), ('HighCurrent', '/+5V_SYS'),
    ('Power', '/BATT_RAW'), ('Power', '/BATT_F2'), ('Power', '/BB_SW*'), ('Power', '/BB_VOUT'),
    ('Power', '/+5V_USB'), ('Power', '/EXT?_VBUS'), ('Power', '/SDR_VBUS'), ('Power', '/USBP_*'), ('Power', '/+5V_AON'),
    ('Power', '/+3V3_*'), ('Power', '/+1V1_MCU'), ('Power', '/BUCK_SW'), ('Power', '/VIM3_5V'), ('Power', '/BATT_F'),
    ('Power', '/HUB*_3V3'), ('Power', '/GNSS_VCCRF'),
]
tmpl = json.load(open('/usr/share/kicad/template/KiCad_MR_diagrams_large_parts/mr_diagrams_large_parts.kicad_pro'))
cls = []
for i, (n, (tw, cl, vd, vh, dw, dg)) in enumerate(CLASSES.items()):
    c = dict(tmpl['net_settings']['classes'][0])
    c.update(name=n, track_width=tw, clearance=cl, via_diameter=vd, via_drill=vh, diff_pair_width=dw, diff_pair_gap=dg,
             priority=2147483647 if n == 'Default' else i)
    cls.append(c)
tmpl['net_settings']['classes'] = cls
tmpl['net_settings']['netclass_patterns'] = [{'netclass': c, 'pattern': p} for c, p in PATTERNS]
r = tmpl['board']['design_settings']['rules']
r.update(min_clearance=0.1, min_track_width=0.15, min_via_diameter=0.45, min_through_hole_diameter=0.2,
         min_via_annular_width=0.1, min_copper_edge_clearance=0.3, min_hole_clearance=0.2, min_hole_to_hole=0.25)
tmpl['meta']['filename'] = base.split('/')[-1] + '.kicad_pro'
json.dump(tmpl, open(base + '.kicad_pro', 'w'), indent=2)
shutil.copy(src, base + '.kicad_pcb')
b = pcbnew.LoadBoard(base + '.kicad_pcb')

# JLCPCB JLC04161H-7628 stack (1.6 mm): outer 1 oz, inner 0.5 oz
W, H = [float(x) for x in re.findall(r'W, H = ([\d.]+), ([\d.]+)', open('/w/lay/floorplan.py').read())[0]]
def zone(layer, net, pts, prio=0, name=''):
    z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(b.FindNet(net)) if net else None
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(MM(x), MM(y))
    z.SetAssignedPriority(prio); z.SetLocalClearance(MM(0.25)); z.SetMinThickness(MM(0.2))
    z.SetThermalReliefGap(MM(0.3)); z.SetThermalReliefSpokeWidth(MM(0.4))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    if name: z.SetZoneName(name)
    b.Add(z); return z
full = [(0.3, 0.3), (W - 0.3, 0.3), (W - 0.3, H - 0.3), (0.3, H - 0.3)]
zone(pcbnew.In1_Cu, 'GND', full, 0, 'GND plane')
# keep In2 free under the HDMI runs so it can be solid GND there
ka = pcbnew.ZONE(b); ka.SetIsRuleArea(True); ka.SetLayer(pcbnew.In2_Cu)
ka.SetDoNotAllowTracks(True); ka.SetDoNotAllowVias(False); ka.SetDoNotAllowPads(False); ka.SetDoNotAllowZoneFills(False)
ol = ka.Outline(); ol.NewOutline()
for x, y in [(62.5, 9.0), (100.5, 9.0), (100.5, 22.0), (62.5, 22.0)]: ol.Append(MM(x), MM(y))
ka.SetZoneName('HDMI reference'); b.Add(ka)
b.Save(base + '.kicad_pcb')

# DSN without the TPS55288 power stage nets (U12 footprint not in yet): strip those pads' nets for export only
skip = re.compile(r'^$^')
for f in b.GetFootprints():
    for p in f.Pads():
        if skip.match(p.GetNetname()): p.SetNetCode(0)
for t in list(b.GetTracks()):
    pass
ok = pcbnew.ExportSpecctraDSN(b, base + '.dsn')
print('dsn', ok)
