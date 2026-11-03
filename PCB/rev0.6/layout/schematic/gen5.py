#!/usr/bin/env python3
"""Generate the car-radio peripheral board schematic (KiCad 7 .kicad_sch) + BOM.

Every connection is made with net labels placed on pin endpoints, so the netlist
is unambiguous and survives import into EasyEDA Pro.
"""
import csv, uuid, copy, sys
from sexp import Sym, parse, dump, find_sym, pins_of

S = Sym
# rev 0.4: one script, two boards. "main" = the peripheral board, "audio" = the plug-in DAC module (J23 <-> J24)
BOARD = sys.argv[1] if len(sys.argv) > 1 else "main"
assert BOARD in ("main", "audio", "usb", "gnss")
PROJECT = {"main": "carradio_peripheral_rev05", "audio": "carradio_audio_rev04", "usb": "carradio_usb_rev04", "gnss": "carradio_gnss_rev04"}[BOARD]
ROOT = str(uuid.uuid5(uuid.NAMESPACE_URL, "carradio-peripheral-rev02-root" if BOARD == "main" else f"carradio-{BOARD}-rev04-root"))
SEC = ["main"]      # which board the items belong to: "main", "audio", "usb", or two joined by "+" (a connector pair)
def mine(tag): return BOARD in tag.split("+")
SECOF = {}          # ref -> section
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

def renumber_pin(lib_id, old, new):
    """Rename a pin number in an embedded symbol so it matches the footprint's pad name."""
    def walk(x):
        for e in x:
            if isinstance(e, list) and e:
                if e[0] == 'pin':
                    for q in e:
                        if isinstance(q, list) and q and q[0] == 'number' and q[1] == old:
                            q[1] = new
                elif e[0] == 'symbol':
                    walk(e)
    walk(lib_symbols[lib_id])
    pin_table[lib_id] = pins_of(lib_symbols[lib_id])

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
class TagList(list):
    def __init__(self): super().__init__(); self.tags = []
    def append(self, x): super().append(x); self.tags.append(SEC[0])
items = TagList()
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
    SECOF[ref] = SEC[0]
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
    SECOF[ref] = SEC[0]
    bom.append(dict(ref=ref, value=value, fp=fp, lcsc=lcsc, mpn=mpn, dnp=dnp, note=note, sec=SEC[0]))

PICK.update({'U20': ('C42415655', 'Raspberry Pi RP2350B QFN-80 (LCSC stock unclear; alt RP2354B C39843328 with 2MB internal flash, then leave U21 unfitted)'), 'U21': ('C97521', 'Winbond W25Q128JVSIQ'), 'U19': ('C51118', 'Diodes AP2112K-3.3TRG1'), 'L5': ('C42411119', 'Abracon AOTA-B201610S3R3-101-T 3.3uH (Raspberry Pi reference part)'), 'Y3': ('C20625731', 'Abracon ABM8-272-T3 12MHz (Raspberry Pi reference part)'), 'C99': ('C1644', 'Samsung CL10C150JB8NNNC 15pF C0G'), 'C100': ('C1644', 'Samsung CL10C150JB8NNNC 15pF C0G'), 'R83': ('C25190', 'UNI-ROYAL 0603WAF270JT5E 27R'), 'R84': ('C25190', 'UNI-ROYAL 0603WAF270JT5E 27R'), 'SW1': ('C2886898', 'E-Switch TL3342F160QG', 'Button_Switch_SMD:SW_SPST_TL3342'), 'SW2': ('C2886898', 'E-Switch TL3342F160QG', 'Button_Switch_SMD:SW_SPST_TL3342'), 'TH1': ('C13564', 'Murata NCP18XH103F03RB 10k B3380 0603'), 'J22': ('C124378', '1x4 male header 2.54mm'), 'J21': ('C57369', 'BOOMELE 1x10 male header 2.54mm'), 'D16': ('C2297', 'KT-0805G green LED')})
PICK.update({'J1': ('C277661', 'Molex 43045-0812'), 'J8': ('C234188', 'Molex 43045-0612'), 'J3': ('C124410', 'Ckmtw B-2200S20P-A120 1x20 female 2.54mm'), 'J4': ('C124410', 'Ckmtw B-2200S20P-A120 1x20 female 2.54mm'), 'JP1': ('C124375', '1x2 male header 2.54mm + jumper cap C5305'), 'J16': ('C124375', '1x2 male header 2.54mm (or solder wires)'), 'J10': ('C124381', 'Ckmtw B-2100S08P-A110 1x8 male header'), 'J2': ('C9138', 'BOOMELE 2.54-2*20P box header (check it is shrouded)'), 'J5': ('C131337', 'JST B2B-PH-K-S'), 'J7': ('C131334', 'JST B4B-PH-K-S'), 'J12': ('C157993', 'JST B5B-PH-K-S'), 'J18': ('C158012', 'JST B2B-XH-A'), 'J11': ('C88374', 'Hirose U.FL-R-SMT-1(80) U.FL receptacle; antenna via U.FL-to-SMA pigtail'), 'J13': ('C427307', 'Amphenol 10029449-111RLF (plating variant of -001RLF; confirm land pattern)'), 'J14': ('C2856837', 'XUNPU FPC-05FB-40PH20, 40P 0.5mm dual-contact flip-top 2.0mm (use the LCSC footprint, not FH12)'), 'J17': ('C2798029', 'Molex 67643-0910 USB-A'), 'J19': ('C2798029', 'Molex 67643-0910 USB-A'), 'J20': ('C2798029', 'Molex 67643-0910 USB-A'), 'F4': ('C206907', 'Littelfuse 01530008Z mini blade holder (use the LCSC footprint) + fuse C178942 Littelfuse 029707.5WXNV 7.5A', ''), 'F1': ('C883126', 'BHFUSE BSMD1206-050-30V'), 'F3': ('C883126', 'BHFUSE BSMD1206-050-30V'), 'F2': ('C151170', 'Littelfuse 1812L075/33DR'), 'F5': ('C75464', 'Bourns MF-NSMF050-2'), 'D2': ('C151920', 'SMBJ22A (BORN); alt DOWO C284010'), 'D5': ('C151920', 'SMBJ22A (BORN); alt DOWO C284010'), 'D13': ('C151920', 'SMBJ22A (BORN); alt DOWO C284010'), 'D14': ('C2990362', 'Liown 5.0SMDJ22A, 5 kW SMC'), 'Q2': ('C400792', 'onsemi FDN5618P -60V P-MOSFET (check 1=G 2=S 3=D in datasheet)'), 'Q3': ('C8545', 'JSCJ 2N7002'), 'Q10': ('C130101', 'NCE40P70K -40V 10 mOhm P-MOSFET TO-252 (alt Diodes DMP4015SK3-13 C513222)'), 'C48': ('C178548', 'Panasonic EEEFK1H101P 100uF 50V 8x10.2'), 'C60': ('C881921', 'Lelon OVZ221M1CTR-0608 polymer 220uF 16V'), 'L2': ('C12669', 'Murata LQG15HS27NJ02D'), 'L3': ('C780205', 'Bourns SRP1265A-4R7M 4.7uH Isat 28A 8.4 mOhm, 13.5x12.5mm (SRP1245A land pattern)', 'Inductor_SMD:L_Bourns_SRP1245A'), 'L4': ('C19191627', 'Coilcraft XAL6060-822MEC 8.2uH Isat 8.4A 24 mOhm (expensive; any 8.2-10uH shielded, Isat >= 5A works)', 'Inductor_SMD:L_Coilcraft_XAL6060-XXX'), 'R69': ('C22984', 'UNI-ROYAL 0603WAF3002T5E'), 'R74': ('C375691', 'Yageo PA2512FKE7T0R01E 10 mOhm 1% 3W'), 'D10': ('C2297', 'KT-0805G green LED'), 'Y1': ('C9002', 'YXC X322512MSB4SI 12MHz'), 'Y2': ('C9002', 'YXC X322512MSB4SI 12MHz'), 'U17': ('C7519', 'ST USBLC6-2SC6'), 'U18': ('C7519', 'ST USBLC6-2SC6')})
PICK.update({'U12': ('C2864583', 'TI TPS55288RPMR', 'carradio:TPS55288RPMR_VQFN-HR-26'), 'F4': ('C206907', 'Littelfuse 01530008Z mini blade holder + fuse C178942 Littelfuse 029707.5WXNV 7.5A', 'carradio:Littelfuse_01530008Z'), 'J14': ('C2856837', 'XUNPU FPC-05FB-40PH20, 40P 0.5mm dual-contact flip-top 2.0mm (pads numbered by panel pin: pin 1 on the right, ribbon leaving the edge)', 'carradio:XUNPU_FPC-05FB-40PH20')})
SWAP.update({'C13585': ('C77092', 'Murata GRM31CR61H106KA12L'), 'C106900': ('C470884', 'EL817S1(C)(TU)-FV'), 'C80670': ('C5370990', 'TECH PUBLIC TPLP5907MFX-3.3 clone; TI part out of stock at LCSC'), 'C15849': ('C77386', 'Murata GRM188R61H105KAALD'), 'C57112': ('C1589', 'Samsung CL10B103KB8NNNC'), 'C25819': ('C105579', 'YAGEO RC0603FR-0747KL')})

