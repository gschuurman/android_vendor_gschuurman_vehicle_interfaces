"""kline_sch.py file.kicad_sch : rev 0.6 schematic edit. J10 (1x8 male header under the USB module) becomes a 2x4
female socket for a stacked K-line module, and F6 (PTC) feeds it protected battery voltage (VBAT_KLINE) from VBAT_P.
Done as a text edit because gen5.py needs the KiCad 7 symbol library (see ../README.md)."""
import re, sys, uuid
fn = sys.argv[1]
s = open(fn, encoding='utf-8').read()
def uid(tag): return str(uuid.uuid5(uuid.NAMESPACE_URL, f'carradio-rev06-{tag}'))
def block_at(start):
    d = 0
    for i in range(start, len(s)):
        if s[i] == '(': d += 1
        elif s[i] == ')':
            d -= 1
            if d == 0: return start, i + 1
def inst(ref):
    for m in re.finditer(r'\n  \(symbol\n    \(lib_id', s):
        a, b = block_at(m.start() + 3)
        if re.search(r'\(property\s+"Reference"\s+"%s"' % ref, s[a:b]): return a, b
def label(name, x, y, ang):
    j = 'right bottom' if ang == 180 else 'left bottom'
    return (f'  (label\n    "{name}"\n    (at {x:g} {y:g} {ang})\n    (fields_autoplaced)\n    (effects\n      (font\n'
            f'        (size 1.27 1.27))\n      (justify {j}))\n    (uuid "{uid(f"label-{name}-{x}-{y}")}"))\n')
JX, JY = 185, 205
# old J10 (Conn_01x08 at 185,205): labels / no-connect on its pin ends at x = 179.92
olds = [round(JY - 7.62 + 2.54 * k, 2) for k in range(8)]
# pins 6/7 are GND power symbols: move them onto the new socket's GND pins (2 and 6)
gnd_new = iter([(JX + 7.62, JY - 2.54), (JX + 7.62, JY + 2.54)])
for y in (olds[5], olds[6]):
    m = re.search(r'\n  \(symbol\n    \(lib_id "power:GND"\)\n    \(at 179\.92 %s 270\)' % re.escape(f'{y:g}'), s)
    a, b = block_at(m.start() + 3); nx, ny = next(gnd_new)
    blk = s[a:b].replace(f'(at 179.92 {y:g} 270)', f'(at {nx:g} {ny:g} 90)')
    blk = re.sub(r'\(at 179\.92 ([\d.]+) 0\)', lambda q: f'(at {nx + 3.5:g} {ny:g} 0)' if 'Value' in blk[:q.start()][-80:] else f'(at {nx:g} {ny:g} 0)', blk)
    s = s[:a] + blk + s[b:]
for y in [o for k, o in enumerate(olds) if k not in (5, 6)]:
    s, n1 = re.subn(r'  \(label\s+"[^"]+"\s+\(at 179\.92 %s \d+\).*?\(uuid "[^"]+"\)\)\n' % re.escape(f'{y:g}'), '', s, flags=re.S)
    s, n2 = re.subn(r'  \(no_connect\s+\(at 179\.92 %s\)\s+\(uuid "[^"]+"\)\)\n' % re.escape(f'{y:g}'), '', s)
    assert n1 + n2 == 1, (y, n1, n2)
a, b = inst('J10'); assert 'Conn_01x08' in s[a:b]
ta, tb = inst('J27'); j = s[ta:tb]
j = j.replace('Conn_02x08_Odd_Even', 'Conn_02x04_Odd_Even').replace('(at 300 280 0)', f'(at {JX} {JY} 0)')
j = j.replace('(at 300 264.54 0)', f'(at {JX + 1.27} {JY - 7.62} 0)').replace('(at 300 294.16 0)', f'(at {JX + 1.27} {JY + 10.16} 0)')
j = re.sub(r'\(uuid "[^"]+"\)', lambda m, c=[0]: (c.__setitem__(0, c[0] + 1), f'(uuid "{uid(f"J10-{c[0]}")}")')[1], j, count=1)
j = j.replace('"J27"', '"J10"').replace('"GNSS module socket"', '"K-line module socket"')
j = j.replace('PinSocket_2x08_P2.54mm_Vertical', 'PinSocket_2x04_P2.54mm_Vertical')
j = j.replace('"2x8 2.54mm female socket, 8.5mm body (same family as J23/J25)"', '"2x4 2.54mm female socket, 8.5mm body (same family as J23/J25/J27)"')
pins = ''.join(f'    (pin\n      "{n}"\n      (uuid "{uid(f"J10-pin{n}")}"))\n' for n in range(1, 9))
j = re.sub(r'(    \(pin\n.*?\n)(    \(instances)', lambda m: pins + m.group(2), j, count=1, flags=re.S)
NETS = {1: '+3V3_MCU', 3: 'EXP_GP32', 4: 'EXP_GP33', 5: 'EXP_GP28', 7: 'VBAT_KLINE', 8: '+5V_AON'}   # 2, 6: GND power symbols
labels = ''
for n, net in NETS.items():
    row = (n - 1) // 2; y = round(JY - 2.54 + 2.54 * row, 2)
    labels += label(net, JX - 5.08, y, 180) if n % 2 else label(net, JX + 7.62, y, 0)
# F6: PTC from VBAT_P to the socket, a copy of F1
FX, FY = 215, 205
fa, fb = inst('F1'); f = s[fa:fb]
f = f.replace('(at 55 42 0)', f'(at {FX} {FY} 0)').replace('(at 57.2 40.8 0)', f'(at {FX + 2.2} {FY - 1.2} 0)').replace('(at 57.2 43.2 0)', f'(at {FX + 2.2} {FY + 1.2} 0)')
f = re.sub(r'\(uuid "[^"]+"\)', lambda m, c=[0]: (c.__setitem__(0, c[0] + 1), f'(uuid "{uid(f"F6-{c[0]}")}")')[1], f)
f = f.replace('"F1"', '"F6"').replace('"PTC 0.5A hold 30V"', f'"{sys.argv[2] if len(sys.argv) > 2 else "PTC 0.2A hold 30V"}"')
if len(sys.argv) > 4: f = f.replace('"C883126"', f'"{sys.argv[3]}"').replace('"BHFUSE BSMD1206-050-30V"', f'"{sys.argv[4]}"')
s = s[:a] + j + '\n  ' + f + s[b:]
labels += label('VBAT_P', FX, FY - 3.81, 0) + label('VBAT_KLINE', FX, FY + 3.81, 0)
i = s.index('\n  (label\n') + 1
s = s[:i] + labels + s[i:]
open(fn, 'w', encoding='utf-8').write(s); print('ok')
