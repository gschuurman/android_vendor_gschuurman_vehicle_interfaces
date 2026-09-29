#!/usr/bin/env python3
"""Generate the car-radio peripheral board schematic (KiCad 7 .kicad_sch) + BOM.

Every connection is made with net labels placed on pin endpoints, so the netlist
is unambiguous and survives import into EasyEDA Pro.
"""
import csv, uuid, copy, sys
from sexp import Sym, parse, dump, find_sym, pins_of

S = Sym
PROJECT = "carradio_peripheral_rev02"
ROOT = str(uuid.uuid5(uuid.NAMESPACE_URL, "carradio-peripheral-rev02-root"))
_n = [0]
def uid():
    _n[0] += 1
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"carradio-{_n[0]}"))

def font(size=1.27):
    return [S('effects'), [S('font'), [S('size'), size, size]]]

# ---------------------------------------------------------------- symbols
lib_symbols = {}    # lib_id -> definition (flattened)
pin_table = {}      # lib_id -> [(num,name,x,y,angle,type)]

def add_lib(libname, name):
    lib_id = f"{libname}:{name}"
    if lib_id in lib_symbols:
        return lib_id
    d = copy.deepcopy(find_sym(libname, name))
    ext = [e for e in d if isinstance(e, list) and e and e[0] == 'extends']
    if ext:
        parent = copy.deepcopy(find_sym(libname, ext[0][1]))
        pname = ext[0][1]
        body = []
        for e in parent[2:]:
            if isinstance(e, list) and e and e[0] == 'symbol':
                e[1] = e[1].replace(pname + "_", name + "_", 1)
                body.append(e)
            elif isinstance(e, list) and e and e[0] in ('pin_names', 'pin_numbers', 'in_bom', 'on_board', 'exclude_from_sim'):
                body.append(e)
        props = [e for e in d[2:] if isinstance(e, list) and e and e[0] == 'property']
        d = ['symbol', name] + body[:0] + [b for b in body if b[0] != 'symbol'] + props + [b for b in body if b[0] == 'symbol']
        d[0] = S('symbol')
    d[1] = lib_id
    lib_symbols[lib_id] = d
    pin_table[lib_id] = pins_of(d)
    return lib_id

def box_symbol(name, left, right, width=20.32, ref="J", value=None, fp=""):
    """Custom rectangular symbol. left/right: list of (number, name) or None (gap)."""
    lib_id = f"carradio:{name}"
    n = max(len(left), len(right))
    h = (n + 1) * 2.54
    top = h / 2
    pins = []
    def mk(side, lst):
        for i, p in enumerate(lst):
            if p is None:
                continue
            num, nm = p
            y = top - 2.54 * (i + 1)
            x = -width / 2 - 2.54 if side == 'L' else width / 2 + 2.54
            ang = 0 if side == 'L' else 180
            pins.append([S('pin'), S('passive'), S('line'), [S('at'), round(x, 2), round(y, 2), ang],
                         [S('length'), 2.54], [S('name'), nm, font()], [S('number'), str(num), font()]])
    mk('L', left); mk('R', right)
    d = [S('symbol'), lib_id, [S('pin_names'), [S('offset'), 1.016]], [S('in_bom'), S('yes')], [S('on_board'), S('yes')],
         [S('property'), "Reference", ref, [S('at'), 0, top + 1.27, 0], font()],
         [S('property'), "Value", value or name, [S('at'), 0, -top - 1.27, 0], font()],
         [S('property'), "Footprint", fp, [S('at'), 0, 0, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
         [S('property'), "Datasheet", "", [S('at'), 0, 0, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
         [S('symbol'), f"{name}_0_1", [S('rectangle'), [S('start'), round(-width / 2, 2), round(top, 2)], [S('end'), round(width / 2, 2), round(-top, 2)],
                                        [S('stroke'), [S('width'), 0.254], [S('type'), S('default')]], [S('fill'), [S('type'), S('background')]]]],
         [S('symbol'), f"{name}_1_1"] + pins]
    lib_symbols[lib_id] = d
    pin_table[lib_id] = pins_of(d)
    return lib_id

POS = {}
TEXTPOS = {}
# ---------------------------------------------------------------- items
items = []
bom = []
nets = {}   # net -> list of (ref,pin)

def label(net, x, y, ang):
    just = [S('justify'), S('left'), S('bottom')] if ang in (0, 90) else [S('justify'), S('right'), S('bottom')]
    items.append([S('label'), net, [S('at'), round(x, 2), round(y, 2), ang], [S('fields_autoplaced')],
                  [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], just], [S('uuid'), uid()]])

def text(t, x, y, size=1.27):
    for k, v in TEXTPOS.items():
        if t.startswith(k):
            if v is None: return
            x, y = v
    items.append([S('text'), t, [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), size, size]], [S('justify'), S('left'), S('bottom')]], [S('uuid'), uid()]])

def noconn(x, y):
    items.append([S('no_connect'), [S('at'), round(x, 2), round(y, 2)], [S('uuid'), uid()]])