# ================================================================ rev 0.3 body
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
       "24k": "C23352", "100k": "C25803", "39k": "C23153", "22k": "C31850", "8.2k": "C25981", "27": "", "20k": "C4184", "30k": "", "47k": "C25819", "220k": "C22961", "1M": "C22935", "0": "C21189"}
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

text("Always-on 5.2V: MCU VSYS + GNSS LDO. TPS560430X runs PFM at light load (~55uA Iq).", 105, 105)
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
    place(OPTO, uref, "EL817S1(C)", ox + 32, oy, {"1": led, "2": "GND", "4": "+3V3_MCU", "3": pico}, FP_OPTO, "C106900", "EL817S1(C)(TU)-F")
    res(rpd, "4.7k", ox + 52, oy + 4, pico, "GND")
    cap(cpd, "100n", ox + 60, oy + 4, pico, "GND")
    text(n, ox - 4, oy - 22, 1.5)
opto_in("ACC (ISO A7)", 225, 45, "ACC_P", "ACC_LED", "MCU_ACC_IN", "R3", "D6", "U2", "R4", "C6", "")
opto_in("ILLUM (ISO A6)", 315, 45, "ILLUM_RAW", "ILLUM_LED", "MCU_ILLUM_IN", "R5", "D7", "U3", "R6", "C7", "")
opto_in("REVERSE lamp (ISO A1)", 225, 105, "REV_RAW", "REV_LED", "MCU_REV_IN", "R29", "D11", "U4", "R30", "C10", "")
# park brake: the MG F handbrake switch grounds the warning lamp, so the LED is fed from ACC and the switch sinks it
res0805("R31", 315, 99, "ACC_P", "PARK_LED", note="PARK input: LED fed from ACC, handbrake switch pulls cathode to ground")
place(OPTO, "U5", "EL817S1(C)", 347, 105, {"1": "PARK_LED", "2": "PARK_K", "4": "+3V3_MCU", "3": "MCU_PARK_IN"}, FP_OPTO, "C106900", "EL817S1(C)(TU)-F")
place(D4148, "D12", "1N4148W", 323, 119, {"1": "PARK_RAW", "2": "PARK_K"}, FP_SOD123, "C81598", "1N4148W", note="series diode: blocks reverse voltage when ACC is off")
res("R32", "4.7k", 367, 109, "MCU_PARK_IN", "GND")
cap("C11", "100n", 375, 109, "MCU_PARK_IN", "GND")
text("PARK (ISO A2, handbrake switch; may stay unwired)", 311, 83, 1.5)
cap("C8", "100n", 395, 60, "+3V3_MCU", "GND")
res("R57", "0", 545, 100, "AMP_REM", "ISO_A5", dnp=True, note="DNP: fit to also put the amp remote on ISO A5 (the usual antenna/amp remote pin)")
text("LED ~2.7mA at 14.4V; EL817 C-grade CTR >= 200%. 4.7k pull-downs satisfy RP2350-E9.", 215, 140)

# ================================================================ 3. amp remote
text("3. AMPLIFIER REMOTE (+12V from ACC, MCU GP20)", 425, 16, 2)
place(PMOS, "Q2", "P-MOSFET -60V", 470, 45, {"S": "ACC_P", "D": "AMP_SW", "G": "AMP_G"}, FP_SOT23, "", "P-MOSFET SOT-23, -60V, Vgs +-20V, >= 1A, Rds(on) < 0.3 ohm at -10V (pick in library)",
      note="review: AO3401A (-30V) was below the 35.5V TVS clamp")
res("R13", "10k", 440, 34, "ACC_P", "AMP_G")
place(DZ, "D8", "BZT52C12", 448, 55, {"1": "ACC_P", "2": "AMP_G"}, FP_SOD123, "C124196", "BZT52C12-7-F 12V zener", note="Vgs clamp")
res("R14", "10k", 440, 72, "AMP_G", "AMP_PULL")
place(NMOS, "Q3", "2N7002", 470, 95, {"D": "AMP_PULL", "S": "GND", "G": "AMP_CTRL"}, FP_SOT23, "", "2N7002 60V N-MOSFET, SOT-23 G-S-D (pick in library)",
      note="review: drain sees ACC through R13, so it needs more than 30V")
res("R16", "100", 445, 102, "MCU_AMP_EN", "AMP_CTRL")
res("R15", "100k", 455, 118, "AMP_CTRL", "GND", note="amp off while the MCU is in reset")
place(PF, "F3", "PTC 0.5A hold 30V", 495, 45, {"1": "AMP_SW", "2": "AMP_REM"}, "Fuse:Fuse_1206_3216Metric", "", "1206 PTC 0.5A hold 30V (pick in library)",
      note="own fuse: a shorted remote wire cannot pull down ACC")
place(DS, "D9", "SS34", 520, 60, {"1": "AMP_REM", "2": "GND"}, FP_SMA, "C8678", "SS34 40V 3A Schottky", note="clamps inductive kick from the remote wire")
tvs("D13", 520, 72, "AMP_REM")
res("R18", "4.7k", 545, 45, "AMP_REM", "AMP_LED")
place(LED, "D10", "LED green", 555, 65, {"2": "AMP_LED", "1": "GND"}, "LED_SMD:LED_0805_2012Metric", "", "0805 green LED (pick in library)", note="amp remote on")
text("Goes to ISO A3 and C1-6 (A5 via R57). ~1A capable; remote inputs draw <100mA.", 425, 135)
text("Only works while ACC is on, even if the MCU hangs.", 425, 139)

