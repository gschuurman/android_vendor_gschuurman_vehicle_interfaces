"""jlcfab.py board.kicad_pcb bom.csv outdir name [REF=LCSC ...] : JLCPCB order package for one board (KiCad 10, kicad-cli).
REF=LCSC fills in a missing LCSC number. Solder jumpers (PCB copper, no part) are left out of the BOM and CPL, and so are
2.54 mm pin headers, pin sockets and IDC box headers (bought through the LCSC cart, soldered by hand).

Writes into outdir:
  <name>_gerbers.zip   Gerbers (Protel extensions, no X2/netlist attributes,
                       silkscreen clipped at mask openings) plus Excellon drill files (mm, absolute origin, PTH and NPTH separate)
  <name>_bom.csv       JLC assembly BOM: Comment, Designator, Footprint, JLCPCB Part # (fitted parts only)
  <name>_cpl.csv       JLC pick-and-place: Designator, Mid X, Mid Y, Layer, Rotation (DNP excluded)
Settings follow JLCPCB's KiCad export guide; check the rotations in JLC's assembly preview before ordering."""
import csv, os, shutil, subprocess, sys, tempfile, zipfile
KCLI = os.environ.get('KCLI', r'C:\Program Files\KiCad\10.0\bin\kicad-cli.exe')
pcb, bomsrc, out, name = sys.argv[1:5]
OVR = dict(a.split('=', 1) for a in sys.argv[5:])
os.makedirs(out, exist_ok=True)
tmp = tempfile.mkdtemp()
txt = open(pcb, encoding='utf-8').read()
inner = [l for l in ('In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu') if f'"{l}"' in txt.split('(setup')[0]]
layers = ['F.Cu'] + inner + ['B.Cu', 'F.Paste', 'B.Paste', 'F.Silkscreen', 'B.Silkscreen', 'F.Mask', 'B.Mask', 'Edge.Cuts']
def run(*a): subprocess.run([KCLI, *a], check=True, stdout=subprocess.DEVNULL)
run('pcb', 'export', 'gerbers', '--layers', ','.join(layers), '--no-x2', '--no-netlist', '--subtract-soldermask', '-o', tmp + os.sep, pcb)
run('pcb', 'export', 'drill', '--format', 'excellon', '--excellon-units', 'mm', '--drill-origin', 'absolute',
    '--excellon-zeros-format', 'decimal', '--excellon-oval-format', 'route', '--excellon-separate-th', '-o', tmp + os.sep, pcb)
files = sorted(f for f in os.listdir(tmp) if not f.endswith('.json'))
with zipfile.ZipFile(os.path.join(out, f'{name}_gerbers.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
    for f in files: z.write(os.path.join(tmp, f), f)
# BOM: group fitted parts by value + footprint + LCSC
groups = {}
for r in csv.DictReader(open(bomsrc, encoding='utf-8')):
    if r.get('Fit', 'yes').strip().lower() != 'yes': continue
    if r['Footprint (KiCad name)'].startswith(('Jumper:SolderJumper', 'Connector_PinHeader', 'Connector_PinSocket', 'Connector_IDC')): continue
    fp = r['Footprint (KiCad name)'].split(':')[-1]
    key = (r['Value'], fp, r['LCSC'].strip() or OVR.get(r['Designator'], ''))
    groups.setdefault(key, []).append(r['Designator'])
def refkey(d): return (''.join(c for c in d if not c.isdigit()), int(''.join(c for c in d if c.isdigit()) or 0))
with open(os.path.join(out, f'{name}_bom.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['Comment', 'Designator', 'Footprint', 'JLCPCB Part #'])
    for (val, fp, lcsc), refs in sorted(groups.items(), key=lambda kv: refkey(sorted(kv[1], key=refkey)[0])):
        w.writerow([val, ','.join(sorted(refs, key=refkey)), fp, lcsc])
fitted = {d for refs in groups.values() for d in refs}
# CPL from KiCad's position file
pos = os.path.join(tmp, 'pos.csv')
run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '--exclude-dnp', '-o', pos, pcb)
with open(os.path.join(out, f'{name}_cpl.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for r in csv.DictReader(open(pos, encoding='utf-8')):
        if r['Ref'] not in fitted: continue
        w.writerow([r['Ref'], f"{float(r['PosX']):.4f}mm", f"{float(r['PosY']):.4f}mm", 'Top' if r['Side'].lower().startswith('top') else 'Bottom', f"{float(r['Rot']):.1f}"])
missing = sorted((d for (v, fp, l), refs in groups.items() if not l for d in refs), key=refkey)
shutil.rmtree(tmp)
print(name, 'gerber/drill files', len(files), 'bom lines', len(groups), 'parts without LCSC:', ','.join(missing) or 'none')
