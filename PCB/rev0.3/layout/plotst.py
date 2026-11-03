"""plotst.py state.json x0 y0 x1 y1 out.png [hilite nets comma]"""
import json, sys, matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle
st = json.load(open(sys.argv[1])); x0, y0, x1, y1 = map(float, sys.argv[2:6]); out = sys.argv[6]
hl = set(sys.argv[7].split(',')) if len(sys.argv) > 7 else set()
LAYS = (sys.argv[8].split(",") if len(sys.argv) > 8 else ["F","In2","B"])
fig, axs = plt.subplots(1, len(LAYS), figsize=(14*len(LAYS), 14*(y1-y0)/(x1-x0)), squeeze=False); axs = axs[0]
cols = {}
import hashlib
def col(n):
    if n == 'GND': return '#bbbbbb'
    h = int(hashlib.md5(n.encode()).hexdigest()[:6], 16)
    return '#%06x' % (h | 0x404040)
for ax, L in zip(axs, LAYS):
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_aspect('equal'); ax.set_title(L)
    for it in st['items']:
        if 'keepout' in it: continue
        n = it['net']; c = col(n); a = 1.0 if (not hl or n in hl) else 0.35
        for l, k, d in it['g']:
            if l not in (L, '*'): continue
            if k == 'poly':
                for pts, holes in d:
                    if not pts: continue
                    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                    if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1: continue
                    ax.add_patch(Polygon(pts, fc=c, ec='k', lw=0.3, alpha=a * (0.5 if it['ref'] == 'zone' else 0.9)))
                    for h in holes: ax.add_patch(Polygon(h, fc='white', ec='none'))
                    if it['ref'] not in ('zone',) and x0 < xs[0] < x1 and y0 < ys[0] < y1:
                        ax.text(sum(xs) / len(xs), sum(ys) / len(ys), it['ref'] + '\n' + n.strip('/')[:9], fontsize=7, ha='center', va='center')
            elif k == 'seg':
                (a1, b1), (a2, b2), r = d
                if max(a1, a2) < x0 or min(a1, a2) > x1 or max(b1, b2) < y0 or min(b1, b2) > y1: continue
                ax.plot([a1, a2], [b1, b2], color=c, lw=r * 2 * 72 * 11 / (y1 - y0) / 25.4 * 25.4 * 0.95, solid_capstyle='round', alpha=a)
            elif k == 'circle':
                (cx, cy), r = d
                if x0 < cx < x1 and y0 < cy < y1: ax.add_patch(Circle((cx, cy), r, fc=c, ec='k', lw=0.4, alpha=a))
            elif k == 'hole':
                (cx, cy), r = d
                if x0 < cx < x1 and y0 < cy < y1: ax.add_patch(Circle((cx, cy), r, fc='white', ec='k', lw=0.4))
    ax.grid(True, lw=0.2)
plt.tight_layout(); plt.savefig(out, dpi=110)