# ================================================================ 4. MCU
text("4. MCU HELPERS (MCU core is section 13)", 12, 158, 2)
text("GPIO map: see section 13 and DESIGN_rev03.md.", 12, 240)
res("R7", "1k", 130, 180, "VIM3_3V3", "MCU_SBC_SENSE", note="VIM3 on/off sense")
res("R8", "4.7k", 138, 180, "MCU_SBC_SENSE", "GND")
res("R10", "1M", 146, 180, "VBAT_P", "MCU_VBAT_ADC", note="battery sense: 14.4V -> 2.6V")
res("R11", "220k", 154, 180, "MCU_VBAT_ADC", "GND")
cap("C9", "100n", 162, 180, "MCU_VBAT_ADC", "GND")
place(CG2, "JP1", "SERVICE jumper", 135, 215, {"1": "+3V3_MCU", "2": "MCU_SERVICE"}, "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "", "1x2 2.54mm pin header + jumper")
res("R9", "4.7k", 150, 218, "MCU_SERVICE", "GND")
place(CG8, "J10", "Expansion", 185, 205, {"1": "+3V3_MCU", "2": "EXP_GP32", "3": "EXP_GP33", "4": "EXP_GP28", "5": "+5V_AON", "6": "GND", "7": "GND", "8": None},   # rev 0.5: GPIO13 no longer broken out
      "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical", "", "1x8 2.54mm pin header",
      note="pins 2/3 = GP32/GP33 UART TX/RX for a future K-line (L9637D) board; pins 4/8 = spare GP28/GP13")

# ================================================================ 5. GNSS
SEC[0] = "main"
text("5. GNSS MODULE: u-blox NEO-M9N, active antenna on U.FL (pigtail to SMA), UART + USB to the main board. Switched 3.3V supply stays on the main board.", 215, 158, 2)
place(LDO, "U6", "LP5907MFX-3.3", 240, 190, {"1": "+5V_AON", "3": "MCU_GNSS_EN", "2": "GND", "5": "+3V3_GNSS"}, FP_SOT23.replace("SOT-23", "SOT-23-5"),
      "C80670", "TI LP5907MFX-3.3/NOPB 250mA LDO", note="GNSS supply, switched by MCU GP9")
cap("C12", "1u", 222, 205, "+5V_AON", "GND")
res("R35", "100k", 230, 205, "MCU_GNSS_EN", "GND", note="GNSS off by default")
cap("C13", "1u", 255, 205, "+3V3_GNSS", "GND")
SEC[0] = "gnss"
cap("C14", "10u", 263, 205, "+3V3_GNSS", "GND")
cap("C15", "100n", 271, 205, "+3V3_GNSS", "GND")
cap("C16", "100n", 279, 205, "+3V3_MCU", "GND", note="at V_BCKP")
place(GNSS, "U7", "NEO-M9N-00B", 330, 205,
      {"23": "+3V3_GNSS", "22": "+3V3_MCU", "7": "+3V3_GNSS", "9": "GNSS_VCCRF", "10": "GND", "12": "GND", "13": "GND", "24": "GND",
       "11": "GNSS_RF", "20": "GNSS_TXD", "21": "GNSS_RXD", "8": "GNSS_RST", "3": "GNSS_PPS", "1": "GNSS_SAFEBOOT",
       "5": "GNSS_USB_DM_M", "6": "GNSS_USB_DP_M"},
      "RF_GPS:ublox_NEO", "C5119087", "u-blox NEO-M9N-00B",
      note="V_BCKP from the main board's always-on 3V3 for hot starts. USB enumerates as CDC-ACM (/dev/ttyACM*, VID 1546). SAFEBOOT_N driven by MCU GPIO29 through R79 (recovery only).")
res("R102", "27", 300, 235, "GNSS_USB_DP_M", "GNSS_USB_DP", note="USB series resistor per the u-blox integration manual reference design")
res("R103", "27", 308, 235, "GNSS_USB_DM_M", "GNSS_USB_DM")
SEC[0] = "main"
res("R37", "1k", 262, 235, "MCU_GNSS_TX", "GNSS_RXD_MCU")
res("R38", "1k", 270, 235, "GNSS_TXD", "MCU_GNSS_RX")
res("R39", "1k", 278, 235, "MCU_GNSS_RST", "GNSS_RST", note="firmware drives low only to reset")
res("R40", "1k", 286, 235, "GNSS_PPS", "MCU_GNSS_PPS")
res("R100", "1k", 262, 255, "GNSS_TXD", "VIM3_UARTC_RX", note="GNSS NMEA also to VIM3 UART_C (header pin 15) for the existing GNSS HAL / kernel gnss driver")
res("R101", "1k", 270, 255, "VIM3_UARTC_TX", "GNSS_RXD_VIM", note="VIM3 UART_C TX (header pin 16)")
place(add_lib('Jumper', 'SolderJumper_3_Bridged12'), "JP2", "GNSS RX source", 290, 255, {"1": "GNSS_RXD_VIM", "2": "GNSS_RXD", "3": "GNSS_RXD_MCU"},
      "Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm", "", "3-pad solder jumper (PCB copper, no part)",
      note="who talks to the receiver: 1-2 (default, bridged) = VIM3 UART_C, 2-3 = MCU UART1 (GPIO4/5). GNSS TX always goes to both.")
SEC[0] = "gnss"
cap("C17", "10n", 360, 170, "GNSS_VCCRF", "GND")
res("R41", "10", 368, 170, "GNSS_VCCRF", "ANT_FEED", note="antenna supply, limits short-circuit current")
place(L, "L2", "27nH RF", 376, 170, {"1": "ANT_FEED", "2": "GNSS_RF"}, "Inductor_SMD:L_0402_1005Metric", "", "27nH 0402 RF inductor, e.g. Murata LQG15HS27NJ02 (pick in library)",
      note="RF choke: feeds DC to the antenna, blocks GNSS signal")
place(COAX, "J11", "U.FL GNSS antenna", 385, 205, {"1": "GNSS_RF", "2": "GND"}, "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", "C88374",
      "Hirose U.FL-R-SMT-1(80) U.FL receptacle", note="U.FL to SMA pigtail to the antenna; 50 ohm coplanar trace to RF_IN, as short as possible")
text("Active antenna (3.3V): VCC_RF -> 10R -> 27nH onto RF_IN. RF_IN is DC-blocked inside the module (verify in the integration manual).", 215, 250)
# ---- GNSS module connector: 2x8 2.54 mm. Main board J27 = socket, module J28 = pin header (same pin map).
SEC[0] = "main+gnss"
GNSS_HDR = {"1": "+3V3_GNSS", "2": "+3V3_GNSS", "3": "GND", "4": "+3V3_MCU", "5": None, "6": "GND",
            "7": "GNSS_USB_DP", "8": "GNSS_TXD", "9": "GNSS_USB_DM", "10": "GNSS_RXD", "11": "GND", "12": "GND",
            "13": "GNSS_RST", "14": "GNSS_PPS", "15": "GNSS_SAFEBOOT", "16": "GND"}
_M2x10 = add_lib('Connector_Generic', 'Conn_02x08_Odd_Even')
if BOARD == "main":
    place(_M2x10, "J27", "GNSS module socket", 300, 280, GNSS_HDR, "Connector_PinSocket_2.54mm:PinSocket_2x08_P2.54mm_Vertical", "",
          "2x8 2.54mm female socket, 8.5mm body (same family as J23/J25)",
          note="GNSS module plugs in here: switched 3V3 (U6), backup 3V3, UART, USB, reset, PPS, safeboot")
elif BOARD == "gnss":
    place(_M2x10, "J28", "Main board plug", 300, 280, GNSS_HDR, "Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical", "",
          "2x8 2.54mm male pin header", note="mates with J27 on the main board; fit on the bottom side")
SEC[0] = "gnss"
for i, nmf in enumerate(["+3V3_GNSS", "+3V3_MCU"]):
    power('PWR_FLAG', 330 + 15 * i, 280, 90); label(nmf, 330 + 15 * i, 280, 270); nets.setdefault(nmf, []).append((f"#FLGG{i}", "1")); SECOF[f"#FLGG{i}"] = "gnss"
power('PWR_FLAG', 360, 280, 90); power('GND', 360, 280, 270)
text("Car radio GNSS module rev 0.4 - NEO-M9N with SMA antenna jack; plugs onto the peripheral board (J28 -> J27). Generated by gen4.py gnss.", 12, 416, 1.5)
SEC[0] = "main"

# ================================================================ 6. MCU peripherals: power key, backlight, lux
text("6. VIM3 POWER KEY, BACKLIGHT, LIGHT SENSOR (all from the MCU)", 425, 158, 2)
place(NMOS, "Q1", "AO3400A", 450, 185, {"D": "VIM3_PWR_KEY", "S": "GND", "G": "PWR_KEY_G"}, FP_SOT23, "C20917", "AO3400A 30V 5.7A N-MOSFET",
      note="open-drain press of the active-low VIM3 POWER key (GPIOAO_7)")
res("R12", "100", 430, 185, "MCU_PWR_KEY", "PWR_KEY_G")
res("R19", "100k", 438, 200, "PWR_KEY_G", "GND")
place(CG2, "J5", "VIM3 POWER key lead", 475, 185, {"1": "VIM3_PWR_KEY", "2": "GND"}, "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", "",
      "JST-PH 2P (pick in library)", note="wire to the VIM3 power-key pad")
res("R23", "100", 500, 180, "MCU_BL_EN", "BL_EN")
res("R24", "100", 508, 180, "MCU_BL_PWM", "BL_PWM")
res("R33", "4.7k", 500, 225, "+3V3_MCU", "LUX_SCL")
res("R34", "4.7k", 508, 225, "+3V3_MCU", "LUX_SDA")
place(CG4, "J7", "BH1750 light sensor", 530, 225, {"1": "+3V3_MCU", "2": "GND", "3": "LUX_SCL", "4": "LUX_SDA"}, "Connector_JST:JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical", "", "JST-PH 4P (pick in library)")
text("Backlight and reverse moved off the VIM3 header; the VHAL now sets/reads them through the MCU.", 425, 262)
# display buttons: switch to ground, pull-up + series R + RC filter at the MCU
BTNS = [("SCREEN", "R58", "R59", "C42"), ("VOLUP", "R60", "R61", "C43"), ("VOLDN", "R62", "R63", "C44"), ("MUTE", "R64", "R65", "C45")]
bx = 425
for nm, rpu, rser, cf in BTNS:
    res(rpu, "10k", bx, 232, "+3V3_MCU", f"MCU_BTN_{nm}")
    res(rser, "1k", bx + 6, 232, f"BTN_{nm}", f"MCU_BTN_{nm}")
    cap(cf, "100n", bx + 12, 232, f"MCU_BTN_{nm}", "GND")
    bx += 18
place(add_lib('Connector_Generic', 'Conn_01x05'), "J12", "Display buttons", 568, 195,
      {"1": "BTN_SCREEN", "2": "BTN_VOLUP", "3": "BTN_VOLDN", "4": "BTN_MUTE", "5": "GND"},
      "Connector_JST:JST_PH_B5B-PH-K_1x05_P2.00mm_Vertical", "", "JST-PH 5P (pick in library)",
      note="momentary buttons to ground: 1 screen off, 2 volume up, 3 volume down, 4 mute, 5 GND")
text("Display buttons (to GND): GP18 screen, GP17 vol+, GP22 vol-, GP16 mute. J12.", 425, 257)

# ================================================================ 7. audio (rev 0.4: on the plug-in audio module)
SEC[0] = "audio"
text("AUDIO MODULE: I2S from J24 -> 2x PCM5102A (front + rear) -> line out back through J24 to ISO C1 on the main board", 12, 268, 2)
place(LDO, "U8", "LP5907MFX-3.3", 40, 300, {"1": "VIM3_5V", "3": "VIM3_5V", "2": "GND", "5": "+3V3_DAC_A"}, "Package_TO_SOT_SMD:SOT-23-5",
      "C80670", "TI LP5907MFX-3.3/NOPB 250mA LDO", note="DAC analog supply (AVDD + CPVDD)")
cap("C18", "1u", 22, 318, "VIM3_5V", "GND")
cap("C19", "1u", 58, 318, "+3V3_DAC_A", "GND")
place(LDO, "U9", "LP5907MFX-3.3", 40, 345, {"1": "VIM3_5V", "3": "VIM3_5V", "2": "GND", "5": "+3V3_DAC_D"}, "Package_TO_SOT_SMD:SOT-23-5",
      "C80670", "TI LP5907MFX-3.3/NOPB 250mA LDO", note="DAC digital supply (DVDD)")
cap("C20", "1u", 22, 363, "VIM3_5V", "GND")
cap("C21", "1u", 58, 363, "+3V3_DAC_D", "GND")
SEC[0] = "main"
res("R42", "33", 85, 385, "VIM3_I2S_BCLK", "I2S_BCLK")
res("R43", "33", 93, 385, "VIM3_I2S_LRCK", "I2S_LRCK")
res("R44", "33", 101, 385, "VIM3_I2S_DOUT0", "I2S_DOUT0")
res("R45", "33", 109, 385, "VIM3_I2S_DOUT1", "I2S_DOUT1")
res("R46", "1k", 125, 385, "MCU_DAC_MUTE", "DAC_XSMT", note="limits back-feed when the VIM3 (DAC supply) is off")
res("R47", "10k", 133, 385, "DAC_XSMT", "GND", note="DACs muted unless the MCU unmutes")
text("I2S series resistors at the ribbon entry.", 80, 405)
SEC[0] = "audio"

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

# ---- module connector: 2x10 2.54 mm. Main board J23 = socket, module J24 = pin header (same pin map).
# Spare lines for other modules: TDM-B MCLK (VIM3 pin 30), TDM-B lane 3 (VIM3 pin 35) and the MCU I2C bus.
SEC[0] = "main+audio"
M2x10 = add_lib('Connector_Generic', 'Conn_02x10_Odd_Even')
AUDIO_HDR = {"1": "VIM3_5V", "2": "VIM3_5V", "3": "GND", "4": "GND", "5": "I2S_BCLK", "6": "GND", "7": "I2S_LRCK", "8": "VIM3_I2S_MCLK",
             "9": "I2S_DOUT0", "10": "I2S_DOUT1", "11": "VIM3_I2S_DOUT2", "12": "DAC_XSMT", "13": "LUX_SCL", "14": "LUX_SDA",
             "15": "GND", "16": "GND", "17": "LINE_FL", "18": "LINE_FR", "19": "LINE_RL", "20": "LINE_RR"}
if BOARD == "main":
    place(M2x10, "J23", "Audio module socket", 470, 395, AUDIO_HDR, "Connector_PinSocket_2.54mm:PinSocket_2x10_P2.54mm_Vertical", "C30867",
          "BOOMELE 2.54-2*10P female 8.5mm (LCSC out of stock 2026-10-01; any 2x10 2.54mm 8.5mm socket fits)",
          note="audio module plugs in here; 5V, I2S, DAC mute, MCU I2C and the four line outs")
else:
    place(M2x10, "J24", "Main board plug", 470, 395, AUDIO_HDR, "Connector_PinHeader_2.54mm:PinHeader_2x10_P2.54mm_Vertical", "C5116480",
          "ZHOURI 2.54-2*10 male pin header", note="mates with J23 on the main board; fit on the bottom side")
SEC[0] = "audio"
power('PWR_FLAG', 520, 392, 90); label("VIM3_5V", 520, 392, 270); nets.setdefault("VIM3_5V", []).append(("#FLGA", "1")); SECOF["#FLGA"] = "audio"
power('PWR_FLAG', 535, 392, 90); power('GND', 535, 392, 270)
text("Car radio audio module rev 0.4 - plugs onto the peripheral board (J24 -> J23). Generated by gen4.py audio.", 12, 412, 1.5)
SEC[0] = "main"
# ================================================================ 8. VIM3 header + ISO C1
text("8. VIM3 40-PIN HEADER + ISO 10487 C1 (line out)", 425, 268, 2)
vim3_sig = {1: "5V", 2: "5V", 3: "USB_DM", 4: "USB_DP", 5: "GND", 6: "VCC_MCU", 7: "MCU_NRST", 8: "MCU_SWIM", 9: "GND", 10: "ADC_CH0",
            11: "1V8", 12: "ADC_CH3", 13: "SPDIF_OUT", 14: "GND", 15: "UARTC_RX", 16: "UARTC_TX", 17: "GND", 18: "Linux_RX", 19: "Linux_TX", 20: "3V3",
            21: "GND", 22: "I2C_M3_SCL", 23: "I2C_M3_SDA", 24: "GND", 25: "I2C_AO_SCK", 26: "I2C_AO_SDA", 27: "3V3", 28: "GND", 29: "TDMB_SCLK",
            30: "TDMB_MCLK", 31: "TDMB_DOUT0", 32: "TDMB_FS", 33: "TDMB_DOUT1", 34: "GND", 35: "TDMB_DOUT3", 36: "RTC_CLK", 37: "GPIOH_4", 38: "MCU_PA1",
            39: "GPIODZ_15", 40: "GND"}
vim3_net = {1: "VIM3_5V", 2: "VIM3_5V", 3: "USB_UP_DM", 4: "USB_UP_DP", 5: "GND", 9: "GND", 14: "GND", 17: "GND", 21: "GND", 24: "GND", 28: "GND", 34: "GND", 40: "GND",
            20: "VIM3_3V3", 27: "VIM3_3V3", 15: "VIM3_UARTC_RX", 16: "VIM3_UARTC_TX", 30: "VIM3_I2S_MCLK", 35: "VIM3_I2S_DOUT2", 29: "VIM3_I2S_BCLK", 31: "VIM3_I2S_DOUT0", 32: "VIM3_I2S_LRCK", 33: "VIM3_I2S_DOUT1"}
def pad(v): return 2 * v - 1 if v <= 20 else 2 * (v - 20)
VH = box_symbol("VIM3_40pin_IDC", [(pad(v), f"V{v}:{vim3_sig[v]}") for v in range(1, 21)],
                [(pad(v), f"V{v}:{vim3_sig[v]}") for v in range(21, 41)], width=30.48, ref="J", value="VIM3 40-pin (2x20 IDC)")
place(VH, "J2", "VIM3 40-pin via 2x20 IDC ribbon", 470, 330, {str(pad(v)): vim3_net.get(v) for v in range(1, 41)},
      "Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical", "", "2x20 2.54mm shrouded box header (pick in library)",
      note="pin names are VIM3 numbers (Vn); pad numbers are IDC odd/even")
text("VIM3 pin v -> IDC pad 2v-1 (v<=20) or 2(v-20) (v>20). Pin 1 sits opposite pin 21 (confirmed by Glenn).", 425, 372)
text("Pins 30 (TDM-B MCLK) and 35 (TDM-B lane 3) go straight to the audio module socket J23 as spares.", 425, 376)
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
      "Connector_Video:HDMI_A_Amphenol_10029449-x01xLF_Horizontal", "", "HDMI type A receptacle (pick in library)",
      note="short HDMI cable from the VIM3. Route TMDS pairs as 100 ohm differential, length-matched")
