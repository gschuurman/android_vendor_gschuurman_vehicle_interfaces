"""plot2.py board x0 y0 x1 y1 out.png : 2x2 panels F/In1/In2/B. GND copper green, pours light green, other nets red, vias blue."""
import pcbnew, sys
from PIL import Image, ImageDraw
T = pcbnew.ToMM
b = pcbnew.LoadBoard(sys.argv[1]); x0, y0, x1, y1 = map(float, sys.argv[2:6]); S = 40
LAY = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
W, H = int((x1 - x0) * S), int((y1 - y0) * S)
img = Image.new('RGB', (W * 2 + 10, H * 2 + 10), 'white'); d = ImageDraw.Draw(img)
for li, l in enumerate(LAY):
    ox, oy = (li % 2) * (W + 10), (li // 2) * (H + 10)
    def P(x, y): return (ox + (x - x0) * S, oy + (y - y0) * S)
    d.rectangle([ox, oy, ox + W, oy + H], fill='black')
    for z in b.Zones():
        if not z.IsOnLayer(l) or z.GetIsRuleArea(): continue
        fp = z.GetFilledPolysList(l)
        for i in range(fp.OutlineCount()):
            o = fp.Outline(i); pts = [P(T(o.CPoint(k).x), T(o.CPoint(k).y)) for k in range(o.PointCount())]
            if len(pts) > 2: d.polygon(pts, fill=(40, 110, 40) if z.GetNetname() == 'GND' else (110, 80, 40))
    for f in b.GetFootprints():
        for p in f.Pads():
            if not p.IsOnLayer(l): continue
            bb = p.GetBoundingBox(); d.rectangle([P(T(bb.GetX()), T(bb.GetY())), P(T(bb.GetRight()), T(bb.GetBottom()))], fill=(0, 220, 0) if p.GetNetname() == 'GND' else (200, 0, 200))
    for t in b.GetTracks():
        g = t.GetNetname() == 'GND'
        if isinstance(t, pcbnew.PCB_VIA):
            p = t.GetPosition(); r = 0.225 * S; cx, cy = P(T(p.x), T(p.y)); d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 255, 0) if g else (80, 80, 255))
        elif t.GetLayer() == l:
            d.line([P(T(t.GetStart().x), T(t.GetStart().y)), P(T(t.GetEnd().x), T(t.GetEnd().y))], fill=(0, 255, 0) if g else (230, 40, 40), width=max(1, int(T(t.GetWidth()) * S)))
    d.text((ox + 4, oy + 4), ['F', 'In1', 'In2', 'B'][li], fill='white')
img.save(sys.argv[6])
