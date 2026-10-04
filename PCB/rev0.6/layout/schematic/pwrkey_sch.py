"""pwrkey_sch.py file.kicad_sch : rev 0.6 schematic edit. The VIM3 POWER key is pressed by a PhotoMOS (U22, Panasonic
AQY210S, SOP-4) whose output shorts the two J5 pins together, isolated, instead of Q1 (AO3400A) pulling J5 pin 1 to GND.
GPIO15 (MCU_PWR_KEY) drives the PhotoMOS LED through R12 (now 390 ohm, ~5 mA); R19 (gate pull-down) goes, an undriven LED
is off. J5 pin 2 leaves GND: J5 = VIM3_PWR_KEY_A / VIM3_PWR_KEY_B, the two pads of the VIM3 key.
Done as a text edit because gen5.py needs the KiCad 7 symbol library (see ../README.md)."""
import re, sys, uuid
fn = sys.argv[1]
s = open(fn, encoding='utf-8').read()
TLP = 'C:/Program Files/KiCad/10.0/share/kicad/symbols/Relay_SolidState.kicad_sym'
def uid(tag): return str(uuid.uuid5(uuid.NAMESPACE_URL, f'carradio-rev06-{tag}'))
def block_at(t, start):
    d = 0
    for i in range(start, len(t)):
        if t[i] == '(': d += 1
        elif t[i] == ')':
            d -= 1
            if d == 0: return start, i + 1
def inst(ref):
    for m in re.finditer(r'\n  \(symbol\n    \(lib_id', s):
        a, b = block_at(s, m.start() + 3)
        if re.search(r'\(property\s+"Reference"\s+"%s"' % ref, s[a:b]): return a, b
def power_at(x, y):
    m = re.search(r'\n  \(symbol\n    \(lib_id "power:GND"\)\n    \(at %s %s \d+\)' % (re.escape(f'{x:g}'), re.escape(f'{y:g}')), s)
    return block_at(s, m.start() + 3)
def drop(a, b):
    global s
    while s[a - 1] in ' ': a -= 1
    s = s[:a] + s[b:].lstrip('\n')
def drop_label(name, x, y):
    global s
    s, n = re.subn(r'  \(label\s+"%s"\s+\(at %s %s \d+\).*?\(uuid "[^"]+"\)\)\n' % (name, re.escape(f'{x:g}'), re.escape(f'{y:g}')), '', s, flags=re.S)
    assert n == 1, (name, x, y, n)
def label(name, x, y, ang):
    j = 'right bottom' if ang == 180 else 'left bottom'
    return (f'  (label\n    "{name}"\n    (at {x:g} {y:g} {ang})\n    (fields_autoplaced)\n    (effects\n      (font\n'
            f'        (size 1.27 1.27))\n      (justify {j}))\n    (uuid "{uid(f"label-{name}-{x}-{y}")}"))\n')
def prop(name, val, x, y, hide=True, size=1.27):
    return (f'    (property\n      "{name}"\n      "{val}"\n      (at {x:g} {y:g} 0)\n      (effects\n        (font\n'
            f'          (size {size} {size})){chr(10) + "        hide" if hide else ""}))\n')
