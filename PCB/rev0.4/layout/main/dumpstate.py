"""Dump copper geometry + unconnected pairs (from a DRC json) for the host maze router.
usage: dumpstate.py board.kicad_pcb drc.json out.json"""
import pcbnew, sys, json
b = pcbnew.LoadBoard(sys.argv[1]); drc = json.load(open(sys.argv[2]))
L = {pcbnew.F_Cu: 'F', pcbnew.In1_Cu: 'In1', pcbnew.In2_Cu: 'In2', pcbnew.B_Cu: 'B'}
def polys(ps):
    out = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i); pts = [(o.CPoint(k).x / 1e6, o.CPoint(k).y / 1e6) for k in range(o.PointCount())]
        holes = []
        for h in range(ps.HoleCount(i)):
            hh = ps.Hole(i, h); holes.append([(hh.CPoint(k).x / 1e6, hh.CPoint(k).y / 1e6) for k in range(hh.PointCount())])
        out.append((pts, holes))
    return out
def geom(item):
    """list of (layer, kind, data)"""
    g = []
    if isinstance(item, pcbnew.PAD):
        for l, ln in L.items():
            if item.IsOnLayer(l) and item.IsOnCopperLayer():
                try: ps = item.GetEffectivePolygon(l, pcbnew.ERROR_INSIDE)
                except TypeError: ps = item.GetEffectivePolygon(pcbnew.ERROR_INSIDE)
                g.append((ln, 'poly', polys(ps)))
        if item.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            g.append(('*', 'hole', ((item.GetPosition().x / 1e6, item.GetPosition().y / 1e6), item.GetDrillSizeX() / 2e6)))
    elif isinstance(item, pcbnew.PCB_VIA):
        c = (item.GetPosition().x / 1e6, item.GetPosition().y / 1e6); r = item.GetWidth(pcbnew.F_Cu) / 2e6
        for ln in ('F', 'In1', 'In2', 'B'): g.append((ln, 'circle', (c, r)))
    elif isinstance(item, pcbnew.PCB_TRACK):
        g.append((L[item.GetLayer()], 'seg', ((item.GetStart().x / 1e6, item.GetStart().y / 1e6), (item.GetEnd().x / 1e6, item.GetEnd().y / 1e6), item.GetWidth() / 2e6)))
    elif isinstance(item, pcbnew.ZONE):
        for l in item.GetLayerSet().Seq():
            if l in L: g.append((L[l], 'poly', polys(item.GetFilledPolysList(l))))
    return g
items = []
for f in b.GetFootprints():
    for p in f.Pads():
        items.append(dict(net=p.GetNetname(), g=geom(p), id=p.m_Uuid.AsString(), ref=f.GetReference() + '.' + p.GetNumber()))
for t in b.GetTracks():
    items.append(dict(net=t.GetNetname(), g=geom(t), id=t.m_Uuid.AsString(), ref='via' if isinstance(t, pcbnew.PCB_VIA) else 'track', locked=t.IsLocked()))
for z in b.Zones():
    if z.GetIsRuleArea():
        items.append(dict(net='', keepout=dict(tracks=z.GetDoNotAllowTracks(), vias=z.GetDoNotAllowVias()), layers=[L[l] for l in z.GetLayerSet().Seq() if l in L],
                          g=[('*', 'poly', polys(z.Outline()))], id=z.m_Uuid.AsString(), ref='keepout'))
    elif z.GetNetname() == 'GND' and z.GetZoneName() in ('F GND', 'In2 GND', 'B GND', 'GND plane'):
        continue   # pours get refilled around new copper
    else:
        items.append(dict(net=z.GetNetname(), g=geom(z), id=z.m_Uuid.AsString(), ref='zone'))
nc = {}
for n in b.GetNetsByName().values() if hasattr(b, 'GetNetsByName') else []:
    pass
classes = {}
for name, ni in b.GetNetInfo().NetsByName().items():
    try: classes[str(name)] = ni.GetNetClass().GetName() if ni.GetNetClass() else 'Default'
    except Exception: classes[str(name)] = 'Default'
pairs = [[(it['uuid'], it['description']) for it in u['items']] for u in drc['unconnected_items']]
json.dump(dict(items=items, pairs=pairs, classes=classes, W=b.GetBoardEdgesBoundingBox().GetWidth() / 1e6), open(sys.argv[3], 'w'))
print('items', len(items), 'pairs', len(pairs))