FPC = add_lib('Connector_Generic_MountingPin', 'Conn_01x40_MountingPin')
fpc = {4: "+5V_SYS", 5: "+5V_SYS", 6: "+5V_SYS", 11: "HDMI_D2P", 13: "HDMI_D2N", 14: "HDMI_D1P", 16: "HDMI_D1N", 17: "HDMI_D0P", 19: "HDMI_D0N",
       20: "HDMI_CLKP", 22: "HDMI_CLKN", 23: "HDMI_CEC", 24: "HDMI_SCL", 25: "HDMI_SDA", 27: "HDMI_5V", 28: "HDMI_HPD",
       33: "TOUCH_DP", 34: "TOUCH_DN", 36: "BL_PWM", 37: "BL_EN"}
for g in (8, 9, 10, 12, 15, 18, 21, 26, 35): fpc[g] = "GND"
place(FPC, "J14", "Display FPC 40P 0.5mm", 200, 490, {**{str(i): fpc.get(i) for i in range(1, 41)}, "MP": "GND"},
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
      {"3": "VSYS_IN", "4": "VIM3_PWR_EN", "5": "LUX_SCL", "6": "LUX_SDA", "15": "BB_MODE", "7": "BB_AGND", "8": "BB_FSW", "17": "BB_ILIM", "16": "BB_CDC",
       "18": "BB_COMP", "14": None, "10": "BB_AGND", "9": "GND", "24": "GND",
       "2": "BB_DR1H", "22": "BB_BOOT1", "23": "BB_SW1", "1": "BB_DR1L", "21": "BB_SW2", "25": "BB_SW2", "20": "BB_BOOT2",
       "11": "BB_VOUT", "26": "BB_VOUT", "12": "BB_ISP", "13": "BB_ISN", "19": "BB_VCC"},
      "", "C2864583", "TI TPS55288RPMR 36V buck-boost, I2C (footprint: use the EasyEDA library part)",
      note="pinout from TI datasheet SLVSF01B Table 5-1. Powers up with output off: the MCU enables it over I2C (address 0x74, OE bit) after EN goes high. Default 5.0V")
