"""am_prep.py in base : rules + DSN for the GNSS module."""
import pcbnew, sys, json, shutil
src, base = sys.argv[1:3]
tmpl = json.load(open('/usr/share/kicad/template/KiCad_MR_diagrams_large_parts/mr_diagrams_large_parts.kicad_pro'))
c0 = tmpl['net_settings']['classes'][0]
def cls(n, tw, cl, vd, vh, pr):
    c = dict(c0); c.update(name=n, track_width=tw, clearance=cl, via_diameter=vd, via_drill=vh, diff_pair_width=tw, diff_pair_gap=0.2, priority=pr); return c
tmpl['net_settings']['classes'] = [cls('Default', 0.2, 0.15, 0.6, 0.3, 2147483647), cls('Power', 0.3, 0.15, 0.6, 0.3, 0)]
tmpl['net_settings']['netclass_patterns'] = [{'netclass': 'Power', 'pattern': p} for p in ('/+3V3_GNSS', '/+3V3_MCU', 'GND')]
r = tmpl['board']['design_settings']['rules']
r.update(min_clearance=0.15, min_track_width=0.2, min_via_diameter=0.6, min_through_hole_diameter=0.3, min_via_annular_width=0.13,
         min_copper_edge_clearance=0.4, min_hole_clearance=0.25, min_hole_to_hole=0.25)
tmpl['meta']['filename'] = base + '.kicad_pro'
json.dump(tmpl, open(base + '.kicad_pro', 'w'), indent=2)
shutil.copy(src, base + '.kicad_pcb')
b = pcbnew.LoadBoard(base + '.kicad_pcb')
print('dsn', pcbnew.ExportSpecctraDSN(b, base + '.dsn'))