pwr_n = [0]
def power(lib_name, x, y, outward):
    """Place power symbol (GND/PWR_FLAG) whose pin is at (x,y)."""
    lib_id = add_lib('power', lib_name)
    pwr_n[0] += 1
    ref = f"#PWR{pwr_n[0]:03d}" if lib_name != 'PWR_FLAG' else f"#FLG{pwr_n[0]:03d}"
    base = 270 if lib_name == 'GND' else 90   # direction the symbol body sits relative to its pin
    rot = (outward - base) % 360
    items.append([S('symbol'), [S('lib_id'), lib_id], [S('at'), round(x, 2), round(y, 2), rot], [S('unit'), 1],
                  [S('in_bom'), S('no')], [S('on_board'), S('yes')], [S('dnp'), S('no')], [S('uuid'), uid()],
                  [S('property'), "Reference", ref, [S('at'), x, y + 5, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
                  [S('property'), "Value", lib_name, [S('at'), x, y + 3.5, 0], font(1.0)],
                  [S('property'), "Footprint", "", [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
                  [S('property'), "Datasheet", "", [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
                  [S('pin'), "1", [S('uuid'), uid()]],
                  [S('instances'), [S('project'), PROJECT, [S('path'), "/" + ROOT, [S('reference'), ref], [S('unit'), 1]]]]])
    nets.setdefault('GND' if lib_name == 'GND' else '(flag)', []).append((ref, '1'))

PICK = {}; SWAP = {}
def place(lib_id, ref, value, x, y, conns, fp="", lcsc="", mpn="", dnp=False, note=""):
    """conns: {pin_number: net or None(no-connect)}; unspecified pins -> no-connect."""
    x, y = POS.get(ref, (x, y))
    if ref in PICK:
        lcsc, mpn = PICK[ref][0], PICK[ref][1]
        if len(PICK[ref]) > 2: fp = PICK[ref][2]
    elif lcsc in SWAP:
        lcsc, mpn = SWAP[lcsc][0], f"{mpn} ({SWAP[lcsc][1]})"
    pins = pin_table[lib_id]
    props = [
        [S('property'), "Reference", ref, [S('at'), x + 2.2, y - 1.2, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], [S('justify'), S('left')]]],
        [S('property'), "Value", value, [S('at'), x + 2.2, y + 1.2, 0], [S('effects'), [S('font'), [S('size'), 1.0, 1.0]], [S('justify'), S('left')]]],
        [S('property'), "Footprint", fp, [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
        [S('property'), "Datasheet", "", [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
        [S('property'), "LCSC", lcsc, [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
        [S('property'), "MPN", mpn, [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
    ]
    if lib_id not in ('Device:R', 'Device:C', 'Device:L', 'Device:Polyfuse') and not lib_id.startswith('carradio:'):
        h = max(abs(p[3]) for p in pins) + 4
        props[0][3] = [S('at'), x, y - h - 1.3, 0]
        props[0][4] = font()
        props[1][3] = [S('at'), x, y + h, 0]
        props[1][4] = font(1.0)
    if lib_id.startswith('carradio:'):
        # box symbols carry their own ref/value text positions
        top = max(abs(p[3]) for p in pins) + 2.54
        props[0][3] = [S('at'), x, y - top - 1.27, 0]
        props[0][4] = font()
        props[1][3] = [S('at'), x, y + top + 1.27, 0]
        props[1][4] = font()
    pin_entries = [[S('pin'), p[0], [S('uuid'), uid()]] for p in pins]
    items.append([S('symbol'), [S('lib_id'), lib_id], [S('at'), x, y, 0], [S('unit'), 1],
                  [S('in_bom'), S('yes')], [S('on_board'), S('yes')], [S('dnp'), S('yes') if dnp else S('no')],
                  [S('fields_autoplaced')], [S('uuid'), uid()]] + props + pin_entries +
                 [[S('instances'), [S('project'), PROJECT, [S('path'), "/" + ROOT, [S('reference'), ref], [S('unit'), 1]]]]])
    for (num, nm, px, py, pa, typ) in pins:
        ax, ay = x + px, y - py
        out = int((pa + 180) % 360)
        net = conns.get(num, conns.get(nm, None))
        if net is None:
            noconn(ax, ay)
        elif net == 'GND':
            power('GND', ax, ay, out)
        else:
            label(net, ax, ay, out)
            nets.setdefault(net, []).append((ref, num))
    bom.append(dict(ref=ref, value=value, fp=fp, lcsc=lcsc, mpn=mpn, dnp=dnp, note=note))

PICK.update({'J1': ('C277661', 'Molex 43045-0812'), 'J8': ('C234188', 'Molex 43045-0612'), 'J3': ('C124410', 'Ckmtw B-2200S20P-A120 1x20 female 2.54mm'), 'J4': ('C124410', 'Ckmtw B-2200S20P-A120 1x20 female 2.54mm'), 'JP1': ('C124375', '1x2 male header 2.54mm + jumper cap C5305'), 'J16': ('C124375', '1x2 male header 2.54mm (or solder wires)'), 'J10': ('C124381', 'Ckmtw B-2100S08P-A110 1x8 male header'), 'J2': ('C9138', 'BOOMELE 2.54-2*20P box header (check it is shrouded)'), 'J5': ('C131337', 'JST B2B-PH-K-S'), 'J7': ('C131334', 'JST B4B-PH-K-S'), 'J12': ('C157993', 'JST B5B-PH-K-S'), 'J18': ('C158012', 'JST B2B-XH-A'), 'J11': ('C3172723', 'Amphenol 132289 SMA edge mount (cheaper: XUNPU C5723200, check pads)'), 'J13': ('C427307', 'Amphenol 10029449-111RLF (plating variant of -001RLF; confirm land pattern)'), 'J14': ('C2856837', 'XUNPU FPC-05FB-40PH20, 40P 0.5mm dual-contact flip-top 2.0mm (use the LCSC footprint, not FH12)'), 'J17': ('C2798029', 'Molex 67643-0910 USB-A'), 'J19': ('C2798029', 'Molex 67643-0910 USB-A'), 'J20': ('C2798029', 'Molex 67643-0910 USB-A'), 'F4': ('C206907', 'Littelfuse 01530008Z mini blade holder (use the LCSC footprint) + fuse C178942 Littelfuse 029707.5WXNV 7.5A', ''), 'F1': ('C883126', 'BHFUSE BSMD1206-050-30V'), 'F3': ('C883126', 'BHFUSE BSMD1206-050-30V'), 'F2': ('C151170', 'Littelfuse 1812L075/33DR'), 'F5': ('C75464', 'Bourns MF-NSMF050-2'), 'D2': ('C151920', 'SMBJ22A (BORN); alt DOWO C284010'), 'D5': ('C151920', 'SMBJ22A (BORN); alt DOWO C284010'), 'D13': ('C151920', 'SMBJ22A (BORN); alt DOWO C284010'), 'D14': ('C2990362', 'Liown 5.0SMDJ22A, 5 kW SMC'), 'Q2': ('C400792', 'onsemi FDN5618P -60V P-MOSFET (check 1=G 2=S 3=D in datasheet)'), 'Q3': ('C8545', 'JSCJ 2N7002'), 'Q10': ('C130101', 'NCE40P70K -40V 10 mOhm P-MOSFET TO-252 (alt Diodes DMP4015SK3-13 C513222)'), 'C48': ('C178548', 'Panasonic EEEFK1H101P 100uF 50V 8x10.2'), 'C60': ('C881921', 'Lelon OVZ221M1CTR-0608 polymer 220uF 16V'), 'L2': ('C12669', 'Murata LQG15HS27NJ02D'), 'L3': ('C780205', 'Bourns SRP1265A-4R7M 4.7uH Isat 28A 8.4 mOhm, 13.5x12.5mm (SRP1245A land pattern)', 'Inductor_SMD:L_Bourns_SRP1245A'), 'L4': ('C19191627', 'Coilcraft XAL6060-822MEC 8.2uH Isat 8.4A 24 mOhm (expensive; any 8.2-10uH shielded, Isat >= 5A works)', 'Inductor_SMD:L_Coilcraft_XAL6060-XXX'), 'R69': ('C22984', 'UNI-ROYAL 0603WAF3002T5E'), 'R74': ('C375691', 'Yageo PA2512FKE7T0R01E 10 mOhm 1% 3W'), 'D10': ('C2297', 'KT-0805G green LED'), 'Y1': ('C9002', 'YXC X322512MSB4SI 12MHz'), 'Y2': ('C9002', 'YXC X322512MSB4SI 12MHz'), 'U17': ('C7519', 'ST USBLC6-2SC6'), 'U18': ('C7519', 'ST USBLC6-2SC6')})
SWAP.update({'C13585': ('C77092', 'Murata GRM31CR61H106KA12L'), 'C106900': ('C470884', 'EL817S1(C)(TU)-FV'), 'C80670': ('C5370990', 'TECH PUBLIC TPLP5907MFX-3.3 clone; TI part out of stock at LCSC'), 'C15849': ('C77386', 'Murata GRM188R61H105KAALD'), 'C57112': ('C1589', 'Samsung CL10B103KB8NNNC'), 'C25819': ('C105579', 'YAGEO RC0603FR-0747KL')})

# ================================================================ rev 0.2 body
R = add_lib('Device', 'R'); C = add_lib('Device', 'C'); L = add_lib('Device', 'L')
DS = add_lib('Device', 'D_Schottky'); DZ = add_lib('Device', 'D_Zener'); PF = add_lib('Device', 'Polyfuse')
LED = add_lib('Device', 'LED')
OPTO = add_lib('Isolator', 'EL817'); NMOS = add_lib('Transistor_FET', 'AO3400A'); PMOS = add_lib('Transistor_FET', 'AO3401A')
D4148 = add_lib('Diode', '1N4148W')
CG2 = add_lib('Connector_Generic', 'Conn_01x02'); CG3 = add_lib('Connector_Generic', 'Conn_01x03'); CG4 = add_lib('Connector_Generic', 'Conn_01x04')
CG8 = add_lib('Connector_Generic', 'Conn_01x08')
M2x2 = add_lib('Connector_Generic', 'Conn_02x02_Odd_Even'); M2x3 = add_lib('Connector_Generic', 'Conn_02x03_Odd_Even')
M2x4 = add_lib('Connector_Generic', 'Conn_02x04_Odd_Even')
COAX = add_lib('Connector', 'Conn_Coaxial')
LDO = add_lib('Regulator_Linear', 'LP5907MFX-3.3')
GNSS = add_lib('RF_GPS', 'NEO-M9N')
DAC = add_lib('Audio', 'PCM5102A')

FP_R0603 = "Resistor_SMD:R_0603_1608Metric"; FP_R0805 = "Resistor_SMD:R_0805_2012Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"; FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"; FP_C1206 = "Capacitor_SMD:C_1206_3216Metric"
FP_SMA = "Diode_SMD:D_SMA"; FP_SMB = "Diode_SMD:D_SMB"; FP_SOD123 = "Diode_SMD:D_SOD-123"; FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"
FP_OPTO = "Package_DIP:SMDIP-4_W7.62mm"
MF = "Connector_Molex:Molex_Micro-Fit_3.0_43045-{}_2x0{}_P3.00mm_Vertical"

RES = {"10": "C22859", "33": "C23140", "100": "C22775", "470": "C23179", "1k": "C21190", "4.7k": "C23162", "10k": "C25804",
       "24k": "C23352", "100k": "C25803", "39k": "C23153", "22k": "C31850", "8.2k": "C25981", "20k": "C4184", "30k": "", "47k": "C25819", "220k": "C22961", "1M": "C22935", "0": "C21189"}
def res(ref, val, x, y, a, b, dnp=False, note=""):
    place(R, ref, val + ("Ω" if val[-1].isdigit() else ""), x, y, {"1": a, "2": b}, FP_R0603, RES[val], f"0603 {val} 1%", dnp, note)
def res0805(ref, x, y, a, b, note=""):
    place(R, ref, "4.7kΩ 0805", x, y, {"1": a, "2": b}, FP_R0805, "C17673", "0805 4.7k 1%", note=note)
CAPS = {"100n": (FP_C0603, "C14663", "0603 100nF 50V X7R", "100nF"), "10u50": (FP_C1206, "C13585", "1206 10uF 50V X5R", "10uF 50V"),
        "22u": (FP_C0805, "C45783", "0805 22uF 25V X5R", "22uF"), "10u": (FP_C0805, "C15850", "0805 10uF 25V X5R", "10uF"),
        "1u": (FP_C0603, "C15849", "0603 1uF 50V X5R", "1uF"), "2u2": (FP_C0603, "C23630", "0603 2.2uF 16V X5R", "2.2uF"),
        "10n": (FP_C0603, "C57112", "0603 10nF 50V X7R", "10nF"), "2n2": (FP_C0805, "C28260", "0805 2.2nF 50V C0G", "2.2nF C0G"),
        "4n7": (FP_C0603, "C53987", "0603 4.7nF 50V X7R", "4.7nF"), "22p": (FP_C0603, "C1653", "0603 22pF 50V C0G", "22pF"),
        "4u7": (FP_C0603, "C19666", "0603 4.7uF 16V X5R", "4.7uF"),
        "100u": ("Capacitor_SMD:C_1206_3216Metric", "C15008", "1206 100uF 6.3V X5R", "100uF 6.3V")}
def cap(ref, val, x, y, a, b, note=""):
    fp, l, m, v = CAPS[val]
    place(C, ref, v, x, y, {"1": a, "2": b}, fp, l, m, note=note)
def tvs(ref, x, y, k):
    place(DZ, ref, "SMBJ22A", x, y, {"1": k, "2": "GND"}, FP_SMB, "", "SMBJ22A 600W TVS (unidirectional) (pick in library)",
          note="review 2026-09-29: 22V standoff survives a 24V jump start; 35.5V max clamp stays under the 38V limit of the TPS560430 and LMR33630")

# ================================================================ 1. ISO 10487 A + always-on supply
text("1. ISO 10487 CONNECTOR A (power) + ALWAYS-ON 5V FOR PICO AND GNSS", 12, 16, 2)
place(M2x4, "J1", "ISO 10487 A (via pigtail)", 30, 45,
      {"1": "REV_RAW", "2": "PARK_RAW", "3": "AMP_REM", "4": "BATT_RAW", "5": "ISO_A5", "6": "ILLUM_RAW", "7": "ACC_RAW", "8": "GND"},
      MF.format("0812", 4), "", "Molex Micro-Fit 3.0 2x4 vertical 43045-0812 (pick in library)",
      note="pad n = ISO A pin n: A1 reverse lamp, A2 handbrake switch, A3 amp remote out, A4 +12V permanent, A5 remote (via R57), A6 illumination, A7 ACC, A8 GND")
text("J1 pad n = ISO A pin n. A1 REVERSE  A2 HANDBRAKE  A3 AMP REMOTE  A4 BATT+  A5 remote (R57)  A6 ILLUM  A7 ACC  A8 GND", 12, 62)
place(PF, "F1", "PTC 0.5A hold 30V", 55, 42, {"1": "BATT_RAW", "2": "BATT_F"}, "Fuse:Fuse_1206_3216Metric", "", "1206 PTC 0.5A hold 30V (pick in library)")
place(DS, "D1", "SS34", 70, 80, {"1": "VBAT_P", "2": "BATT_F"}, FP_SMA, "C8678", "SS34 40V 3A Schottky", note="reverse-polarity protection")
tvs("D2", 70, 90, "VBAT_P")
cap("C1", "10u50", 88, 42, "VBAT_P", "GND")
cap("C2", "100n", 96, 42, "VBAT_P", "GND")
TPS = box_symbol("TPS560430XDBVR", [(5, "VIN"), (4, "EN"), None, (2, "GND")], [(1, "CB"), (6, "SW"), None, (3, "FB")], width=15.24, ref="U")
place(TPS, "U1", "TPS560430XDBVR", 125, 45, {"5": "VBAT_P", "4": "VBAT_P", "2": "GND", "1": "BUCK_CB", "6": "BUCK_SW", "3": "BUCK_FB"},
      "Package_TO_SOT_SMD:SOT-23-6", "C524782", "TPS560430XDBVR 36V 600mA buck, 1.1MHz", note="pinout checked against TI datasheet")
cap("C3", "100n", 160, 42, "BUCK_CB", "BUCK_SW")
place(L, "L1", "18uH", 168, 42, {"1": "BUCK_SW", "2": "+5V_AON"}, "Inductor_SMD:L_Sunlord_SWPA4030S", "C96895", "SWPA4030S180MT 18uH")
res("R1", "100k", 176, 42, "+5V_AON", "BUCK_FB")
res("R2", "24k", 184, 42, "BUCK_FB", "GND", note="Vout = 1.0V x (1 + 100k/24k) = 5.17V")
cap("C4", "22u", 192, 42, "+5V_AON", "GND")
place(DS, "D3", "SS14", 130, 90, {"1": "PICO_VSYS", "2": "+5V_AON"}, FP_SMA, "C2480", "SS14 40V 1A Schottky", note="OR-ing with Pico USB VBUS")
text("Always-on 5.2V: Pico VSYS + GNSS LDO. TPS560430X runs PFM at light load (~55uA Iq).", 105, 105)
# ACC front end (feeds the ACC opto and the amp remote switch)
place(PF, "F2", "PTC 0.75A hold 30V", 55, 130, {"1": "ACC_RAW", "2": "ACC_F"}, "Fuse:Fuse_1812_4532Metric", "", "1812 PTC 0.75A hold 30V (pick in library)")
place(DS, "D4", "SS34", 70, 125, {"1": "ACC_P", "2": "ACC_F"}, FP_SMA, "C8678", "SS34 40V 3A Schottky")
tvs("D5", 70, 135, "ACC_P")
cap("C5", "100n", 88, 130, "ACC_P", "GND")

# ================================================================ 2. opto inputs
text("2. VEHICLE INPUTS (opto-isolated). ACC, ILLUM, REVERSE: +12V = on. PARK: switch to ground = on.", 215, 16, 2)
def opto_in(n, ox, oy, raw, led, pico, rref, dref, uref, rpd, cpd, note):
    res0805(rref, ox, oy - 6, raw, led, note=note)
    place(D4148, dref, "1N4148W", ox + 8, oy + 14, {"1": led, "2": "GND"}, FP_SOD123, "C81598", "1N4148W", note="reverse-voltage clamp across opto LED")
    place(OPTO, uref, "EL817S1(C)", ox + 32, oy, {"1": led, "2": "GND", "4": "+3V3_PICO", "3": pico}, FP_OPTO, "C106900", "EL817S1(C)(TU)-F")
    res(rpd, "4.7k", ox + 52, oy + 4, pico, "GND")
    cap(cpd, "100n", ox + 60, oy + 4, pico, "GND")
    text(n, ox - 4, oy - 22, 1.5)
opto_in("ACC (ISO A7)", 225, 45, "ACC_P", "ACC_LED", "PICO_ACC_IN", "R3", "D6", "U2", "R4", "C6", "")
opto_in("ILLUM (ISO A6)", 315, 45, "ILLUM_RAW", "ILLUM_LED", "PICO_ILLUM_IN", "R5", "D7", "U3", "R6", "C7", "")
opto_in("REVERSE lamp (ISO A1)", 225, 105, "REV_RAW", "REV_LED", "PICO_REV_IN", "R29", "D11", "U4", "R30", "C10", "")
# park brake: the MG F handbrake switch grounds the warning lamp, so the LED is fed from ACC and the switch sinks it
res0805("R31", 315, 99, "ACC_P", "PARK_LED", note="PARK input: LED fed from ACC, handbrake switch pulls cathode to ground")
place(OPTO, "U5", "EL817S1(C)", 347, 105, {"1": "PARK_LED", "2": "PARK_K", "4": "+3V3_PICO", "3": "PICO_PARK_IN"}, FP_OPTO, "C106900", "EL817S1(C)(TU)-F")
place(D4148, "D12", "1N4148W", 323, 119, {"1": "PARK_RAW", "2": "PARK_K"}, FP_SOD123, "C81598", "1N4148W", note="series diode: blocks reverse voltage when ACC is off")
res("R32", "4.7k", 367, 109, "PICO_PARK_IN", "GND")
cap("C11", "100n", 375, 109, "PICO_PARK_IN", "GND")
text("PARK (ISO A2, handbrake switch; may stay unwired)", 311, 83, 1.5)
cap("C8", "100n", 395, 60, "+3V3_PICO", "GND")
res("R57", "0", 545, 100, "AMP_REM", "ISO_A5", dnp=True, note="DNP: fit to also put the amp remote on ISO A5 (the usual antenna/amp remote pin)")
text("LED ~2.7mA at 14.4V; EL817 C-grade CTR >= 200%. 4.7k pull-downs satisfy RP2350-E9.", 215, 140)

# ================================================================ 3. amp remote
text("3. AMPLIFIER REMOTE (+12V from ACC, Pico GP9)", 425, 16, 2)
place(PMOS, "Q2", "P-MOSFET -60V", 470, 45, {"S": "ACC_P", "D": "AMP_SW", "G": "AMP_G"}, FP_SOT23, "", "P-MOSFET SOT-23, -60V, Vgs +-20V, >= 1A, Rds(on) < 0.3 ohm at -10V (pick in library)",
      note="review: AO3401A (-30V) was below the 35.5V TVS clamp")
res("R13", "10k", 440, 34, "ACC_P", "AMP_G")
place(DZ, "D8", "BZT52C12", 448, 55, {"1": "ACC_P", "2": "AMP_G"}, FP_SOD123, "C124196", "BZT52C12-7-F 12V zener", note="Vgs clamp")
res("R14", "10k", 440, 72, "AMP_G", "AMP_PULL")
place(NMOS, "Q3", "2N7002", 470, 95, {"D": "AMP_PULL", "S": "GND", "G": "AMP_CTRL"}, FP_SOT23, "", "2N7002 60V N-MOSFET, SOT-23 G-S-D (pick in library)",
      note="review: drain sees ACC through R13, so it needs more than 30V")
res("R16", "100", 445, 102, "PICO_AMP_EN", "AMP_CTRL")
res("R15", "100k", 455, 118, "AMP_CTRL", "GND", note="amp off while the Pico is in reset")
place(PF, "F3", "PTC 0.5A hold 30V", 495, 45, {"1": "AMP_SW", "2": "AMP_REM"}, "Fuse:Fuse_1206_3216Metric", "", "1206 PTC 0.5A hold 30V (pick in library)",
      note="own fuse: a shorted remote wire cannot pull down ACC")
place(DS, "D9", "SS34", 520, 60, {"1": "AMP_REM", "2": "GND"}, FP_SMA, "C8678", "SS34 40V 3A Schottky", note="clamps inductive kick from the remote wire")
tvs("D13", 520, 72, "AMP_REM")
res("R18", "4.7k", 545, 45, "AMP_REM", "AMP_LED")
place(LED, "D10", "LED green", 555, 65, {"2": "AMP_LED", "1": "GND"}, "LED_SMD:LED_0805_2012Metric", "", "0805 green LED (pick in library)", note="amp remote on")
text("Goes to ISO A3 and C1-6 (A5 via R57). ~1A capable; remote inputs draw <100mA.", 425, 135)
text("Only works while ACC is on, even if the Pico hangs.", 425, 139)

# ================================================================ 4. Pico
text("4. PICO 2 (on two 1x20 sockets) + USB to VIM3", 12, 158, 2)
pico_nets = {1: "PICO_GNSS_TX", 2: "PICO_GNSS_RX", 3: "GND", 4: "PICO_ACC_IN", 5: "PICO_REV_IN", 6: "LUX_SDA", 7: "LUX_SCL", 8: "GND",
             9: "PICO_ILLUM_IN", 10: "PICO_PARK_IN", 11: "PICO_PWR_KEY", 12: "PICO_AMP_EN", 13: "GND", 14: "PICO_BL_EN", 15: "PICO_BL_PWM",
             16: "PICO_GNSS_EN", 17: "PICO_SBC_SENSE", 18: "GND", 19: "PICO_SERVICE", 20: "PICO_DAC_MUTE",
             23: "GND", 24: "PICO_GNSS_RST", 25: "PICO_GNSS_PPS", 26: "EXP_GP20", 27: "EXP_GP21", 28: "GND", 29: "PICO_BTN_VOLDN", 21: "PICO_BTN_SCREEN", 22: "PICO_BTN_VOLUP",
             31: "PICO_VBAT_ADC", 32: "PICO_BTN_MUTE", 33: "GND", 34: "PICO_VIM3_PWR_EN", 36: "+3V3_PICO", 38: "GND", 39: "PICO_VSYS"}
pico_names = {1: "GP0", 2: "GP1", 3: "GND", 4: "GP2", 5: "GP3", 6: "GP4", 7: "GP5", 8: "GND", 9: "GP6", 10: "GP7", 11: "GP8", 12: "GP9",
              13: "GND", 14: "GP10", 15: "GP11", 16: "GP12", 17: "GP13", 18: "GND", 19: "GP14", 20: "GP15", 21: "GP16", 22: "GP17",
              23: "GND", 24: "GP18", 25: "GP19", 26: "GP20", 27: "GP21", 28: "GND", 29: "GP22", 30: "RUN", 31: "GP26_ADC0", 32: "GP27_ADC1",
              33: "AGND", 34: "GP28_ADC2", 35: "ADC_VREF", 36: "3V3_OUT", 37: "3V3_EN", 38: "GND", 39: "VSYS", 40: "VBUS"}
PL = box_symbol("Pico2_Left_1x20", [(i, f"{i}:{pico_names[i]}") for i in range(1, 21)], [], width=17.78, ref="J", value="Pico2 pins 1-20")
PR = box_symbol("Pico2_Right_1x20", [], [(i - 20, f"{i}:{pico_names[i]}") for i in range(21, 41)], width=17.78, ref="J", value="Pico2 pins 21-40")
place(PL, "J3", "Pico 2 pins 1-20 (1x20 F)", 45, 200, {str(i): pico_nets.get(i) for i in range(1, 21)},
      "Connector_PinSocket_2.54mm:PinSocket_1x20_P2.54mm_Vertical", "", "1x20 2.54mm female header (pick in library)", note="pad n = Pico pin n")
place(PR, "J4", "Pico 2 pins 21-40 (1x20 F)", 95, 200, {str(i - 20): pico_nets.get(i) for i in range(21, 41)},
      "Connector_PinSocket_2.54mm:PinSocket_1x20_P2.54mm_Vertical", "", "1x20 2.54mm female header (pick in library)", note="pad n = Pico pin 20+n")
text("USB: Pico micro-USB cable to a VIM3 USB-A port (HID vehicle data + CDC GNSS bridge).", 12, 240)
text("GP0/1 GNSS UART0, GP2 ACC, GP3 REV, GP4/5 I2C0 lux, GP6 ILLUM, GP7 PARK, GP8 PWR key, GP9 AMP,", 12, 244)
text("GP10 BL_EN, GP11 BL_PWM, GP12 GNSS_EN, GP13 SBC sense, GP14 service, GP15 DAC mute, GP18 GNSS reset,", 12, 248)
text("GP19 GNSS PPS, GP20/21 UART1 (K-line, reserved), GP16/17/22/27 display buttons, GP28 VIM3 5V supply enable, GP26 battery voltage.", 12, 252)
res("R7", "1k", 130, 180, "VIM3_3V3", "PICO_SBC_SENSE", note="VIM3 on/off sense")
res("R8", "4.7k", 138, 180, "PICO_SBC_SENSE", "GND")
res("R10", "1M", 146, 180, "VBAT_P", "PICO_VBAT_ADC", note="battery sense: 14.4V -> 2.6V")
res("R11", "220k", 154, 180, "PICO_VBAT_ADC", "GND")
cap("C9", "100n", 162, 180, "PICO_VBAT_ADC", "GND")
place(CG2, "JP1", "SERVICE jumper", 135, 215, {"1": "+3V3_PICO", "2": "PICO_SERVICE"}, "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "", "1x2 2.54mm pin header + jumper")
res("R9", "4.7k", 150, 218, "PICO_SERVICE", "GND")
place(CG8, "J10", "Expansion", 185, 205, {"1": "+3V3_PICO", "2": "EXP_GP20", "3": "EXP_GP21", "4": None, "5": "+5V_AON", "6": "GND", "7": "GND", "8": None},
      "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical", "", "1x8 2.54mm pin header",
      note="GP20/21 = UART1 for a future K-line (L9637D) board")

# ================================================================ 5. GNSS
text("5. GNSS: u-blox NEO-M9N, active antenna on SMA", 215, 158, 2)
place(LDO, "U6", "LP5907MFX-3.3", 240, 190, {"1": "+5V_AON", "3": "PICO_GNSS_EN", "2": "GND", "5": "+3V3_GNSS"}, FP_SOT23.replace("SOT-23", "SOT-23-5"),
      "C80670", "TI LP5907MFX-3.3/NOPB 250mA LDO", note="GNSS supply, switched by Pico GP12")
cap("C12", "1u", 222, 205, "+5V_AON", "GND")
res("R35", "100k", 230, 205, "PICO_GNSS_EN", "GND", note="GNSS off by default")
cap("C13", "1u", 255, 205, "+3V3_GNSS", "GND")
cap("C14", "10u", 263, 205, "+3V3_GNSS", "GND")
cap("C15", "100n", 271, 205, "+3V3_GNSS", "GND")
cap("C16", "100n", 279, 205, "+3V3_PICO", "GND", note="at V_BCKP")
place(GNSS, "U7", "NEO-M9N-00B", 330, 205,
      {"23": "+3V3_GNSS", "22": "+3V3_PICO", "7": "GND", "9": "GNSS_VCCRF", "10": "GND", "12": "GND", "13": "GND", "24": "GND",
       "11": "GNSS_RF", "20": "GNSS_TXD", "21": "GNSS_RXD", "8": "GNSS_RST", "3": "GNSS_PPS"},
      "RF_GPS:ublox_NEO", "C5119087", "u-blox NEO-M9N-00B",
      note="V_BCKP from always-on 3V3 for hot starts. V_USB tied to GND (USB unused). SAFEBOOT_N: add a test pad in layout.")
res("R37", "1k", 262, 235, "PICO_GNSS_TX", "GNSS_RXD")
res("R38", "1k", 270, 235, "GNSS_TXD", "PICO_GNSS_RX")
res("R39", "1k", 278, 235, "PICO_GNSS_RST", "GNSS_RST", note="firmware drives low only to reset")
res("R40", "1k", 286, 235, "GNSS_PPS", "PICO_GNSS_PPS")
cap("C17", "10n", 360, 170, "GNSS_VCCRF", "GND")
res("R41", "10", 368, 170, "GNSS_VCCRF", "ANT_FEED", note="antenna supply, limits short-circuit current")
place(L, "L2", "27nH RF", 376, 170, {"1": "ANT_FEED", "2": "GNSS_RF"}, "Inductor_SMD:L_0402_1005Metric", "", "27nH 0402 RF inductor, e.g. Murata LQG15HS27NJ02 (pick in library)",
      note="RF choke: feeds DC to the antenna, blocks GNSS signal")
place(COAX, "J11", "SMA GNSS antenna", 385, 205, {"1": "GNSS_RF", "2": "GND"}, "Connector_Coaxial:SMA_Amphenol_132289_EdgeMount", "",
      "SMA edge-mount jack (pick in library)", note="50 ohm coplanar trace to RF_IN, as short as possible")
text("Active antenna (3.3V): VCC_RF -> 10R -> 27nH onto RF_IN. RF_IN is DC-blocked inside the module (verify in the integration manual).", 215, 250)

# ================================================================ 6. Pico peripherals: power key, backlight, lux
text("6. VIM3 POWER KEY, BACKLIGHT, LIGHT SENSOR (all from the Pico)", 425, 158, 2)
place(NMOS, "Q1", "AO3400A", 450, 185, {"D": "VIM3_PWR_KEY", "S": "GND", "G": "PWR_KEY_G"}, FP_SOT23, "C20917", "AO3400A 30V 5.7A N-MOSFET",
      note="open-drain press of the active-low VIM3 POWER key (GPIOAO_7)")
res("R12", "100", 430, 185, "PICO_PWR_KEY", "PWR_KEY_G")
res("R19", "100k", 438, 200, "PWR_KEY_G", "GND")
place(CG2, "J5", "VIM3 POWER key lead", 475, 185, {"1": "VIM3_PWR_KEY", "2": "GND"}, "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", "",
      "JST-PH 2P (pick in library)", note="wire to the VIM3 power-key pad")
res("R23", "100", 500, 180, "PICO_BL_EN", "BL_EN")
res("R24", "100", 508, 180, "PICO_BL_PWM", "BL_PWM")
res("R33", "4.7k", 500, 225, "+3V3_PICO", "LUX_SCL")
res("R34", "4.7k", 508, 225, "+3V3_PICO", "LUX_SDA")
place(CG4, "J7", "BH1750 light sensor", 530, 225, {"1": "+3V3_PICO", "2": "GND", "3": "LUX_SCL", "4": "LUX_SDA"}, "Connector_JST:JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical", "", "JST-PH 4P (pick in library)")
text("Backlight and reverse moved off the VIM3 header; the VHAL now sets/reads them through the Pico.", 425, 262)
# display buttons: switch to ground, pull-up + series R + RC filter at the Pico
BTNS = [("SCREEN", "R58", "R59", "C42"), ("VOLUP", "R60", "R61", "C43"), ("VOLDN", "R62", "R63", "C44"), ("MUTE", "R64", "R65", "C45")]
bx = 425
for nm, rpu, rser, cf in BTNS:
    res(rpu, "10k", bx, 232, "+3V3_PICO", f"PICO_BTN_{nm}")
    res(rser, "1k", bx + 6, 232, f"BTN_{nm}", f"PICO_BTN_{nm}")
    cap(cf, "100n", bx + 12, 232, f"PICO_BTN_{nm}", "GND")
    bx += 18
place(add_lib('Connector_Generic', 'Conn_01x05'), "J12", "Display buttons", 568, 195,
      {"1": "BTN_SCREEN", "2": "BTN_VOLUP", "3": "BTN_VOLDN", "4": "BTN_MUTE", "5": "GND"},
      "Connector_JST:JST_PH_B5B-PH-K_1x05_P2.00mm_Vertical", "", "JST-PH 5P (pick in library)",
      note="momentary buttons to ground: 1 screen off, 2 volume up, 3 volume down, 4 mute, 5 GND")
text("Display buttons (to GND): GP16 screen, GP17 vol+, GP22 vol-, GP27 mute. J12.", 425, 257)

# ================================================================ 7. audio
text("7. AUDIO: VIM3 TDM-B I2S -> 2x PCM5102A (front + rear) -> line out on ISO C1", 12, 268, 2)
place(LDO, "U8", "LP5907MFX-3.3", 40, 300, {"1": "VIM3_5V", "3": "VIM3_5V", "2": "GND", "5": "+3V3_DAC_A"}, "Package_TO_SOT_SMD:SOT-23-5",
      "C80670", "TI LP5907MFX-3.3/NOPB 250mA LDO", note="DAC analog supply (AVDD + CPVDD)")
cap("C18", "1u", 22, 318, "VIM3_5V", "GND")
cap("C19", "1u", 58, 318, "+3V3_DAC_A", "GND")
place(LDO, "U9", "LP5907MFX-3.3", 40, 345, {"1": "VIM3_5V", "3": "VIM3_5V", "2": "GND", "5": "+3V3_DAC_D"}, "Package_TO_SOT_SMD:SOT-23-5",
      "C80670", "TI LP5907MFX-3.3/NOPB 250mA LDO", note="DAC digital supply (DVDD)")
cap("C20", "1u", 22, 363, "VIM3_5V", "GND")
cap("C21", "1u", 58, 363, "+3V3_DAC_D", "GND")
res("R42", "33", 85, 385, "VIM3_I2S_BCLK", "I2S_BCLK")
res("R43", "33", 93, 385, "VIM3_I2S_LRCK", "I2S_LRCK")
res("R44", "33", 101, 385, "VIM3_I2S_DOUT0", "I2S_DOUT0")
res("R45", "33", 109, 385, "VIM3_I2S_DOUT1", "I2S_DOUT1")
res("R46", "1k", 125, 385, "PICO_DAC_MUTE", "DAC_XSMT", note="limits back-feed when the VIM3 (DAC supply) is off")
res("R47", "10k", 133, 385, "DAC_XSMT", "GND", note="DACs muted unless the Pico unmutes")
text("I2S series resistors at the ribbon entry.", 80, 405)

def dac(ref, ox, din, outl, outr, caps, rs, lines, name):
    place(DAC, ref, "PCM5102APWR", ox, 320,
          {"1": "+3V3_DAC_A", "8": "+3V3_DAC_A", "20": "+3V3_DAC_D", "3": "GND", "9": "GND", "19": "GND",
           "2": f"{ref}_CAPP", "4": f"{ref}_CAPM", "5": f"{ref}_VNEG", "18": f"{ref}_LDOO",
           "10": "GND", "11": "GND", "12": "GND", "16": "GND",
           "13": "I2S_BCLK", "15": "I2S_LRCK", "14": din, "17": "DAC_XSMT", "6": outl, "7": outr},
          "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm", "C107671", "TI PCM5102APWR 32-bit 384kHz stereo DAC",
          note=f"{name}. SCK=GND (PLL from BCK), FMT=GND (I2S), FLT=GND (normal latency), DEMP=GND")
    c = caps
    cap(c[0], "2u2", ox + 25, 300, f"{ref}_CAPP", f"{ref}_CAPM", note="charge-pump flying cap")
    cap(c[1], "2u2", ox + 33, 300, f"{ref}_VNEG", "GND")
    cap(c[2], "1u", ox + 41, 300, f"{ref}_LDOO", "GND")
    cap(c[3], "100n", ox - 22, 290, "+3V3_DAC_A", "GND", note="at CPVDD")
    cap(c[4], "100n", ox - 14, 290, "+3V3_DAC_A", "GND", note="at AVDD")
    cap(c[5], "100n", ox - 6, 290, "+3V3_DAC_D", "GND", note="at DVDD")
    cap(c[6], "10u", ox + 6, 290, "+3V3_DAC_A", "GND")
    cap(c[7], "10u", ox + 14, 290, "+3V3_DAC_D", "GND")
    res(rs[0], "470", ox + 30, 350, outl, lines[0], note="output RC filter (datasheet)")
    res(rs[1], "470", ox + 38, 350, outr, lines[1])
    cap(c[8], "2n2", ox + 46, 350, lines[0], "GND")
    cap(c[9], "2n2", ox + 54, 350, lines[1], "GND")
dac("U10", 190, "I2S_DOUT0", "DAC_FL", "DAC_FR", ["C22", "C23", "C24", "C25", "C26", "C27", "C28", "C29", "C30", "C31"], ["R48", "R49"], ["LINE_FL", "LINE_FR"], "Front L/R, TDM-B lane 0")
dac("U11", 320, "I2S_DOUT1", "DAC_RL", "DAC_RR", ["C32", "C33", "C34", "C35", "C36", "C37", "C38", "C39", "C40", "C41"], ["R50", "R51"], ["LINE_RL", "LINE_RR"], "Rear L/R, TDM-B lane 1")
text("2.1 Vrms ground-centred line out, no coupling caps. 24-bit in 32-bit I2S slots, 48/96/192 kHz.", 160, 380)

# ================================================================ 8. VIM3 header + ISO C1
text("8. VIM3 40-PIN HEADER + ISO 10487 C1 (line out)", 425, 268, 2)
vim3_sig = {1: "5V", 2: "5V", 3: "USB_DM", 4: "USB_DP", 5: "GND", 6: "VCC_MCU", 7: "MCU_NRST", 8: "MCU_SWIM", 9: "GND", 10: "ADC_CH0",
            11: "1V8", 12: "ADC_CH3", 13: "SPDIF_OUT", 14: "GND", 15: "UARTC_RX", 16: "UARTC_TX", 17: "GND", 18: "Linux_RX", 19: "Linux_TX", 20: "3V3",
            21: "GND", 22: "I2C_M3_SCL", 23: "I2C_M3_SDA", 24: "GND", 25: "I2C_AO_SCK", 26: "I2C_AO_SDA", 27: "3V3", 28: "GND", 29: "TDMB_SCLK",
            30: "TDMB_MCLK", 31: "TDMB_DOUT0", 32: "TDMB_FS", 33: "TDMB_DOUT1", 34: "GND", 35: "TDMB_DOUT3", 36: "RTC_CLK", 37: "GPIOH_4", 38: "MCU_PA1",
            39: "GPIODZ_15", 40: "GND"}
vim3_net = {1: "VIM3_5V", 2: "VIM3_5V", 3: "USB_UP_DM", 4: "USB_UP_DP", 5: "GND", 9: "GND", 14: "GND", 17: "GND", 21: "GND", 24: "GND", 28: "GND", 34: "GND", 40: "GND",
            20: "VIM3_3V3", 27: "VIM3_3V3", 29: "VIM3_I2S_BCLK", 31: "VIM3_I2S_DOUT0", 32: "VIM3_I2S_LRCK", 33: "VIM3_I2S_DOUT1"}
def pad(v): return 2 * v - 1 if v <= 20 else 2 * (v - 20)
VH = box_symbol("VIM3_40pin_IDC", [(pad(v), f"V{v}:{vim3_sig[v]}") for v in range(1, 21)],
                [(pad(v), f"V{v}:{vim3_sig[v]}") for v in range(21, 41)], width=30.48, ref="J", value="VIM3 40-pin (2x20 IDC)")
place(VH, "J2", "VIM3 40-pin via 2x20 IDC ribbon", 470, 330, {str(pad(v)): vim3_net.get(v) for v in range(1, 41)},
      "Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical", "", "2x20 2.54mm shrouded box header (pick in library)",
      note="pin names are VIM3 numbers (Vn); pad numbers are IDC odd/even")
text("VIM3 pin v -> IDC pad 2v-1 (v<=20) or 2(v-20) (v>20). Pin 1 sits opposite pin 21 (confirmed by Glenn).", 425, 372)
text("Pin 35 (TDM-B lane 3) left free for a later sub/3rd pair. MCLK (30) not used.", 425, 376)
place(M2x3, "J8", "ISO 10487 C1 (via pigtail)", 545, 300,
      {"1": "LINE_RL", "2": "LINE_RR", "3": "LINE_FL", "4": "LINE_FR", "5": "LINE_GND", "6": "AMP_REM"},
      MF.format("0612", 3), "", "Molex Micro-Fit 3.0 2x3 vertical 43045-0612 (pick in library)",
      note="pad n = ISO C1 pin n: 1 rear L, 2 rear R, 3 front L, 4 front R, 5 line-out ground, 6 remote")
res("R56", "0", 545, 330, "LINE_GND", "GND", note="ground-lift option: fit 0R, or 10R if the amp hums (alternator whine)")
text("J8 pad n = ISO C1 pin n: 1 RL, 2 RR, 3 FL, 4 FR, 5 line GND, 6 remote +12V.", 505, 345)

# ================================================================ 9. display (Waveshare 70H-1024600 adapter, embedded)
text("9. DISPLAY: Waveshare 7in 70H-1024600 adapter built in (HDMI in from VIM3 -> 40-pin FPC to the panel)", 12, 428, 2)
HDMI = add_lib('Connector', 'HDMI_A')
place(HDMI, "J13", "HDMI in (from VIM3)", 60, 490,
      {"1": "HDMI_D2P", "3": "HDMI_D2N", "4": "HDMI_D1P", "6": "HDMI_D1N", "7": "HDMI_D0P", "9": "HDMI_D0N", "10": "HDMI_CLKP", "12": "HDMI_CLKN",
       "2": "GND", "5": "GND", "8": "GND", "11": "GND", "17": "GND", "SH": "GND",
       "13": "HDMI_CEC", "15": "HDMI_SCL", "16": "HDMI_SDA", "18": "HDMI_5V", "19": "HDMI_HPD"},
      "Connector_HDMI:HDMI_A_Amphenol_10029449-x01xLF_Horizontal", "", "HDMI type A receptacle (pick in library)",
      note="short HDMI cable from the VIM3. Route TMDS pairs as 100 ohm differential, length-matched")
FPC = add_lib('Connector_Generic', 'Conn_01x40')
fpc = {4: "+5V_SYS", 5: "+5V_SYS", 6: "+5V_SYS", 11: "HDMI_D2P", 13: "HDMI_D2N", 14: "HDMI_D1P", 16: "HDMI_D1N", 17: "HDMI_D0P", 19: "HDMI_D0N",
       20: "HDMI_CLKP", 22: "HDMI_CLKN", 23: "HDMI_CEC", 24: "HDMI_SCL", 25: "HDMI_SDA", 27: "HDMI_5V", 28: "HDMI_HPD",
       33: "TOUCH_DP", 34: "TOUCH_DN", 36: "BL_PWM", 37: "BL_EN"}
for g in (8, 9, 10, 12, 15, 18, 21, 26, 35): fpc[g] = "GND"
place(FPC, "J14", "Display FPC 40P 0.5mm", 200, 490, {str(i): fpc.get(i) for i in range(1, 41)},
      "Connector_FFC-FPC:Hirose_FH12-40S-0.5SH_1x40-1MP_P0.50mm_Horizontal", "", "40-pin 0.5mm FPC, flip-lock, DUAL-CONTACT (top + bottom), 2.0mm high (pick in library)",
      note="pinout from the Waveshare HDMI LCD Adapter schematic (Glenn, 2026-09-29): 1-3 = 12V (NC on the adapter, R1 not fitted), 4-6 = 5V, 7 = 3V3 out from the panel (unused), 8-10 GND, 29-32 audio (unused), 38-40 KEY/IO0/IO1 (unused), mounting tabs = GND")
USBM = add_lib('Connector', 'USB_B_Micro')
cap("C46", "10u", 245, 450, "+5V_SYS", "GND", note="at FPC 5V pins")
cap("C47", "100n", 253, 450, "+5V_SYS", "GND")
text("Panel 5V (~0.45A) comes from the board's switched 5V rail (+5V_SYS, section 10), not from VIM3 USB. Touch USB goes to the on-board hub (section 11).", 12, 552)
text("Backlight EN/PWM now go straight to the panel: 0V = brightest, 3.3V = darkest (invert PWM in firmware). J6 removed.", 12, 556)
text("FPC orientation as on the Waveshare adapter: seen from the top, ribbon leaving the board edge, pin 1 is on the RIGHT, pin 40 on the left.", 12, 560)

# ================================================================ 10. VIM3 + screen 5V supply (buck-boost)
text("10. 5V/5A SYSTEM SUPPLY FOR VIM3 + SCREEN + HUB (TPS55288 buck-boost, rides through cranking and overvoltage)", 610, 16, 2)
place(add_lib('Device', 'Fuse'), "F4", "7.5A fuse", 615, 50, {"1": "BATT_RAW", "2": "BATT_F2"}, "Fuse:Fuseholder_Blade_Mini_Keystone_3568", "",
      "Mini blade fuse holder + 7.5A fuse (pick in library)", note="feeds the VIM3 supply from permanent +12V (ISO A4)")
PFET = add_lib('Device', 'Q_PMOS_GDS')
place(PFET, "Q10", "P-MOSFET -40V", 640, 45, {"D": "BATT_F2", "S": "VSYS_IN", "G": "RPP_G"}, "Package_TO_SOT_SMD:TO-252-2", "",
      "P-MOSFET, -40V or more, <=10 mOhm, e.g. SQD40031EL (pick in library)", note="reverse-polarity protection, no diode drop")
place(DZ, "D15", "BZT52C12", 632, 62, {"1": "VSYS_IN", "2": "RPP_G"}, FP_SOD123, "C124196", "BZT52C12-7-F 12V zener", note="Vgs clamp")
res("R66", "10k", 646, 70, "RPP_G", "GND")
place(DZ, "D14", "Load-dump TVS", 664, 62, {"1": "VSYS_IN", "2": "GND"}, "Diode_SMD:D_SMC", "", "Load-dump TVS SM8S22A (pick in library)",
      note="SM8S: 6.6 kW, rated for ISO 16750 load dump. 24.4V min breakdown (survives a 24V jump start), 35.5V max clamp, under the 38V limit of U15 and 40V of U12")
place(add_lib('Device', 'C_Polarized'), "C48", "100uF 50V", 676, 50, {"1": "VSYS_IN", "2": "GND"}, "Capacitor_SMD:CP_Elec_8x10", "", "100uF 50V aluminium electrolytic (pick in library)",
      note="bulk + input damping")
cap("C49", "10u50", 684, 50, "VSYS_IN", "GND")
cap("C50", "10u50", 692, 50, "VSYS_IN", "GND")
TPS88 = box_symbol("TPS55288RPMR",
    [(3, "VIN"), (4, "EN/UVLO"), (5, "SCL"), (6, "SDA"), (15, "MODE"), (7, "DITH/SYNC"), (8, "FSW"), (17, "ILIM"), (16, "CDC"), (18, "COMP"), (14, "FB/INT"), None, (10, "AGND"), (9, "PGND"), (24, "PGND")],
    [(2, "DR1H"), (22, "BOOT1"), (23, "SW1"), (1, "DR1L"), None, (21, "SW2"), (25, "SW2"), (20, "BOOT2"), None, (11, "VOUT"), (26, "VOUT"), (12, "ISP"), (13, "ISN"), (19, "VCC")],
    width=22.86, ref="U")
place(TPS88, "U12", "TPS55288RPMR", 735, 110,
      {"3": "VSYS_IN", "4": "VIM3_PWR_EN", "5": "LUX_SCL", "6": "LUX_SDA", "15": "BB_MODE", "7": "GND", "8": "BB_FSW", "17": "BB_ILIM", "16": "BB_CDC",
       "18": "BB_COMP", "14": None, "10": "GND", "9": "GND", "24": "GND",
       "2": "BB_DR1H", "22": "BB_BOOT1", "23": "BB_SW1", "1": "BB_DR1L", "21": "BB_SW2", "25": "BB_SW2", "20": "BB_BOOT2",
       "11": "BB_VOUT", "26": "BB_VOUT", "12": "BB_VOUT", "13": "+5V_SYS", "19": "BB_VCC"},
      "", "C2864583", "TI TPS55288RPMR 36V buck-boost, I2C (footprint: use the EasyEDA library part)",
      note="pinout from TI datasheet SLVSF01B Table 5-1. Powers up with output off: the Pico enables it over I2C (address 0x74, OE bit) after EN goes high. Default 5.0V")
res("R67", "0", 700, 150, "BB_MODE", "GND", note="MODE = 0 ohm: internal VCC, I2C 0x74, forced PWM")
res("R68", "47k", 707, 150, "BB_FSW", "GND", note="fsw = 1000/(0.05 x 47000 + 20) = 422 kHz")
res("R69", "30k", 714, 150, "BB_ILIM", "GND", note="average inductor current limit = 330000/R = 11 A (max ~12.7 A), below L3 saturation; still covers 25 W out at 3 V in")
res("R70", "100k", 721, 150, "BB_CDC", "GND")
res("R71", "8.2k", 690, 175, "BB_COMP", "BB_COMP_RC", note="compensation calculated for fc ~2.5-4 kHz, Cout ~60uF effective; check on the bench")
cap("C54", "4n7", 690, 190, "BB_COMP_RC", "GND")
cap("C55", "22p", 698, 182, "BB_COMP", "GND")
res("R72", "100k", 682, 175, "VIM3_PWR_EN", "GND", note="VIM3 supply off unless the Pico enables it")
res("R73", "1k", 674, 175, "PICO_VIM3_PWR_EN", "VIM3_PWR_EN")
NFET = add_lib('Transistor_FET', 'CSD18543Q3A')
place(NFET, "Q11", "CSD18543Q3A", 772, 60, {"5": "VSYS_IN", "1": "BB_SW1", "2": "BB_SW1", "3": "BB_SW1", "4": "BB_DR1H"}, "Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET",
      "C840100", "TI CSD18543Q3A 60V 8.5mOhm N-MOSFET", note="buck-side high-side switch")
place(NFET, "Q12", "CSD18543Q3A", 772, 90, {"5": "BB_SW1", "1": "GND", "2": "GND", "3": "GND", "4": "BB_DR1L"}, "Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET",
      "C840100", "TI CSD18543Q3A 60V 8.5mOhm N-MOSFET", note="buck-side low-side switch")
cap("C51", "100n", 790, 60, "BB_BOOT1", "BB_SW1")
place(L, "L3", "4.7uH 12A+", 800, 75, {"1": "BB_SW1", "2": "BB_SW2"}, "Inductor_SMD:L_Vishay_IHLP-5050", "",
      "4.7uH, Isat >= 15A, DCR ~10 mOhm, e.g. Vishay IHLP5050EZER4R7 (datasheet list; pick in library)")
cap("C52", "100n", 810, 60, "BB_BOOT2", "BB_SW2")
cap("C53", "4u7", 770, 150, "BB_VCC", "GND", note="VCC; join AGND to PGND at this capacitor")
for i, r in enumerate(["C56", "C57", "C58", "C59"]):
    cap(r, "22u", 770 + 8 * i, 175, "BB_VOUT", "GND")
place(add_lib('Device', 'C_Polarized'), "C60", "220uF 10V polymer", 805, 175, {"1": "BB_VOUT", "2": "GND"}, "Capacitor_SMD:CP_Elec_6.3x7.7", "",
      "220uF 10V polymer, low ESR (pick in library)")
place(R, "R74", "10mΩ 2512", 818, 140, {"1": "BB_VOUT", "2": "+5V_SYS"}, "Resistor_SMD:R_2512_6332Metric", "", "10 mOhm 1% 2512 current sense (pick in library)",
      note="ISP/ISN sense: 50 mV default = 5 A output current limit, adjustable to 6.35 A over I2C")
place(CG2, "J18", "VIM3 VIN (JST-XH 2P)", 800, 140, {"1": "+5V_SYS", "2": "GND"}, "Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical", "",
      "JST-XH B2B-XH-A 2-pin header (pick in library)", note="mates with Glenn's existing VIM3 VIN lead: pin 1 +, pin 2 -. VIM3 VIN accepts 5-12V (Khadas docs)")
text("Input 3V-36V (runs through cranking); output 5.0V up to 5A. Pico GP28 = EN, Pico I2C0 sets OE/voltage/current limit.", 610, 205)
text("VIN is permanent +12V so the VIM3 can finish its Android shutdown after ACC drops.", 610, 209)

# ================================================================ 11. USB hub: one link to the VIM3 over the 40-pin header
text("11. USB HUB: VIM3 header USB (pins 3/4) -> Pico, screen touch, spare port", 610, 228, 2)
HUB = add_lib('Interface_USB', 'CH334R')
place(HUB, "U13", "CH334R", 700, 290,
      {"12": "+5V_SYS", "13": "HUB_3V3", "14": "GND", "15": "HUB_XO", "16": "HUB_XI", "9": None,
       "10": "USB_UP_DM", "11": "USB_UP_DP", "7": "PICO_USB_DM", "8": "PICO_USB_DP", "5": "TOUCH_DN", "6": "TOUCH_DP",
       "3": "SDR_DM", "4": "SDR_DP", "1": "HUB2_UP_DM", "2": "HUB2_UP_DP"},
      "Package_SO:QSOP-16_3.9x4.9mm_P0.635mm", "C4154405", "WCH CH334R 4-port USB 2.0 hub, QSOP-16",
      note="pinout checked against WCH CH334 datasheet (CH334R column). Upstream = VIM3 header pins 3/4 (VIM3 hub port 4)")
place(add_lib('Device', 'Crystal'), "Y1", "12MHz", 660, 305, {"1": "HUB_XI", "2": "HUB_XO"}, "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", "",
      "12MHz crystal (pick in library)", note="CH334R has built-in load capacitors")
cap("C61", "1u", 720, 262, "+5V_SYS", "GND", note="at V5")
cap("C62", "10u", 728, 262, "HUB_3V3", "GND")
cap("C63", "100n", 736, 262, "HUB_3V3", "GND")
place(CG2, "J16", "Pico USB pads", 760, 320, {"1": "PICO_USB_DM", "2": "PICO_USB_DP"}, "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "",
      "Solder pads / 1x2 header", note="wire to Pico TP2 (D-) and TP3 (D+), or route directly when the Pico is surface-mounted with a footprint that has TP pads")
place(PF, "F5", "PTC 0.5A", 780, 270, {"1": "+5V_SYS", "2": "SDR_VBUS"}, "Fuse:Fuse_1206_3216Metric", "", "1206 PTC 0.5A hold (pick in library)")
USBA = add_lib('Connector', 'USB_A')
place(USBA, "J17", "RTL-SDR (internal)", 805, 290, {"1": "SDR_VBUS", "2": "SDR_DM", "3": "SDR_DP", "4": "GND", "5": "GND"}, "Connector_USB:USB_A_Molex_67643_Horizontal", "",
      "USB-A receptacle, board mount (pick in library)", note="RTL-SDR dongle for FM/DAB+ plugs in here with its existing USB-A to USB-C cable")
text("One link to the VIM3: no USB cables. Port 1 Pico (HID + GNSS CDC), 2 touch, 3 RTL-SDR, 4 second hub (external ports). Route D+/D- as 90 ohm pairs.", 610, 345)
text("VIM3 header pins 3/4 are a working USB host port (confirmed by Glenn, 2026-09-29).", 610, 349)

# ================================================================ 12. external USB ports (phone) + their own 5V/3A supply
text("12. EXTERNAL USB PORTS (phone etc.): second hub + dedicated 5V/3A supply, 1.5A current-limited per port", 320, 580 - 150, 2)
BUCK = add_lib('Regulator_Switching', 'LMR33630ADDA')
place(BUCK, "U15", "LMR33630ADDA", 360, 470, {"2": "VSYS_IN", "3": "VIM3_PWR_EN", "1": "GND", "9": "GND", "6": "USBP_VCC", "7": "USBP_BOOT", "8": "USBP_SW", "5": "USBP_FB", "4": None},
      "Package_SO:TI_SO-PowerPAD-8_ThermalVias", "C841384", "TI LMR33630ADDAR 36V 3A buck, 400 kHz",
      note="pinout and values from the TI LMR33630 datasheet (5V/3A example). On whenever the VIM3 supply is enabled (GP28)")
cap("C64", "10u50", 330, 460, "VSYS_IN", "GND")
cap("C65", "100n", 338, 460, "VSYS_IN", "GND")
cap("C66", "1u", 342, 490, "USBP_VCC", "GND")
cap("C67", "100n", 380, 455, "USBP_BOOT", "USBP_SW")
place(L, "L4", "8.2uH 5A", 390, 468, {"1": "USBP_SW", "2": "+5V_USB"}, "Inductor_SMD:L_Bourns_SRP7028A_7.3x6.6mm", "", "8.2uH, Isat >= 5A (datasheet uses 8uH; pick in library)")
res("R75", "100k", 400, 468, "+5V_USB", "USBP_FB")
res("R76", "24k", 400, 490, "USBP_FB", "GND", note="Vout = 1.0V x (1 + 100k/24k) = 5.17V")
for i, r in enumerate(["C68", "C69", "C70", "C71"]):
    cap(r, "22u", 410 + 8 * i, 468, "+5V_USB", "GND")
SW2561 = add_lib('Interface_USB', 'TPS2561')
place(SW2561, "U16", "TPS2561DRCR", 480, 470, {"2": "+5V_USB", "3": "+5V_USB", "4": "+5V_USB", "5": "+5V_USB", "1": "GND", "11": "GND",
      "9": "EXT1_VBUS", "8": "EXT2_VBUS", "7": "USBP_ILIM", "10": None, "6": None},
      "Package_SON:VSON-10-1EP_3x3mm_P0.5mm_EP1.65x2.4mm", "C140303", "TI TPS2561DRCR dual 2.8A USB power switch",
      note="current limit 56000/RILIM(k) mA: 39k = 1.44 A per port")
cap("C72", "100n", 458, 485, "+5V_USB", "GND")
res("R77", "39k", 505, 485, "USBP_ILIM", "GND")
cap("C73", "100u", 515, 485, "EXT1_VBUS", "GND")
cap("C74", "100u", 523, 485, "EXT2_VBUS", "GND")
place(HUB, "U14", "CH334R", 560, 480,
      {"12": "+5V_SYS", "13": "HUB2_3V3", "14": "GND", "15": "HUB2_XO", "16": "HUB2_XI", "9": "HUB2_3V3",
       "10": "HUB2_UP_DM", "11": "HUB2_UP_DP", "7": "EXT1_DM", "8": "EXT1_DP", "5": "EXT2_DM", "6": "EXT2_DP", "3": None, "4": None, "1": None, "2": None},
      "Package_SO:QSOP-16_3.9x4.9mm_P0.635mm", "C4154405", "WCH CH334R 4-port USB 2.0 hub, QSOP-16",
      note="cascaded on hub 1 port 4. RESET#/CDP tied high = BC1.2 CDP for faster phone charging (WCH: depends on batch)")
place(add_lib('Device', 'Crystal'), "Y2", "12MHz", 530, 505, {"1": "HUB2_XI", "2": "HUB2_XO"}, "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", "", "12MHz crystal (pick in library)")
cap("C75", "1u", 580, 455, "+5V_SYS", "GND")
cap("C76", "10u", 588, 455, "HUB2_3V3", "GND")
cap("C77", "100n", 596, 455, "HUB2_3V3", "GND")
place(USBA, "J19", "External USB 1", 600, 510, {"1": "EXT1_VBUS", "2": "EXT1_DM", "3": "EXT1_DP", "4": "GND", "5": "GND"}, "Connector_USB:USB_A_Molex_67643_Horizontal", "",
      "USB-A receptacle (pick in library), or a JST lead to a dash-mount USB socket")
place(USBA, "J20", "External USB 2", 600, 540, {"1": "EXT2_VBUS", "2": "EXT2_DM", "3": "EXT2_DP", "4": "GND", "5": "GND"}, "Connector_USB:USB_A_Molex_67643_Horizontal", "",
      "USB-A receptacle (pick in library), or a JST lead to a dash-mount USB socket")

ESD = add_lib('Power_Protection', 'USBLC6-2SC6')
for i, (ref, y) in enumerate((("U17", 510), ("U18", 540)), 1):
    place(ESD, ref, "USBLC6-2SC6", 640, y, {"1": f"EXT{i}_DP", "6": f"EXT{i}_DP", "3": f"EXT{i}_DM", "4": f"EXT{i}_DM", "2": "GND", "5": f"EXT{i}_VBUS"},
          "Package_TO_SOT_SMD:SOT-23-6", "", "ST USBLC6-2SC6 USB ESD protection (pick in library)",
          note="review: ESD for the user-facing USB ports; place right at the connector, pairs route straight through pins 1-6 and 3-4")
text("Ports are powered only while the VIM3 supply is on. All USB shares the VIM3 header's USB 2.0 link (480 Mbit/s); RTL-SDR needs ~40 Mbit/s.", 320, 560)

# ================================================================ power flags
def flag(net, x, y):
    power('PWR_FLAG', x, y, 90)
    label(net, x, y, 270)
    nets.setdefault(net, []).append(("#FLG", "1"))
fx = 330
for net in ["BATT_RAW", "ACC_RAW", "+3V3_PICO", "PICO_VSYS", "VIM3_3V3", "VIM3_5V"]:
    flag(net, fx, 392); fx += 15
power('PWR_FLAG', fx, 392, 90); power('GND', fx, 392, 270)

text("Car radio peripheral board rev 0.2 - MG F (1996), VIM3 + Pico 2, 4ch line out, NEO-M9N. Generated; see DESIGN.md.", 12, 412, 1.5)

# ---------------------------------------------------------------- write
sch = [S('kicad_sch'), [S('version'), 20230121], [S('generator'), S('eeschema')], [S('uuid'), ROOT], [S('paper'), "A1"],
       [S('title_block'), [S('title'), "Car radio peripheral board (Pico 2 + VIM3)"], [S('date'), "2026-09-29"], [S('rev'), "0.2"]],
       [S('lib_symbols')] + list(lib_symbols.values())] + items + \
      [[S('sheet_instances'), [S('path'), "/", [S('page'), "1"]]]]
open(f"{PROJECT}.kicad_sch", "w").write(dump(sch) + "\n")
with open(f"{PROJECT}_bom.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Value", "Description / MPN", "LCSC", "Footprint (KiCad name)", "Fit", "Note"])
    for b in bom:
        w.writerow([b['ref'], b['value'], b['mpn'], b['lcsc'], b['fp'], "DNP" if b['dnp'] else "yes", b['note']])
refs = [b['ref'] for b in bom]
dups = {r for r in refs if refs.count(r) > 1}
bad = {n: v for n, v in nets.items() if len(v) < 2 and n != '(flag)'}
if bad or dups:
    print("SINGLE-PIN NETS:", bad, "DUP REFS:", dups); sys.exit(1)
print("ok", len(bom), "parts", len(nets), "nets")
