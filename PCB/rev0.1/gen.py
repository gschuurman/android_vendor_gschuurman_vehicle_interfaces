#!/usr/bin/env python3
"""Generate the car-radio peripheral board schematic (KiCad 7 .kicad_sch) + BOM.

Every connection is made with net labels placed on pin endpoints, so the netlist
is unambiguous and survives import into EasyEDA Pro.
"""
import csv, uuid, copy, sys
from sexp import Sym, parse, dump, find_sym, pins_of

S = Sym
PROJECT = "carradio_peripheral"
ROOT = str(uuid.uuid5(uuid.NAMESPACE_URL, "carradio-peripheral-root"))
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

POS = {
 "J1": (25, 50), "F1": (55, 45), "D1": (80, 45), "D2": (100, 62), "C1": (115, 50), "C2": (128, 50), "U1": (160, 50),
 "C3": (190, 36), "L1": (205, 50), "R1": (220, 50), "R2": (220, 74), "C4": (235, 50), "D3": (250, 80),
 "F2": (272, 48), "D4": (292, 45), "D5": (292, 62), "C5": (307, 52), "R3": (320, 45), "D6": (328, 64), "U2": (352, 50),
 "R4": (377, 55), "C6": (392, 55), "C8": (405, 72),
 "R5": (320, 88), "D7": (328, 106), "U3": (352, 92), "R6": (377, 97), "C7": (392, 97),
 "D8": (35, 158), "R13": (55, 145), "Q2": (72, 152), "R14": (55, 172), "Q3": (72, 192), "R15": (60, 205),
 "R16": (42, 188), "R17": (25, 188), "D9": (98, 172), "R18": (110, 152), "D10": (125, 172),
 "J3": (175, 172), "J4": (235, 172), "R7": (268, 145), "R8": (276, 160), "JP1": (270, 188), "R9": (285, 198),
 "R10": (292, 148), "R11": (292, 168), "C9": (302, 180),
 "R12": (22, 245), "R19": (27, 265), "Q1": (42, 255), "J5": (65, 255),
 "R20": (88, 250), "R21": (100, 250), "R22": (112, 250), "R23": (128, 250), "R24": (140, 250), "J6": (165, 252),
 "R25": (185, 250), "R26": (197, 250), "R27": (209, 250), "R28": (221, 250), "J7": (245, 255),
 "J2": (372, 172),
}
TEXTPOS = {
 "1. VEHICLE": (15, 22), "J1: 1=BATT+": (15, 68), "Always-on": (110, 92),
 "2. ACC": (265, 22), "LED ~": (265, 120),
 "3. AMPLIFIER": (15, 130), "Gate = ": (15, 218),
 "4. PICO": (150, 130), "Pico firmware": (150, 208), "GP6 SBC": (150, 212),
 "5. VIM3": (15, 232), "VIM3 pin v": (300, 212), "VERIFY": (300, 216), "Android side": (15, 280), "pin 35 PWM_F": (15, 284),
 "Car radio peripheral board": None,
}
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

