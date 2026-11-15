import sys; sys.path.insert(0, '.')
from design import *
# PCB local (x from centre, ky from top edge) -> OpenSCAD: x, and "dy" = offset above cap_y = SW_Y - ky
f = lambda v: "%.3f" % v
o = ["// generated from bb4/design.py (button bar PCB v4) - do not edit by hand"]
o.append("pcb4_sw = [%s];" % ", ".join(f(x) for _, _, x, _ in BTNS))
o.append("pcb4_diodes = [%s];" % ", ".join("[%s, %s]" % (f(x), f(SW_Y - y)) for _, x, y, _, _, _ in diodes()))
o.append("pcb4_bh = [%s, %s];" % (f(BH_X), f(SW_Y - YC)))
o.append("pcb4_j = [[%s, 5], [%s, 4]];   // pin-1 x, pins" % (f(J1_X), f(J2_X)))
o.append("pcb4_j_dy = %s;   // pin row" % f(SW_Y - J_Y))
o.append("pcb4_m3 = [%s];" % ", ".join("[%s, %s]" % (f(x), f(SW_Y - y)) for x, y in HOLES))
o.append("pcb4_head = [%s];" % ", ".join("[%s, %s]" % (f(x), f(SW_Y - y)) for x, y in HEAD_HOLES))
open("pcb4_data.scad", "w").write("\n".join(o) + "\n"); print("\n".join(o))