assert 'AQY210S' not in s, 'already applied'
# 1. library symbol: the KiCad library's TLP3123 body (AQY2xxS share it), renamed, without the KiCad 8+ only tokens
lib = open(TLP, encoding='utf-8').read()
a, b = block_at(lib, lib.index('(symbol "TLP3123"'))
sym = lib[a:b].replace('(symbol "TLP3123"', '(symbol "Relay_SolidState:AQY210S"', 1)
sym = sym.replace('"TLP3123_', '"AQY210S_').replace('"Value" "TLP3123"', '"Value" "AQY210S"')
sym = sym.replace('Package_SO:SO-4_4.4x3.9mm_P2.54mm', 'Package_SO:SO-4_4.4x4.3mm_P2.54mm')
sym = re.sub(r'\s*\((exclude_from_sim|in_pos_files|duplicate_pin_numbers_are_jumpers|show_name|do_not_autoplace|embedded_fonts) \w+\)', '', sym)
i = s.index('(lib_symbols') + len('(lib_symbols')
s = s[:i] + '\n    ' + sym + s[i:]
# 2. Q1 (AO3400A, at 450 185) -> U22 (AQY210S, same spot). Pins: 1 LED anode (442.38, 182.46), 2 LED cathode
#    (442.38, 187.54), 3 / 4 PhotoMOS output (457.62, 187.54 / 182.46). Pin 3 -> J5 pin 1 (A), pin 4 -> J5 pin 2 (B): the
#    layout's pad order (the output is a bidirectional switch, so either way round works)
a, b = inst('Q1'); q = s[a:b]
path = re.search(r'\(path\s+"([^"]+)"', q).group(1)
u = (f'(symbol\n    (lib_id "Relay_SolidState:AQY210S")\n    (at 450 185 0)\n    (unit 1)\n    (in_bom yes)\n    (on_board yes)\n'
     f'    (dnp no)\n    (uuid "{uid("U22")}")\n'
     + prop('Reference', 'U22', 450, 178.65, hide=False) + prop('Value', 'AQY210S', 450, 191.35, hide=False, size=1)
     + prop('Footprint', 'Package_SO:SO-4_4.4x4.3mm_P2.54mm', 450, 185) + prop('Datasheet', '', 450, 185)
     + prop('LCSC', '', 450, 185) + prop('MPN', 'Panasonic AQY210S PhotoMOS 350V 120mA 1 Form A, SOP-4 (own stock)', 450, 185)
     + ''.join(f'    (pin\n      "{n}"\n      (uuid "{uid(f"U22-pin{n}")}"))\n' for n in range(1, 5))
     + f'    (instances\n      (project\n        "carradio_peripheral_rev06"\n        (path\n          "{path}"\n'
       f'          (reference "U22")\n          (unit 1)))))')
s = s[:a] + u + s[b:]
drop_label('PWR_KEY_G', 444.92, 185); drop_label('VIM3_PWR_KEY', 452.54, 179.92)
# Q1's source GND symbol moves to the LED cathode (pin 2), pointing left like J5's
a, b = power_at(452.54, 190.08); g = s[a:b]
g = g.replace('(at 452.54 190.08 0)', '(at 442.38 187.54 270)', 1)
g = re.sub(r'\(at 452\.54 ([\d.]+) 0\)', lambda m: '(at 442.38 187.54 0)', g)
s = s[:a] + g + s[b:]
# 3. R12: LED resistor. 3.3 V - ~1.2 V LED over 390 ohm = ~5 mA (AQY210S: 3 mA max to turn on)
a, b = inst('R12'); r = s[a:b]
r = r.replace('"100Ω"', '"390Ω"').replace('"C22775"', '"C23151"').replace('"0603 100 1%"', '"UNI-ROYAL 0603WAF3900T5E 390 1%"')
s = s[:a] + r + s[b:]
drop_label('PWR_KEY_G', 430, 188.81)
# 4. R19 (gate pull-down) and its GND go
drop_label('PWR_KEY_G', 438, 196.19)
a, b = power_at(438, 203.81); drop(a, b)
a, b = inst('R19'); drop(a, b)
# 5. J5: pin 1 / pin 2 = the two VIM3 key pads; pin 2's GND symbol goes
drop_label('VIM3_PWR_KEY', 469.92, 185)
a, b = power_at(469.92, 187.54); drop(a, b)
labels = (label('PWR_KEY_LED', 430, 188.81, 270) + label('PWR_KEY_LED', 442.38, 182.46, 180)
          + label('VIM3_PWR_KEY_B', 457.62, 182.46, 0) + label('VIM3_PWR_KEY_A', 457.62, 187.54, 0)
          + label('VIM3_PWR_KEY_A', 469.92, 185, 180) + label('VIM3_PWR_KEY_B', 469.92, 187.54, 180))
i = s.index('\n  (label\n') + 1
s = s[:i] + labels + s[i:]
open(fn, 'w', encoding='utf-8').write(s); print('ok')