res("R67", "0", 700, 150, "BB_MODE", "BB_AGND", note="MODE = 0 ohm: internal VCC, I2C 0x74, forced PWM")
res("R68", "47k", 707, 150, "BB_FSW", "BB_AGND", note="fsw = 1000/(0.05 x 47000 + 20) = 422 kHz")
res("R69", "30k", 714, 150, "BB_ILIM", "BB_AGND", note="average inductor current limit = 330000/R = 11 A (max ~12.7 A), below L3 saturation; still covers 25 W out at 3 V in")
res("R70", "100k", 721, 150, "BB_CDC", "BB_AGND")
res("R71", "8.2k", 690, 175, "BB_COMP", "BB_COMP_RC", note="compensation calculated for fc ~2.5-4 kHz, Cout ~60uF effective; check on the bench")
cap("C54", "4n7", 690, 190, "BB_COMP_RC", "BB_AGND")
cap("C55", "22p", 698, 182, "BB_COMP", "BB_AGND")
res("R72", "100k", 682, 175, "VIM3_PWR_EN", "GND", note="VIM3 supply off unless the MCU enables it")
res("R73", "1k", 674, 175, "MCU_VIM3_PWR_EN", "VIM3_PWR_EN")
NFET = add_lib('Transistor_FET', 'CSD18543Q3A')
place(NFET, "Q11", "CSD18543Q3A", 772, 60, {"5": "VSYS_IN", "1": "BB_SW1", "2": "BB_SW1", "3": "BB_SW1", "4": "BB_DR1H_G"}, "Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET",
      "C840100", "TI CSD18543Q3A 60V 8.5mOhm N-MOSFET", note="buck-side high-side switch")
place(NFET, "Q12", "CSD18543Q3A", 772, 90, {"5": "BB_SW1", "1": "GND", "2": "GND", "3": "GND", "4": "BB_DR1L_G"}, "Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET",
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
# Layout review 2026-10-01 (TI SLVAER0C): Kelvin sense lines and a separate analog ground, each joined by a net tie
NT = add_lib('Device', 'NetTie_2')
for ref, a, b, x, why in [("NT1", "BB_ISP", "BB_VOUT", 826, "ISP Kelvin tap: place on R74 pad 1"),
                          ("NT2", "BB_ISN", "+5V_SYS", 834, "ISN Kelvin tap: place on R74 pad 2"),
                          ("NT3", "BB_AGND", "GND", 778, "AGND joins PGND at one point: place at C53's GND pad")]:
    place(NT, ref, "NetTie", x, 160 if ref != "NT3" else 160, {"1": a, "2": b}, "NetTie:NetTie-2_SMD_Pad0.5mm", "", "net tie (copper only, not a part)", note=why)
    bom.pop()
    sym = next(e for e in reversed(items) if e[0] == 'symbol' and e[1] == [S('lib_id'), NT])
    sym[4] = [S('in_bom'), S('no')]
text("Input 3V-36V (runs through cranking); output 5.0V up to 5A. MCU GP23 = EN, MCU I2C1 sets OE/voltage/current limit.", 610, 205)
text("VIN is permanent +12V so the VIM3 can finish its Android shutdown after ACC drops.", 610, 209)

# ================================================================ 11. USB hub: one link to the VIM3 over the 40-pin header
text("11. USB HUB: VIM3 header USB (pins 3/4) -> MCU, screen touch, spare port", 610, 228, 2)
HUB = add_lib('Interface_USB', 'CH334R')
place(HUB, "U13", "CH334R", 700, 290,
      {"12": "+5V_AON", "13": "HUB_3V3", "14": "GND", "15": "HUB_XO", "16": "HUB_XI", "9": "HUB1_RST",
       "10": "USB_UP_DM", "11": "USB_UP_DP", "7": "MCU_USB_DM", "8": "MCU_USB_DP", "5": "TOUCH_DN", "6": "TOUCH_DP",
       "3": "GNSS_USB_DM", "4": "GNSS_USB_DP", "1": "HUB2_UP_DM", "2": "HUB2_UP_DP"},
      "Package_SO:QSOP-16_3.9x4.9mm_P0.635mm", "C4154405", "WCH CH334R 4-port USB 2.0 hub, QSOP-16",
      note="pinout checked against WCH CH334 datasheet (CH334R column). Upstream = VIM3 header pins 3/4 (VIM3 hub port 4)")
place(add_lib('Device', 'Crystal_GND24'), "Y1", "12MHz", 660, 305, {"1": "HUB_XI", "3": "HUB_XO", "2": "GND", "4": "GND"}, "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", "",
      "12MHz crystal (pick in library)", note="CH334R has built-in load capacitors")
cap("C61", "1u", 720, 262, "+5V_AON", "GND", note="at V5")
cap("C62", "10u", 728, 262, "HUB_3V3", "GND")
cap("C63", "100n", 736, 262, "HUB_3V3", "GND")
SEC[0] = "usb"
place(PF, "F5", "PTC 0.5A", 780, 270, {"1": "+5V_SYS", "2": "SDR_VBUS"}, "Fuse:Fuse_1206_3216Metric", "", "1206 PTC 0.5A hold (pick in library)")
USBA = add_lib('Connector', 'USB_A')
renumber_pin(USBA, "5", "SH")   # KiCad's USB-A footprints call the shield pads "SH", not "5"
place(USBA, "J17", "RTL-SDR (internal)", 805, 290, {"1": "SDR_VBUS", "2": "SDR_DM", "3": "SDR_DP", "4": "GND", "SH": "GND"}, "Connector_USB:USB_A_Molex_67643_Horizontal", "",
      "USB-A receptacle, board mount (pick in library)", note="RTL-SDR dongle for FM/DAB+ plugs in here with its existing USB-A to USB-C cable")
SEC[0] = "main"
text("Hub 1 runs from the always-on +5V_AON so a blank MCU enumerates (first flash over USB). One link to the VIM3: no USB cables. Port 1 MCU, 2 touch, 3 GNSS module USB, 4 second hub (external ports + RTL-SDR). Route D+/D- as 90 ohm pairs.", 610, 345)
text("VIM3 header pins 3/4 are a working USB host port (confirmed by Glenn, 2026-09-29).", 610, 349)

# ================================================================ 12. external USB ports (phone) + their own 5V/3A supply (rev 0.4: USB module)
SEC[0] = "usb"
text("12. EXTERNAL USB PORTS (phone etc.): second hub + dedicated 5V/3A supply, 1.5A current-limited per port", 320, 580 - 150, 2)
BUCK = add_lib('Regulator_Switching', 'LMR33630ADDA')
place(BUCK, "U15", "LMR33630ADDA", 360, 470, {"2": "VSYS_IN", "3": "VIM3_PWR_EN", "1": "GND", "9": "GND", "6": "USBP_VCC", "7": "USBP_BOOT", "8": "USBP_SW", "5": "USBP_FB", "4": "MCU_USBP_PG"},
      "Package_SO:TI_SO-PowerPAD-8_ThermalVias", "C841384", "TI LMR33630ADDAR 36V 3A buck, 400 kHz",
      note="pinout and values from the TI LMR33630 datasheet (5V/3A example). On whenever the VIM3 supply is enabled (GP23)")
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
      "9": "EXT1_VBUS", "8": "EXT2_VBUS", "7": "USBP_ILIM", "10": "MCU_USBP_FAULT1", "6": "MCU_USBP_FAULT2"},
      "Package_SON:VSON-10-1EP_3x3mm_P0.5mm_EP1.65x2.4mm", "C140303", "TI TPS2561DRCR dual 2.8A USB power switch",
      note="current limit 56000/RILIM(k) mA: 39k = 1.44 A per port")
