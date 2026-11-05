import pcbnew, sys, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle, FancyBboxPatch
b = pcbnew.LoadBoard(sys.argv[1]); out = sys.argv[2]
mm = pcbnew.ToMM; OX = 100 + 88.35; OY = 100
fig, ax = plt.subplots(figsize=(24, 2.6), dpi=130)
ax.add_patch(Rectangle((-88.35, 0), 176.7, 11.5, fc="#1d5e3a", ec="k", lw=1))
layers = [(pcbnew.B_Cu, "#5aa9e6", 0.85), (pcbnew.F_Cu, "#e05a4f", 0.9)]
for lay, col, a in layers:
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetLayer() == lay:
            s, e = t.GetStart(), t.GetEnd()
            ax.plot([mm(s.x)-OX, mm(e.x)-OX], [mm(s.y)-OY, mm(e.y)-OY], color=col, lw=mm(t.GetWidth())*130/25.4*72/130*1.0*2.2, solid_capstyle="round", alpha=a)
for fp in b.GetFootprints():
    ref = fp.GetReference(); p = fp.GetPosition()
    if ref.startswith("SW"):
        ax.add_patch(Rectangle((mm(p.x)-OX-3, mm(p.y)-OY-1.75), 6, 3.5, fc="none", ec="#f5f5f5", lw=1, ls="--"))
    if ref.startswith("D"):
        pads = list(fp.Pads()); x1 = mm(pads[0].GetPosition().x)-OX; x2 = mm(pads[1].GetPosition().x)-OX; y = mm(p.y)-OY
        ax.add_patch(Rectangle((min(x1, x2)+2.3, y-0.8), abs(x2-x1)-4.6, 1.6, fc="#c87f3a", ec="none", alpha=0.8))
        kx = min(x1, x2)+2.3+0.4 if pads[0].GetPosition().x < pads[1].GetPosition().x else max(x1, x2)-2.7
        ax.add_patch(Rectangle((kx, y-0.8), 0.4, 1.6, fc="k"))
    for pad in fp.Pads():
        q = pad.GetPosition(); r = mm(pad.GetSize().x)/2
        ax.add_patch(Circle((mm(q.x)-OX, mm(q.y)-OY), r, fc="#d4af37", ec="none"))
        ax.add_patch(Circle((mm(q.x)-OX, mm(q.y)-OY), mm(pad.GetDrillSize().x)/2, fc="#111", ec="none"))
    ax.text(mm(p.x)-OX, (mm(p.y)-OY) + (2.6 if ref.startswith("SW") else -1.1), ref, color="w", fontsize=6, ha="center", va="center")
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        q = t.GetPosition(); ax.add_patch(Circle((mm(q.x)-OX, mm(q.y)-OY), 0.5, fc="#ddd", ec="k", lw=0.5))
ax.set_xlim(-89.5, 89.5); ax.set_ylim(12.2, -0.7); ax.set_aspect("equal"); ax.axis("off")
ax.set_title(sys.argv[3] if len(sys.argv) > 3 else "", fontsize=10, loc="left")
plt.savefig(out, bbox_inches="tight", facecolor="white"); print("saved")
