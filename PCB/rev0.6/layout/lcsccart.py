"""lcsccart.py out.csv bom.csv [bom.csv ...] [REF=LCSC ...] [+LCSC=QTY:description ...] [OLD->NEW ...] : one LCSC order list for a set of boards (hand assembly).
Sums fitted parts per LCSC number over all BOMs (solder jumpers skipped); 0402/0603/0805 resistors and capacitors get
3 spares. OLD->NEW swaps an LCSC number everywhere (out of stock, BOM left as it is). +LCSC=QTY:description adds a part the BOM only names in a note (fuse insert, jumper cap). Parts without an
LCSC number are listed at the end with quantity 0 for manual sourcing.
Also writes <out>_upload.csv: only 'LCSC Part Number,Quantity', ASCII, no zero rows, for LCSC's BOM tool (it matches
by value/footprint text when other columns are present, and reads plain UTF-8 as GBK). The full list is UTF-8 with BOM.
With openpyxl available (withlib.py), also <out>_upload.xlsx: Quantity, LCSC Part Number, Description (ASCII), in the
column order of LCSC's BOM template."""
import csv, sys, collections
out = sys.argv[1]; boms = [a for a in sys.argv[2:] if '=' not in a and not a.startswith('+') and '->' not in a]
SWAP = dict(a.split('->', 1) for a in sys.argv[2:] if '->' in a); OVR = dict(a.split('=', 1) for a in sys.argv[2:] if '=' in a and not a.startswith('+'))
EXTRA = [a[1:].split('=', 1) for a in sys.argv[2:] if a.startswith('+')]
qty = collections.Counter(); info = {}; refs = collections.defaultdict(list); nolcsc = []
for fn in boms:
    board = fn.replace(chr(92), '/').split('/')[-1].replace('_bom.csv', '')
    for r in csv.DictReader(open(fn, encoding='utf-8')):
        if r.get('Fit', 'yes').strip().lower() != 'yes' or r['Footprint (KiCad name)'].startswith('Jumper:SolderJumper'): continue
        l = r['LCSC'].strip() or OVR.get(r['Designator'], ''); l = SWAP.get(l, l)
        if not l: nolcsc.append((board, r['Designator'], r['Value'], r['Description / MPN'])); continue
        qty[l] += 1; info[l] = (r['Value'], r['Description / MPN'], r['Footprint (KiCad name)'].split(':')[-1]); refs[l].append(f"{board}:{r['Designator']}")
rows = []
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(['LCSC Part Number', 'Quantity', 'Needed', 'Value', 'Description / MPN', 'Footprint', 'Used on'])
    for l in sorted(qty, key=lambda k: info[k][2]):
        v, d, fp = info[l]; spare = 3 if fp.split('_')[0] in ('R', 'C') and any(s in fp for s in ('0402', '0603', '0805')) else 0
        w.writerow([l, qty[l] + spare, qty[l], v, d, fp, ' '.join(refs[l])]); rows.append((l, qty[l] + spare, f'{v} {d}'))
    for l, qd in EXTRA:
        q, d = qd.split(':', 1); w.writerow([l, q, q, '', d, '', 'extra (named in a BOM note)']); rows.append((l, int(q), d))
    for board, ref, v, d in nolcsc: w.writerow(['', 0, 1, v, d, '', f'{board}:{ref} (no LCSC number: source separately)'])
with open(out.replace('.csv', '_upload.csv'), 'w', newline='', encoding='ascii') as f:
    w = csv.writer(f); w.writerow(['Quantity', 'LCSC Part Number'])
    for l, q, _ in rows: w.writerow([q, l])
def ascii(t): return t.replace('Ω', 'ohm').replace('µ', 'u').encode('ascii', 'replace').decode().replace('?', '')
try:
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'BOM'
    ws.append(['Quantity', 'LCSC Part Number', 'Description'])
    for l, q, d in rows: ws.append([q, l, ascii(d)[:120]])
    ws.column_dimensions['B'].width = 18; ws.column_dimensions['C'].width = 80
    wb.save(out.replace('.csv', '_upload.xlsx'))
except ImportError:
    pass
print('lines', len(qty), 'parts', sum(qty.values()), 'without LCSC', [f'{b}:{r}' for b, r, v, d in nolcsc])