cap("C72", "100n", 458, 485, "+5V_USB", "GND")
res("R77", "39k", 505, 485, "USBP_ILIM", "GND")
cap("C73", "100u", 515, 485, "EXT1_VBUS", "GND")
cap("C74", "100u", 523, 485, "EXT2_VBUS", "GND")
place(HUB, "U14", "CH334R", 560, 480,
      {"12": "+5V_SYS", "13": "HUB2_3V3", "14": "GND", "15": "HUB2_XO", "16": "HUB2_XI", "9": "HUB2_3V3",
       "10": "HUB2_UP_DM", "11": "HUB2_UP_DP", "7": "EXT1_DM", "8": "EXT1_DP", "5": "EXT2_DM", "6": "EXT2_DP", "3": "SDR_DM", "4": "SDR_DP", "1": None, "2": None},
      "Package_SO:QSOP-16_3.9x4.9mm_P0.635mm", "C4154405", "WCH CH334R 4-port USB 2.0 hub, QSOP-16",
      note="cascaded on hub 1 port 4. RESET#/CDP tied high = BC1.2 CDP for faster phone charging (WCH: depends on batch)")
place(add_lib('Device', 'Crystal_GND24'), "Y2", "12MHz", 530, 505, {"1": "HUB2_XI", "3": "HUB2_XO", "2": "GND", "4": "GND"}, "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", "", "12MHz crystal (pick in library)")
cap("C75", "1u", 580, 455, "+5V_SYS", "GND")
cap("C76", "10u", 588, 455, "HUB2_3V3", "GND")
cap("C77", "100n", 596, 455, "HUB2_3V3", "GND")
place(USBA, "J19", "External USB 1", 600, 510, {"1": "EXT1_VBUS", "2": "EXT1_DM", "3": "EXT1_DP", "4": "GND", "SH": "GND"}, "Connector_USB:USB_A_Molex_67643_Horizontal", "",
      "USB-A receptacle (pick in library), or a JST lead to a dash-mount USB socket")
place(USBA, "J20", "External USB 2", 600, 540, {"1": "EXT2_VBUS", "2": "EXT2_DM", "3": "EXT2_DP", "4": "GND", "SH": "GND"}, "Connector_USB:USB_A_Molex_67643_Horizontal", "",
      "USB-A receptacle (pick in library), or a JST lead to a dash-mount USB socket")

ESD = add_lib('Power_Protection', 'USBLC6-2SC6')
for i, (ref, y) in enumerate((("U17", 510), ("U18", 540)), 1):
    place(ESD, ref, "USBLC6-2SC6", 640, y, {"1": f"EXT{i}_DP", "6": f"EXT{i}_DP", "3": f"EXT{i}_DM", "4": f"EXT{i}_DM", "2": "GND", "5": f"EXT{i}_VBUS"},
          "Package_TO_SOT_SMD:SOT-23-6", "", "ST USBLC6-2SC6 USB ESD protection (pick in library)",
          note="review: ESD for the user-facing USB ports; place right at the connector, pairs route straight through pins 1-6 and 3-4")
text("Ports are powered only while the VIM3 supply is on. All USB shares the VIM3 header's USB 2.0 link (480 Mbit/s); RTL-SDR needs ~40 Mbit/s.", 320, 560)

# ---- USB module connector: 2x10 2.54 mm. Main board J25 = socket, module J26 = pin header (same pin map).
SEC[0] = "main+usb"
USB_HDR = {"1": "VSYS_IN", "2": "VSYS_IN", "3": "GND", "4": "GND", "5": "+5V_SYS", "6": "+5V_SYS", "7": "GND", "8": "GND",
           "9": None, "10": "HUB2_UP_DP", "11": None, "12": "HUB2_UP_DM", "13": "GND", "14": "GND",
           "15": "MCU_USBP_PG", "16": "VIM3_PWR_EN", "17": "MCU_USBP_FAULT2", "18": "MCU_USBP_FAULT1", "19": None, "20": "GND"}
if BOARD == "main":
    place(M2x10, "J25", "USB module socket", 540, 395, USB_HDR, "Connector_PinSocket_2.54mm:PinSocket_2x10_P2.54mm_Vertical", "C30867",
          "BOOMELE 2.54-2*10P female 8.5mm (LCSC out of stock 2026-10-01; any 2x10 2.54mm 8.5mm socket fits)",
          note="USB module plugs in here: 12V in for its 5V/3A supply, 5V for hub 2 and the SDR port, two USB pairs, enable and status")
elif BOARD == "usb":
    place(M2x10, "J26", "Main board plug", 540, 395, USB_HDR, "Connector_PinHeader_2.54mm:PinHeader_2x10_P2.54mm_Vertical", "C5116480",
          "ZHOURI 2.54-2*10 male pin header", note="mates with J25 on the main board")
SEC[0] = "usb"
for i, nmf in enumerate(["VSYS_IN", "+5V_SYS", "VIM3_PWR_EN"]):
    power('PWR_FLAG', 600 + 15 * i, 392, 90); label(nmf, 600 + 15 * i, 392, 270); nets.setdefault(nmf, []).append((f"#FLGU{i}", "1")); SECOF[f"#FLGU{i}"] = "usb"
power('PWR_FLAG', 645, 392, 90); power('GND', 645, 392, 270)
text("Car radio USB module rev 0.4 - phone ports, hub 2, their 5V/3A supply and the RTL-SDR socket; plugs onto the peripheral board (J26 -> J25). Generated by gen4.py usb.", 12, 416, 1.5)
SEC[0] = "main"
# ================================================================ 13. MCU core: RP2350B on the board (replaces the Pico 2 module)
text("13. MCU: RP2350B (QFN-80) + 16MB QSPI flash + 12MHz crystal + 3.3V LDO, per the Raspberry Pi Pico 2 reference design", 860, 16, 2)
# pin numbers from the official KiCad library symbol MCU_RaspberryPi:RP2350B (QFN-80); all GPIO, USB, QSPI, XIN/XOUT, RUN and SWD pins cross-checked against the WeAct RP2350B core board schematic
RP_GPIO_PIN = {0: 77, 1: 78, 2: 79, 3: 80, 4: 1, 5: 2, 6: 3, 7: 4, 8: 6, 9: 7, 10: 8, 11: 9, 12: 11, 13: 12, 14: 13, 15: 14,
               16: 16, 17: 17, 18: 18, 19: 19, 20: 20, 21: 21, 22: 22, 23: 23, 24: 25, 25: 26, 26: 27, 27: 28, 28: 36, 29: 37,
               30: 38, 31: 39, 32: 40, 33: 42, 34: 43, 35: 44, 36: 45, 37: 46, 38: 47, 39: 48,
               40: 49, 41: 52, 42: 53, 43: 54, 44: 55, 45: 56, 46: 57, 47: 58}
# rev 0.4 (2026-10-02): GPIOs re-assigned so each signal leaves the QFN on the side facing its destination
GPIO_NET = {0: "MCU_BL_EN", 1: "MCU_BL_PWM", 2: "MCU_HUB_RST", 3: "MCU_GNSS_PPS", 4: "MCU_GNSS_TX", 5: "MCU_GNSS_RX", 6: "MCU_SBC_SENSE", 7: "MCU_GNSS_RST", 8: "MCU_GNSS_SAFEBOOT", 9: "MCU_GNSS_EN", 10: "MCU_DAC_MUTE", 14: "MCU_PARK_IN", 15: "MCU_PWR_KEY", 16: "MCU_BTN_MUTE", 17: "MCU_BTN_VOLUP", 18: "MCU_BTN_SCREEN", 19: "MCU_SERVICE", 20: "MCU_AMP_EN", 21: "MCU_LED", 22: "MCU_BTN_VOLDN", 23: "MCU_VIM3_PWR_EN", 24: "EXP_GP24", 25: "EXP_GP25", 26: "EXP_GP26", 27: "EXP_GP27", 28: "EXP_GP28", 30: "LUX_SDA", 31: "LUX_SCL", 32: "EXP_GP32", 33: "EXP_GP33", 35: "MCU_REV_IN", 36: "MCU_USBP_PG", 37: "MCU_ILLUM_IN", 38: "MCU_USBP_FAULT2", 39: "MCU_USBP_FAULT1", 40: "MCU_VBAT_ADC", 41: "MCU_5VSYS_ADC", 42: "MCU_TEMP_ADC", 43: "MCU_ACC_IN"}
RP_LEFT = [(64, "VREG_VIN"), (63, "VREG_LX"), (65, "VREG_FB"), (61, "VREG_AVDD"), (62, "VREG_PGND"), None,
           (5, "IOVDD"), (15, "IOVDD"), (24, "IOVDD"), (29, "IOVDD"), (41, "IOVDD"), (50, "IOVDD"), (60, "IOVDD"), (76, "IOVDD"), None,
           (10, "DVDD"), (32, "DVDD"), (51, "DVDD"), None, (59, "ADC_AVDD"), (68, "USB_OTP_VDD"), (69, "QSPI_IOVDD"), None,
           (75, "~{QSPI_SS}"), (71, "QSPI_SCLK"), (72, "QSPI_SD0"), (74, "QSPI_SD1"), (73, "QSPI_SD2"), (70, "QSPI_SD3"), None,
           (30, "XIN"), (31, "XOUT"), None, (33, "SWCLK"), (34, "SWDIO"), (35, "RUN"), None, (66, "USB_DM"), (67, "USB_DP"), None, (81, "GND (pad)")]