def place(lib_id, ref, value, x, y, conns, fp="", lcsc="", mpn="", dnp=False, note=""):
    """conns: {pin_number: net or None(no-connect)}; unspecified pins -> no-connect."""
    x, y = POS.get(ref, (x, y))
    pins = pin_table[lib_id]
    props = [
        [S('property'), "Reference", ref, [S('at'), x + 2.2, y - 1.2, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], [S('justify'), S('left')]]],
        [S('property'), "Value", value, [S('at'), x + 2.2, y + 1.2, 0], [S('effects'), [S('font'), [S('size'), 1.0, 1.0]], [S('justify'), S('left')]]],
        [S('property'), "Footprint", fp, [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
        [S('property'), "Datasheet", "", [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
        [S('property'), "LCSC", lcsc, [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
        [S('property'), "MPN", mpn, [S('at'), x, y, 0], [S('effects'), [S('font'), [S('size'), 1.27, 1.27]], S('hide')]],
    ]
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

# ---------------------------------------------------------------- library parts
R = add_lib('Device', 'R'); C = add_lib('Device', 'C'); L = add_lib('Device', 'L')
DS = add_lib('Device', 'D_Schottky'); DZ = add_lib('Device', 'D_Zener'); PF = add_lib('Device', 'Polyfuse')
OPTO = add_lib('Isolator', 'EL817'); NMOS = add_lib('Transistor_FET', 'AO3400A'); PMOS = add_lib('Transistor_FET', 'AO3401A')
D4148 = add_lib('Diode', '1N4148W'); TERM5 = add_lib('Connector', 'Screw_Terminal_01x05')
C2 = add_lib('Connector_Generic', 'Conn_01x02'); C3 = add_lib('Connector_Generic', 'Conn_01x03'); C4 = add_lib('Connector_Generic', 'Conn_01x04')

FP_R0603 = "Resistor_SMD:R_0603_1608Metric"; FP_R0805 = "Resistor_SMD:R_0805_2012Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"; FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"; FP_C1206 = "Capacitor_SMD:C_1206_3216Metric"
FP_SMA = "Diode_SMD:D_SMA"; FP_SMB = "Diode_SMD:D_SMB"; FP_SOD123 = "Diode_SMD:D_SOD-123"; FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"

RES = {  # value -> (lcsc 0603)
    "100": "C22775", "1k": "C21190", "4.7k": "C23162", "10k": "C25804", "22k": "C31850", "24k": "C23352",
    "100k": "C25803", "220k": "C22961", "1M": "C22935", "0": "C21189"}
def res(ref, val, x, y, a, b, dnp=False, note=""):
    place(R, ref, val + ("Ω" if val[-1].isdigit() else ""), x, y, {"1": a, "2": b}, FP_R0603, RES[val], f"0603 {val} 1%", dnp, note)
def cap(ref, val, x, y, a, b):
    table = {"100n": (FP_C0603, "C14663", "0603 100nF 50V X7R"), "10u50": (FP_C1206, "C13585", "1206 10uF 50V X5R"),
             "22u": (FP_C0805, "C45783", "0805 22uF 25V X5R")}
    fp, l, m = table[val]
    place(C, ref, {"100n": "100nF 50V", "10u50": "10uF 50V", "22u": "22uF 25V"}[val], x, y, {"1": a, "2": b}, fp, l, m)

# ================================================================ SECTION 1: vehicle connector + always-on supply
text("1. VEHICLE CONNECTOR, PROTECTION, ALWAYS-ON 5V FOR PICO", 15, 18, 2)
place(TERM5, "J1", "Vehicle 5-pin 5.08mm", 25, 45,
      {"1": "BATT_RAW", "2": "ACC_RAW", "3": "REV_RAW", "4": "AMP_REM_OUT", "5": "GND"},
      "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MSTBA-2,5-5-G-5,08_1x05_P5.08mm_Horizontal", "", "5.08mm pluggable terminal block 5P (pick from EasyEDA library)",
      note="1 BATT+ permanent, 2 ACC, 3 REVERSE lamp, 4 AMP REMOTE out, 5 GND")
text("J1: 1=BATT+ (permanent 12V)  2=ACC  3=REVERSE lamp +12V  4=AMP REMOTE out  5=GND", 15, 58)

place(PF, "F1", "PTC 200mA hold, 30V", 50, 40, {"1": "BATT_RAW", "2": "BATT_F"}, "Fuse:Fuse_1206_3216Metric", "", "1206 PTC 0.2A hold 30V (pick in library)")
place(DS, "D1", "SS34", 62, 40, {"1": "VBAT_P", "2": "BATT_F"}, FP_SMA, "C8678", "SS34 40V 3A Schottky", note="reverse-polarity protection")
place(DZ, "D2", "SMBJ18A TVS", 75, 45, {"1": "VBAT_P", "2": "GND"}, FP_SMB, "C49301917", "SMBJ18A 600W TVS (unidirectional)")
cap("C1", "10u50", 85, 45, "VBAT_P", "GND")
cap("C2", "100n", 92, 45, "VBAT_P", "GND")

TPS = box_symbol("TPS560430XDBVR", [(5, "VIN"), (4, "EN"), None, (2, "GND")], [(1, "CB"), (6, "SW"), None, (3, "FB")], width=15.24, ref="U")
place(TPS, "U1", "TPS560430XDBVR", 110, 45, {"5": "VBAT_P", "4": "VBAT_P", "2": "GND", "1": "BUCK_CB", "6": "BUCK_SW", "3": "BUCK_FB"},
      "Package_TO_SOT_SMD:SOT-23-6", "C524782", "TPS560430XDBVR 36V 600mA buck, 1.1MHz", note="pinout checked against TI datasheet: 1 CB, 2 GND, 3 FB, 4 EN, 5 VIN, 6 SW")
cap("C3", "100n", 128, 38, "BUCK_CB", "BUCK_SW")
place(L, "L1", "18uH", 136, 45, {"1": "BUCK_SW", "2": "+5V_AON"}, "Inductor_SMD:L_Sunlord_SWPA4030S", "C96895", "SWPA4030S180MT 18uH (TI-recommended value for 5V out)")
res("R1", "100k", 146, 45, "+5V_AON", "BUCK_FB")
res("R2", "24k", 146, 58, "BUCK_FB", "GND", note="Vout = 1.0V x (1 + 100k/24k) = 5.17V")
cap("C4", "22u", 156, 45, "+5V_AON", "GND")
place(DS, "D3", "SS14", 168, 40, {"1": "PICO_VSYS", "2": "+5V_AON"}, FP_SMA, "C2480", "SS14 40V 1A Schottky", note="lets Pico USB and board 5V coexist (Pico datasheet VSYS OR-ing)")
text("Always-on: ~5.2V into Pico VSYS. TPS560430X is PFM at light load (~55uA Iq).", 95, 66)

# ================================================================ SECTION 2: ACC + reverse inputs (opto-isolated)
text("2. ACC + REVERSE INPUTS (opto-isolated, active-high)", 190, 18, 2)
place(PF, "F2", "PTC 750mA hold, 30V", 200, 40, {"1": "ACC_RAW", "2": "ACC_F"}, "Fuse:Fuse_1812_4532Metric", "", "1812 PTC 0.75A hold 30V (pick in library)", note="also feeds amp remote output")
place(DS, "D4", "SS34", 212, 40, {"1": "ACC_P", "2": "ACC_F"}, FP_SMA, "C8678", "SS34 40V 3A Schottky")
place(DZ, "D5", "SMBJ18A TVS", 222, 45, {"1": "ACC_P", "2": "GND"}, FP_SMB, "C49301917", "SMBJ18A 600W TVS (unidirectional)")
cap("C5", "100n", 230, 45, "ACC_P", "GND")

place(R, "R3", "4.7kΩ 0805", 245, 38, {"1": "ACC_P", "2": "ACC_LED"}, FP_R0805, "C17673", "0805 4.7k 1%")
place(D4148, "D6", "1N4148W", 252, 52, {"1": "ACC_LED", "2": "GND"}, FP_SOD123, "C81598", "1N4148W", note="reverse-voltage clamp across opto LED")
place(OPTO, "U2", "EL817S1(C)", 272, 45, {"1": "ACC_LED", "2": "GND", "4": "+3V3_PICO", "3": "PICO_ACC_IN"},
      "Package_DIP:SMDIP-4_W7.62mm", "C106900", "EL817S1(C)(TU)-F")
res("R4", "4.7k", 290, 50, "PICO_ACC_IN", "GND")
cap("C6", "100n", 297, 50, "PICO_ACC_IN", "GND")

place(R, "R5", "4.7kΩ 0805", 245, 72, {"1": "REV_RAW", "2": "REV_LED"}, FP_R0805, "C17673", "0805 4.7k 1%")
place(D4148, "D7", "1N4148W", 252, 86, {"1": "REV_LED", "2": "GND"}, FP_SOD123, "C81598", "1N4148W")
place(OPTO, "U3", "EL817S1(C)", 272, 79, {"1": "REV_LED", "2": "GND", "4": "+3V3_PICO", "3": "PICO_REV_IN"},
      "Package_DIP:SMDIP-4_W7.62mm", "C106900", "EL817S1(C)(TU)-F")
res("R6", "4.7k", 290, 84, "PICO_REV_IN", "GND")
cap("C7", "100n", 297, 84, "PICO_REV_IN", "GND")
cap("C8", "100n", 305, 70, "+3V3_PICO", "GND")
text("LED ~2.7mA at 14.4V, ~1.7mA at 9V; EL817 C-grade CTR >= 200%. 4.7k pull-downs satisfy RP2350-E9.", 235, 100)

# ================================================================ SECTION 3: amplifier remote 12V output
text("3. AMPLIFIER REMOTE-ON (+12V high-side, switched from ACC)", 320, 18, 2)
place(PMOS, "Q2", "AO3401A", 345, 45, {"S": "ACC_P", "D": "AMP_REM_OUT", "G": "AMP_G"}, FP_SOT23, "C15127", "AO3401A -30V -4A P-MOSFET")
res("R13", "10k", 330, 34, "ACC_P", "AMP_G")
place(DZ, "D8", "BZT52C12", 322, 45, {"1": "ACC_P", "2": "AMP_G"}, FP_SOD123, "C124196", "BZT52C12-7-F 12V zener", note="Vgs clamp")
res("R14", "10k", 330, 60, "AMP_G", "AMP_PULL")
place(NMOS, "Q3", "AO3400A", 345, 78, {"D": "AMP_PULL", "S": "GND", "G": "AMP_CTRL"}, FP_SOT23, "C20917", "AO3400A 30V 5.7A N-MOSFET")
res("R15", "100k", 332, 88, "AMP_CTRL", "GND")
res("R16", "0", 322, 72, "PICO_AMP_EN", "AMP_CTRL", note="fit: Pico GP11 controls the amp")
res("R17", "0", 312, 72, "VIM3_GPIOH4", "AMP_CTRL", dnp=True, note="DNP: fit instead of R16 to let Android (header pin 37) control the amp")
place(DS, "D9", "SS34", 362, 55, {"1": "AMP_REM_OUT", "2": "GND"}, FP_SMA, "C8678", "SS34 40V 3A Schottky", note="clamps inductive kick from long remote wire")
place(R, "R18", "4.7kΩ 0805", 372, 45, {"1": "AMP_REM_OUT", "2": "AMP_LED"}, FP_R0805, "C17673", "0805 4.7k 1%")
place(add_lib('Device', 'LED'), "D10", "LED green", 382, 55, {"2": "AMP_LED", "1": "GND"}, "LED_SMD:LED_0805_2012Metric", "", "0805 green LED (pick in library)", note="amp remote on indicator")
text("Gate = -Vacc/2 (~-7V at 14.4V). Rated ~1A; typical remote inputs draw <100mA.", 312, 100)

# ================================================================ SECTION 4: Pico 2 module (2x 1x20 sockets)
text("4. PICO 2 (on two 1x20 female headers, 17.78mm apart)", 15, 125, 2)
pico_nets = {1: "PICO_TX", 2: "PICO_RX", 3: "GND", 4: "PICO_REV_OUT", 7: "PICO_PWR_BTN", 8: "GND", 9: "PICO_SBC_SENSE",
             13: "GND", 14: "PICO_SERVICE", 15: "PICO_AMP_EN", 18: "GND",
             23: "GND", 27: "PICO_REV_IN", 28: "GND", 31: "PICO_VBAT_ADC", 32: "PICO_ACC_IN", 33: "GND", 36: "+3V3_PICO",
             38: "GND", 39: "PICO_VSYS"}
pico_names = {1: "GP0", 2: "GP1", 3: "GND", 4: "GP2", 5: "GP3", 6: "GP4", 7: "GP5", 8: "GND", 9: "GP6", 10: "GP7", 11: "GP8", 12: "GP9",
              13: "GND", 14: "GP10", 15: "GP11", 16: "GP12", 17: "GP13", 18: "GND", 19: "GP14", 20: "GP15", 21: "GP16", 22: "GP17",
              23: "GND", 24: "GP18", 25: "GP19", 26: "GP20", 27: "GP21", 28: "GND", 29: "GP22", 30: "RUN", 31: "GP26_ADC0", 32: "GP27_ADC1",
              33: "AGND", 34: "GP28_ADC2", 35: "ADC_VREF", 36: "3V3_OUT", 37: "3V3_EN", 38: "GND", 39: "VSYS", 40: "VBUS"}
PL = box_symbol("Pico2_Left_1x20", [(i, f"{i}:{pico_names[i]}") for i in range(1, 21)], [], width=17.78, ref="J",
                value="Pico2 pins 1-20")
PR = box_symbol("Pico2_Right_1x20", [], [(i - 20, f"{i}:{pico_names[i]}") for i in range(21, 41)], width=17.78, ref="J",
                value="Pico2 pins 21-40")
place(PL, "J3", "Pico 2 pins 1-20 (1x20 F)", 45, 160, {str(i): pico_nets.get(i) for i in range(1, 21)},
      "Connector_PinSocket_2.54mm:PinSocket_1x20_P2.54mm_Vertical", "", "1x20 2.54mm female header (pick in library)",
      note="pad n = Pico pin n")
place(PR, "J4", "Pico 2 pins 21-40 (1x20 F)", 95, 160, {str(i - 20): pico_nets.get(i) for i in range(21, 41)},
      "Connector_PinSocket_2.54mm:PinSocket_1x20_P2.54mm_Vertical", "", "1x20 2.54mm female header (pick in library)",
      note="pad n = Pico pin 20+n; J4 pad 1 (pin 21) sits opposite J3 pad 20 (pin 20)")
text("Pico firmware pin use (mcu/main.py): GP27 ACC in, GP21 reverse in, GP2 reverse out, GP5 power button,", 15, 192)
text("GP6 SBC 3.3V sense, GP10 service jumper. New on this board: GP11 amp remote, GP26 battery voltage, GP0/GP1 UART to VIM3.", 15, 196)

# Pico-side helpers
res("R7", "1k", 130, 140, "VIM3_3V3", "PICO_SBC_SENSE")
res("R8", "4.7k", 138, 150, "PICO_SBC_SENSE", "GND")
place(C2, "JP1", "SERVICE jumper", 130, 170, {"1": "+3V3_PICO", "2": "PICO_SERVICE"}, "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", "", "1x2 2.54mm pin header + jumper")
res("R9", "4.7k", 145, 172, "PICO_SERVICE", "GND")
res("R10", "1M", 160, 140, "VBAT_P", "PICO_VBAT_ADC", note="battery sense: 14.4V -> 2.6V")
res("R11", "220k", 160, 153, "PICO_VBAT_ADC", "GND")
cap("C9", "100n", 168, 153, "PICO_VBAT_ADC", "GND")

# ================================================================ SECTION 5: VIM3 interface
text("5. VIM3 INTERFACE (power key, reverse, backlight, light sensor, UART)", 190, 125, 2)
place(NMOS, "Q1", "AO3400A", 210, 150, {"D": "VIM3_PWR_KEY", "S": "GND", "G": "PWR_KEY_G"}, FP_SOT23, "C20917", "AO3400A 30V 5.7A N-MOSFET", note="open-drain press of the active-low VIM3 POWER key (GPIOAO_7)")
res("R12", "100", 195, 140, "PICO_PWR_BTN", "PWR_KEY_G")
res("R19", "100k", 197, 158, "PWR_KEY_G", "GND")
place(C2, "J5", "VIM3 POWER key lead", 235, 145, {"1": "VIM3_PWR_KEY", "2": "GND"}, "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", "", "JST-PH 2P (pick in library)",
      note="wire to the VIM3 power-key pad; not on the 40-pin header")
res("R20", "1k", 255, 140, "PICO_REV_OUT", "VIM3_REV", note="limits back-feed when VIM3 is off")
res("R21", "1k", 265, 140, "PICO_TX", "VIM3_UARTC_RX", note="optional Pico<->Android link")
res("R22", "1k", 275, 140, "VIM3_UARTC_TX", "PICO_RX")
res("R23", "100", 255, 162, "VIM3_BL_EN", "BL_EN")
res("R24", "100", 265, 162, "VIM3_BL_PWM", "BL_PWM")
place(C3, "J6", "Display backlight", 290, 165, {"1": "BL_EN", "2": "BL_PWM", "3": "GND"}, "Connector_JST:JST_PH_B3B-PH-K_1x03_P2.00mm_Vertical", "", "JST-PH 3P (pick in library)")
res("R25", "0", 255, 185, "VIM3_I2C_AO_SCL", "LUX_SCL", note="fit: BH1750 on I2C_AO (pins 25/26)")
res("R26", "0", 265, 185, "VIM3_I2C_AO_SDA", "LUX_SDA")
res("R27", "0", 275, 185, "VIM3_I2C_M3_SCL", "LUX_SCL", dnp=True, note="DNP: fit instead of R25/R26 for I2C_M3 (pins 22/23)")
res("R28", "0", 285, 185, "VIM3_I2C_M3_SDA", "LUX_SDA", dnp=True)
place(C4, "J7", "BH1750 light sensor", 305, 187, {"1": "VIM3_3V3", "2": "GND", "3": "LUX_SCL", "4": "LUX_SDA"}, "Connector_JST:JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical", "", "JST-PH 4P (pick in library)")

# VIM3 40-pin header. Khadas numbering: pins 1-20 in one row, 21-40 in the other, pin 1 opposite pin 21.
# A standard 2x20 IDC footprint numbers pads odd/even, so VIM3 pin v -> pad (2v-1) for v<=20, 2(v-20) for v>20.
vim3_sig = {1: "5V", 2: "5V", 3: "USB_DM", 4: "USB_DP", 5: "GND", 6: "VCC_MCU", 7: "MCU_NRST", 8: "MCU_SWIM", 9: "GND", 10: "ADC_CH0",
            11: "1V8", 12: "ADC_CH3", 13: "SPDIF_OUT", 14: "GND", 15: "UARTC_RX", 16: "UARTC_TX", 17: "GND", 18: "Linux_RX", 19: "Linux_TX", 20: "3V3",
            21: "GND", 22: "I2C_M3_SCL", 23: "I2C_M3_SDA", 24: "GND", 25: "I2C_AO_SCK", 26: "I2C_AO_SDA", 27: "3V3", 28: "GND", 29: "I2SB_SCLK",
            30: "I2S_MCLK0", 31: "I2SB_SDO", 32: "GPIOA_2", 33: "GPIOA_4", 34: "GND", 35: "PWM_F", 36: "RTC_CLK", 37: "GPIOH_4", 38: "MCU_PA1",
            39: "GPIODZ_15", 40: "GND"}
vim3_net = {5: "GND", 9: "GND", 14: "GND", 17: "GND", 21: "GND", 24: "GND", 28: "GND", 34: "GND", 40: "GND",
            20: "VIM3_3V3", 27: "VIM3_3V3", 15: "VIM3_UARTC_RX", 16: "VIM3_UARTC_TX", 22: "VIM3_I2C_M3_SCL", 23: "VIM3_I2C_M3_SDA",
            25: "VIM3_I2C_AO_SCL", 26: "VIM3_I2C_AO_SDA", 32: "VIM3_REV", 33: "VIM3_BL_EN", 35: "VIM3_BL_PWM", 37: "VIM3_GPIOH4"}
def pad(v): return 2 * v - 1 if v <= 20 else 2 * (v - 20)
VH = box_symbol("VIM3_40pin_IDC", [(pad(v), f"V{v}:{vim3_sig[v]}") for v in range(1, 21)],
                [(pad(v), f"V{v}:{vim3_sig[v]}") for v in range(21, 41)], width=30.48, ref="J", value="VIM3 40-pin (2x20 IDC)")
place(VH, "J2", "VIM3 40-pin via 2x20 IDC ribbon", 370, 160, {str(pad(v)): vim3_net.get(v) for v in range(1, 41)},
      "Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical", "", "2x20 2.54mm shrouded box header (pick in library)",
      note="pin names are VIM3 numbers (Vn); pad numbers are IDC odd/even")
text("VIM3 pin v -> IDC pad 2v-1 (v<=20) or 2(v-20) (v>20).", 312, 200)
text("VERIFY: VIM3 pin 1 sits opposite pin 21 on your board.", 300, 218)
text("Android side (device_khadas_vim3/vehicle.mk + kernel DT): pin 32 GPIOA_2 = reverse gear in, pin 33 GPIOA_4 = backlight enable,", 190, 270)
text("pin 35 PWM_F = backlight PWM (32.768kHz), I2C = BH1750 (bh1750d), POWER key GPIOAO_7 active-low = ACC wake/sleep.", 190, 274)

# PWR_FLAGs so ERC knows these nets are driven from connectors
def flag(net, x, y):
    power('PWR_FLAG', x, y, 90)
    label(net, x, y, 270)
    nets.setdefault(net, []).append(("#FLG", "1"))
flag("BATT_RAW", 20, 100); flag("ACC_RAW", 38, 100); power('PWR_FLAG', 56, 100, 90); power('GND', 56, 100, 270)
flag("+3V3_PICO", 74, 100); flag("PICO_VSYS", 92, 100); flag("VIM3_3V3", 110, 100)

text("Car radio peripheral board  -  generated from gschuurman vehicle_interfaces (android-16) mcu/main.py + device_khadas_vim3", 15, 285, 1.5)

# ---------------------------------------------------------------- write
sch = [S('kicad_sch'), [S('version'), 20230121], [S('generator'), S('eeschema')], [S('uuid'), ROOT], [S('paper'), "A3"],
       [S('title_block'), [S('title'), "Car radio peripheral board (Pico 2 + VIM3)"], [S('date'), "2026-09-28"], [S('rev'), "0.1"]],
       [S('lib_symbols')] + list(lib_symbols.values())] + items + \
      [[S('sheet_instances'), [S('path'), "/", [S('page'), "1"]]]]
open(f"{PROJECT}.kicad_sch", "w").write(dump(sch) + "\n")

with open(f"{PROJECT}_bom.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Value", "Description / MPN", "LCSC", "Footprint (KiCad name)", "Fit", "Note"])
    for b in bom:
        w.writerow([b['ref'], b['value'], b['mpn'], b['lcsc'], b['fp'], "DNP" if b['dnp'] else "yes", b['note']])

# sanity: every net needs >= 2 connections
bad = {n: v for n, v in nets.items() if len(v) < 2 and n != '(flag)'}
if bad:
    print("SINGLE-PIN NETS:", bad); sys.exit(1)
print("ok", len(bom), "parts", len(nets), "nets")
