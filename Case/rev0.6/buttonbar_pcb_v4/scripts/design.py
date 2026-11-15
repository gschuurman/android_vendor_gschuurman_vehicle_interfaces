# Button bar v4 (2026-11-15): one 2-layer PCB, switches + SS14 diodes + BH1750 module + 2x JST PH.
# Coordinates: x from bar centre (front view, = KiCad top view), y from the PCB top edge downward.
L, H = 176.7, 11.5
SW_Y = 6.4                  # switch row (cap centre), 0.65 below the board centre
YC = H / 2
D_UP, D_DN = 1.55, 10.0     # SS14 rows on the back, above / below the switch row
LINES = {"S": "/BTN_SCREEN", "U": "/BTN_VOLUP", "D": "/BTN_VOLDN", "M": "/BTN_MUTE"}
BTNS = [("SW1", "Home",       -78.74, "SD"),
        ("SW2", "Vol -",      -60.96, "D"),
        ("SW3", "Mute",       -48.26, "M"),
        ("SW4", "Vol +",      -35.56, "U"),
        ("SW5", "Screen off",   0.00, "S"),
        ("SW6", "Prev",        35.56, "DM"),
        ("SW7", "Play/Pause",  48.26, "UD"),
        ("SW8", "Next",        60.96, "UM"),
        ("SW9", "Voice",       78.74, "SU")]
D_SHIFT = {"SW1": 1.5, "SW9": -1.5}       # keep the end diodes clear of the M3 standoffs
BH_X = -14.0                # BH1750 module centre (light window in the bar)
J1_X, J2_X = 7.8, 22.0      # pin 1 x of the JST headers (back side): J1 -> main board J12, J2 -> J7
J_Y = YC + 0.55             # pin row so the 4.5 mm housing is centred on the board
HOLES = [(-86.0, 2.5), (-26.8, SW_Y), (86.0, 2.5)]   # M3 countersunk (ends above the switch row: clear of the home/voice legs)
J1_PINS = ["/BTN_SCREEN", "/BTN_VOLUP", "/BTN_VOLDN", "/BTN_MUTE", "GND"]   # = J12 pin 1..5
J2_PINS = ["/+3V3", "GND", "/LUX_SCL", "/LUX_SDA"]                            # = J7 pin 1..4
BH_PINS = {"1": None, "2": "GND", "3": "GND", "4": None,                      # 3V3 out (NC), ADDR->GND, GND, NC
           "5": "/+3V3", "6": "GND", "7": "/LUX_SCL", "8": "/LUX_SDA"}        # VCC, GND, SCL, SDA
def node(ref): return "/N_" + ref
def diodes():
    out = []; n = 1
    for ref, lab, x, ls in BTNS:
        if len(ls) == 2:
            for l, y in zip(ls, (D_UP, D_DN)):
                out.append(("D%d" % n, x + D_SHIFT.get(ref, 0), y, LINES[l], node(ref), lab)); n += 1
    return out
HEAD_HOLES = [(-69.85, 7.6), (69.85, 7.6)]   # 6.6 holes: the cap-plate screw ears (M3 countersunk) reach through the PCB