RP_RIGHT = [(RP_GPIO_PIN[g], f"GPIO{g}" + (f"/ADC{g - 40}" if g >= 40 else "")) for g in range(48)]
RP = box_symbol("RP2350B", RP_LEFT, RP_RIGHT, width=30.48, ref="U", value="RP2350B")
rp_conns = {"64": "+3V3_MCU", "63": "MCU_VREG_LX", "65": "+1V1_MCU", "61": "MCU_VREG_AVDD", "62": "GND", "81": "GND",
            "59": "+3V3_MCU", "68": "+3V3_MCU", "69": "+3V3_MCU",
            "75": "QSPI_SS", "71": "QSPI_SCLK", "72": "QSPI_SD0", "74": "QSPI_SD1", "73": "QSPI_SD2", "70": "QSPI_SD3",
            "30": "MCU_XIN", "31": "MCU_XOUT", "33": "MCU_SWCLK", "34": "MCU_SWDIO", "35": "MCU_RUN", "66": "MCU_USB_DM_R", "67": "MCU_USB_DP_R"}
for p in (5, 15, 24, 29, 41, 50, 60, 76): rp_conns[str(p)] = "+3V3_MCU"
for p in (10, 32, 51): rp_conns[str(p)] = "+1V1_MCU"
for g, n in GPIO_NET.items(): rp_conns[str(RP_GPIO_PIN[g])] = n
for g in range(44, 48): rp_conns[str(RP_GPIO_PIN[g])] = None
place(RP, "U20", "RP2350B", 960, 150, rp_conns, "Package_DFN_QFN:QFN-80-1EP_10x10mm_P0.4mm_EP3.4x3.4mm", "", "Raspberry Pi RP2350B, QFN-80 (use the EasyEDA library footprint)",
      note="GPIO map: rev 0.4 README (re-assigned for routing). ADCs stay on GPIO40-42 (only GPIO40-47 have ADC); GNSS on UART1 (GPIO4/5), I2C on I2C1 (GPIO30/31)")

# 3.3V: low-quiescent LDO from the always-on 5.2V (the Pico module's own regulator is gone)
LDO33 = add_lib('Regulator_Linear', 'AP2112K-3.3')
place(LDO33, "U19", "AP2112K-3.3", 880, 60, {"1": "+5V_AON", "3": "+5V_AON", "2": "GND", "5": "+3V3_MCU", "4": None},
      "Package_TO_SOT_SMD:SOT-23-5", "", "Diodes AP2112K-3.3TRG1 600mA LDO (pick in library)",
      note="MCU, GNSS backup, light sensor, pull-ups; replaces the Pico 2 regulator")
cap("C80", "1u", 866, 75, "+5V_AON", "GND")
cap("C81", "10u", 896, 75, "+3V3_MCU", "GND")

# core regulator (RP2350 internal switcher): values from the Pico 2 schematic
place(L, "L5", "3.3uH", 900, 110, {"1": "MCU_VREG_LX", "2": "+1V1_MCU"}, "Inductor_SMD:L_Murata_DFE201610P", "",
      "Abracon AOTA-B201610S3R3-101-T 3.3uH 2016 (pick in library)",
      note="Raspberry Pi reference part. Its orientation affects the regulator (hardware design guide): copy the Pico 2 layout for L5, C82, C83")
cap("C82", "4u7", 880, 110, "+3V3_MCU", "GND", note="VREG_VIN, next to pin 64")
cap("C83", "4u7", 912, 125, "+1V1_MCU", "GND", note="DVDD / VREG_FB output cap, next to the inductor")
res("R80", "33", 880, 130, "+3V3_MCU", "MCU_VREG_AVDD", note="VREG_AVDD filter (Pico 2: 33R + 4.7uF)")
cap("C84", "4u7", 888, 140, "MCU_VREG_AVDD", "GND")
# decoupling: 100nF per IOVDD and DVDD pin, ADC_AVDD, and one shared by USB_OTP_VDD + QSPI_IOVDD
dec = [("C85", "+3V3_MCU", "IOVDD 5"), ("C86", "+3V3_MCU", "IOVDD 15"), ("C87", "+3V3_MCU", "IOVDD 24"), ("C88", "+3V3_MCU", "IOVDD 29"),
       ("C89", "+3V3_MCU", "IOVDD 41"), ("C90", "+3V3_MCU", "IOVDD 50"), ("C91", "+3V3_MCU", "IOVDD 60"), ("C92", "+3V3_MCU", "IOVDD 76"),
       ("C93", "+1V1_MCU", "DVDD 10"), ("C94", "+1V1_MCU", "DVDD 32"), ("C95", "+1V1_MCU", "DVDD 51"),
       ("C96", "+3V3_MCU", "ADC_AVDD 59"), ("C97", "+3V3_MCU", "USB_OTP_VDD 68 + QSPI_IOVDD 69")]
