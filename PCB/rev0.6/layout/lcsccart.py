"""lcsccart.py out.csv bom.csv [bom.csv ...] [REF=LCSC ...] [+LCSC=QTY:description ...] : one LCSC order list for a set of boards (hand assembly).
Sums fitted parts per LCSC number over all BOMs (solder jumpers skipped); 0402/0603/0805 resistors and capacitors get
3 spares. +LCSC=QTY:description adds a part the BOM only names in a note (fuse insert, jumper cap). Parts without an
LCSC number are listed at the end with quantity 0 for manual sourcing."""
import csv, sys, collections
out = sys.argv[1]; boms = [a for a in sys.argv[2:] if '=' not in a and not a.startswith('+')]; OVR = dict(a.split('=', 1) for a in sys.argv[2:] if '=' in a and not a.startswith('+'))
EXTRA = [a[1:].split('=', 1) for a in sys.argv[2:] if a.startswith('+')]
qty = collections.Counter(); info = {}; refs = collections.defaultdict(list); nolcsc = []
for fn in boms:
    board = fn.replace(chr(92), '/').split('/')[-1].replace('_bom.csv', '')
    for r in csv.DictReader(open(fn, encoding='utf-8')):
        if r.get('Fit', 'yes').strip().lower() != 'yes' or r['Footprint (KiCad name)'].startswith('Jumper:SolderJumper'): continue
        l = r['LCSC'].strip() or OVR.get(r['Designator'], '')
        if not l: nolcsc.append((board, r['Designator'], r['Value'], r['Description / MPN'])); continue
        qty[l] += 1; info[l] = (r['Value'], r['Description / MPN'], r['Footprint (KiCad name)'].split(':')[-1]); refs[l].append(f"{board}:{r['Designator']}")
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['LCSC Part Number', 'Quantity', 'Needed', 'Value', 'Description / MPN', 'Footprint', 'Used on'])
    for l in sorted(qty, key=lambda k: info[k][2]):
        v, d, fp = info[l]; spare = 3 if fp.split('_')[0] in ('R', 'C') and any(s in fp for s in ('0402', '0603', '0805')) else 0
        w.writerow([l, qty[l] + spare, qty[l], v, d, fp, ' '.join(refs[l])])
    for l, qd in EXTRA:
        q, d = qd.split(':', 1); w.writerow([l, q, q, '', d, '', 'extra (named in a BOM note)'])
    for board, ref, v, d in nolcsc: w.writerow(['', 0, 1, v, d, '', f'{board}:{ref} (no LCSC number: source separately)'])
print('lines', len(qty), 'parts', sum(qty.values()), 'without LCSC', [f'{b}:{r}' for b, r, v, d in nolcsc])
