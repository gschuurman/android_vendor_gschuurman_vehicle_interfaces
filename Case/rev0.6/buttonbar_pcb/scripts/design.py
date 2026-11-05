# Shared design data for the button-bar strip (bar coordinates: x from bar centre, front view)
L, H = 176.7, 11.5          # strip size (matches the case grooves)
SW_Y = 6.4                  # switch row, from the top edge (cap centre)
D_UP, D_DN = 2.4, 9.7       # diode rows above / below the switches
LINES = {"S": "/BTN_SCREEN", "U": "/BTN_VOLUP", "D": "/BTN_VOLDN", "M": "/BTN_MUTE"}
# (ref, label, x, lines)
BTNS = [("SW1", "Home",       -78.74, "SD"),
        ("SW2", "Vol -",      -58.42, "D"),
        ("SW3", "Mute",       -45.72, "M"),
        ("SW4", "Vol +",      -33.02, "U"),
        ("SW5", "Screen off",   0.00, "S"),
        ("SW6", "Prev",        33.02, "DM"),
        ("SW7", "Play/Pause",  45.72, "UD"),
        ("SW8", "Next",        58.42, "UM"),
        ("SW9", "Voice",       78.74, "SU")]
J1_X = -11.0                # wire pads / header to J12 (pin 1..5 = J12 pin 1..5)
J1_PINS = ["S", "U", "D", "M", "GND"]
def node(ref): return "/N_" + ref
def diodes():
    out = []; n = 1
    for ref, lab, x, ls in BTNS:
        if len(ls) == 2:
            for k, (l, y) in enumerate(zip(ls, (D_UP, D_DN))):
                out.append(("D%d" % n, x, y, LINES[l], node(ref), lab)); n += 1
    return out