for i, (r, n, nt) in enumerate(dec):
    cap(r, "100n", 870 + 8 * (i % 7), 170 + 18 * (i // 7), n, "GND", note=f"at {nt}")

# QSPI flash + BOOTSEL
FLASH = add_lib('Memory_Flash', 'W25Q128JVS')
place(FLASH, "U21", "W25Q128JVS", 900, 250, {"1": "QSPI_SS", "2": "QSPI_SD1", "3": "QSPI_SD2", "4": "GND", "5": "QSPI_SD0", "6": "QSPI_SCLK", "7": "QSPI_SD3", "8": "+3V3_MCU"},
      "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", "", "Winbond W25Q128JVSIQ 16MB QSPI flash (pick in library)")
cap("C98", "100n", 880, 270, "+3V3_MCU", "GND", note="at flash VCC")
res("R81", "1k", 925, 280, "QSPI_SS", "BOOTSEL_SW")
SWP = add_lib('Switch', 'SW_Push')
place(SWP, "SW1", "BOOTSEL", 940, 290, {"1": "BOOTSEL_SW", "2": "GND"}, "Button_Switch_SMD:SW_SPST_TL3342", "", "SMD tact switch 4.2x3.2mm (pick in library)",
      note="hold while resetting to enter the USB bootloader")

# crystal: ABM8-272-T3, 15pF load caps, 1k series resistor on XOUT (Pico 2 schematic)
place(add_lib('Device', 'Crystal_GND24'), "Y3", "12MHz", 1010, 290, {"1": "MCU_XIN", "3": "MCU_XTAL_R", "2": "GND", "4": "GND"},
      "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", "", "Abracon ABM8-272-T3 12MHz (pick in library)")
res("R82", "1k", 1030, 280, "MCU_XOUT", "MCU_XTAL_R", note="series resistor on XOUT")
place(C, "C99", "15pF", 995, 305, {"1": "MCU_XIN", "2": "GND"}, FP_C0603, "", "0603 15pF 50V C0G (pick in library)")
place(C, "C100", "15pF", 1025, 305, {"1": "MCU_XTAL_R", "2": "GND"}, FP_C0603, "", "0603 15pF 50V C0G (pick in library)")

# USB to hub 1 port 1: 27R series (Pico 2 schematic)
res("R83", "27", 1060, 230, "MCU_USB_DM_R", "MCU_USB_DM", note="USB series termination")
res("R84", "27", 1068, 230, "MCU_USB_DP_R", "MCU_USB_DP")

# SWD, reset, status LED
place(CG4, "J22", "SWD", 1100, 60, {"1": "MCU_SWCLK", "2": "GND", "3": "MCU_SWDIO", "4": "MCU_RUN"},
      "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "", "1x4 2.54mm pin header", note="Debug probe: SWCLK, GND, SWDIO, RUN")
res("R85", "10k", 1080, 90, "+3V3_MCU", "MCU_RUN")
cap("C101", "100n", 1088, 105, "MCU_RUN", "GND")
place(SWP, "SW2", "RESET", 1110, 100, {"1": "MCU_RUN", "2": "GND"}, "Button_Switch_SMD:SW_SPST_TL3342", "", "SMD tact switch 4.2x3.2mm (pick in library)")
res("R86", "1k", 1080, 130, "MCU_LED", "MCU_LED_K")
place(LED, "D16", "LED green", 1095, 140, {"1": "GND", "2": "MCU_LED_K"}, "LED_SMD:LED_0805_2012Metric", "", "0805 green LED (pick in library)", note="status LED (Pico LED was on GP25)")

# status inputs from the power stage (all open-drain)
for r, n, nt in (("R87", "MCU_USBP_FAULT1", "TPS2561 FAULT1: port 1 over-current"), ("R88", "MCU_USBP_FAULT2", "TPS2561 FAULT2: port 2 over-current"),
                 ("R89", "MCU_USBP_PG", "LMR33630 power good")):
    res(r, "10k", 1060 + 8 * int(r[-1]), 330, "+3V3_MCU", n, note=nt)
res("R90", "1k", 1100, 360, "MCU_HUB_RST", "HUB1_RST", note="firmware pulls low to reset hub 1 (e.g. while the VIM3 is off), otherwise input")
res("R104", "10k", 1108, 360, "HUB_3V3", "HUB1_RST", note="keeps hub 1 out of reset on a blank MCU (RP2350 pads default to pull-down)")
res("R79", "1k", 1110, 360, "MCU_GNSS_SAFEBOOT", "GNSS_SAFEBOOT", note="firmware keeps this an input; low at GNSS power-up = u-blox safeboot")

# ADC: battery (GPIO40), 5V system rail (GPIO41), board temperature (GPIO42)
res("R91", "10k", 870, 360, "+5V_SYS", "MCU_5VSYS_ADC", note="5V system rail monitor: /2")
res("R92", "10k", 878, 360, "MCU_5VSYS_ADC", "GND")
cap("C102", "100n", 886, 360, "MCU_5VSYS_ADC", "GND")
res("R93", "10k", 900, 360, "+3V3_MCU", "MCU_TEMP_ADC")
place(add_lib('Device', 'Thermistor_NTC'), "TH1", "NTC 10k B3950", 908, 375, {"1": "MCU_TEMP_ADC", "2": "GND"}, FP_R0603, "", "0603 NTC 10k 1% B~3950 (pick in library)",
      note="place next to the TPS55288 / LMR33630: board temperature for thermal derating")
cap("C103", "100n", 916, 360, "MCU_TEMP_ADC", "GND")

# expansion: GPIO32-39
place(add_lib('Connector_Generic', 'Conn_01x10'), "J21", "Expansion 2", 1140, 200,
      {"1": "+3V3_MCU", "2": "LUX_SDA", "3": "LUX_SCL", "4": None, "5": None,   # rev 0.5: I2C1 here, GPIO11/12/29/34 dropped
       "6": "EXP_GP27", "7": "EXP_GP26", "8": "EXP_GP25", "9": "EXP_GP24", "10": "GND"},
      "Connector_PinHeader_2.54mm:PinHeader_1x10_P2.54mm_Vertical", "", "1x10 2.54mm pin header", note="spare GPIOs (e.g. CAN, extra UART/SPI); numbers in the net names")
text("rev 0.4: GPIO map re-assigned for routing; see the README pin table. ADC: GPIO40 battery, 41 5V rail, 42 board temperature.", 860, 400)
text("GPIO44-47 are unused (ADC-capable spares).", 860, 404)

# RP2350-E9 (input pad can latch near 2V with only the internal pull-down): every MCU input that can float
# gets an external resistor. Pull-downs are 4.7k (below the ~8.2k the erratum workaround calls for).
res("R94", "4.7k", 1000, 360, "MCU_GNSS_PPS", "GND", note="RP2350-E9: PPS floats while the GNSS supply is off")
res("R95", "4.7k", 1008, 360, "MCU_GNSS_RX", "GND", note="RP2350-E9: UART RX floats while the GNSS supply is off")
res("R96", "100k", 1016, 360, "MCU_BL_EN", "GND", note="backlight off while the MCU is in reset or booting")
text("RP2350-E9 check (every MCU pin): opto inputs GP2/3/6/7 4.7k down; SBC sense and service jumper 4.7k down; buttons, USB faults/PG, I2C, RUN pulled up;", 860, 412)
text("GNSS PPS/RX 4.7k down (R94/R95); outputs have defined off-state resistors; ADC pins run with the digital input disabled; unused and expansion pins: see DESIGN_rev03.md.", 860, 416)


# Layout review follow-up 2026-10-01: series gate resistors (fitted as 0 ohm; try 2.2-4.7 ohm on the bench only after
# checking dead time on a scope, the TPS55288 senses the gate through DRx) and an RC snubber on SW1. Added last so the
# generated UUIDs of every earlier part stay the same.
R0402 = "Resistor_SMD:R_0402_1005Metric"
place(R, "R97", "0Ω", 760, 45, {"1": "BB_DR1H", "2": "BB_DR1H_G"}, R0402, "C17168", "UNI-ROYAL 0402WGF0000TCE 0402 0R",
      note="DR1H gate resistor: 0 ohm by default; 2.2-4.7 ohm slows SW1 edges (check dead time on a scope first)")
place(R, "R98", "0Ω", 760, 100, {"1": "BB_DR1L", "2": "BB_DR1L_G"}, R0402, "C17168", "UNI-ROYAL 0402WGF0000TCE 0402 0R",
      note="DR1L gate resistor: 0 ohm by default; 2.2-4.7 ohm slows SW1 edges (check dead time on a scope first)")
place(C, "C104", "1nF", 790, 100, {"1": "BB_SW1", "2": "BB_SNUB"}, FP_C0603, "C1588", "Samsung CL10B102KB8NNNC 0603 1nF 50V X7R",
      note="SW1 RC snubber; about 0.08 W in R99 at 14 V and 422 kHz")
place(R, "R99", "2.2Ω 0805", 800, 100, {"1": "BB_SNUB", "2": "GND"}, FP_R0805, "C17521", "UNI-ROYAL 0805W8F220KT5E 0805 2.2R 125mW",
      note="SW1 RC snubber resistor")

# ================================================================ power flags
def flag(net, x, y):
    power('PWR_FLAG', x, y, 90)
    label(net, x, y, 270)
    nets.setdefault(net, []).append(("#FLG" + SEC[0], "1")); SECOF["#FLG" + SEC[0]] = SEC[0]
fx = 330
for net in ["BATT_RAW", "ACC_RAW", "VIM3_3V3", "VIM3_5V", "+5V_AON", "+5V_SYS", "+5V_USB", "SDR_VBUS", "VSYS_IN", "HDMI_5V"]:
    SEC[0] = "usb" if net in ("+5V_USB", "SDR_VBUS") else "main"
    flag(net, fx, 392); fx += 15
SEC[0] = "main"
power('PWR_FLAG', fx, 392, 90); power('GND', fx, 392, 270)

text("Car radio peripheral board rev 0.4 - MG F (1996), VIM3 + RP2350B, 4ch line out on the audio module, NEO-M9N. Generated by gen4.py; see DESIGN_rev04.md.", 12, 412, 1.5)

# ---------------------------------------------------------------- write
sch = [S('kicad_sch'), [S('version'), 20230121], [S('generator'), S('eeschema')], [S('uuid'), ROOT], [S('paper'), "A0"],
       [S('title_block'), [S('title'), {"main": "Car radio peripheral board (RP2350B + VIM3)", "audio": "Car radio audio module (2x PCM5102A)", "usb": "Car radio USB module", "gnss": "Car radio GNSS module (NEO-M9N)"}[BOARD]], [S('date'), "2026-10-01"], [S('rev'), "0.4"]],
       [S('lib_symbols')] + list(lib_symbols.values())] + [it for it, tg in zip(items, items.tags) if mine(tg)] + \
      [[S('sheet_instances'), [S('path'), "/", [S('page'), "1"]]]]
open(f"{PROJECT}.kicad_sch", "w").write(dump(sch) + "\n")
with open(f"{PROJECT}_bom.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Value", "Description / MPN", "LCSC", "Footprint (KiCad name)", "Fit", "Note"])
    bom = [b for b in bom if mine(b['sec'])]
    for b in bom:
        w.writerow([b['ref'], b['value'], b['mpn'], b['lcsc'], b['fp'], "DNP" if b['dnp'] else "yes", b['note']])
refs = [b['ref'] for b in bom]
dups = {r for r in refs if refs.count(r) > 1}
nets = {n: [(r, p) for r, p in v if mine(SECOF.get(r, "main"))] for n, v in nets.items()}
nets = {n: v for n, v in nets.items() if v}
# spare module-connector lines are allowed to end at the connector on the module
bad = {n: v for n, v in nets.items() if len(v) < 2 and n != '(flag)' and not (BOARD != "main" and v[0][0] in ("J24", "J26", "J28"))}
if bad or dups:
    print("SINGLE-PIN NETS:", bad, "DUP REFS:", dups); sys.exit(1)
print("ok", len(bom), "parts", len(nets), "nets")
