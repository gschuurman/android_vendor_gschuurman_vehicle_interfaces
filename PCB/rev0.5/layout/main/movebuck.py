"""movebuck.py in out: rev 0.5 TPS560430 (U1) layout per the datasheet (SLVSE22B section 11): input caps C1/C2 at VIN/GND,
bootstrap C3 at CB, feedback divider R1/R2 at FB, output cap C4 at L1's output. In rev 0.4 they sat 9-42 mm away.
R19 moves out of C4's way, D14 0.15 mm down for C1. All copper of the touched nets is removed; the routers reconnect it."""
import pcbnew, sys
MM = pcbnew.FromMM
b = pcbnew.LoadBoard(sys.argv[1])
MOVE = {'C1': (8.5, 69.0, 180), 'C2': (11.4, 66.2, 90), 'C3': (5.3, 64.2, 90), 'R1': (5.3, 67.6, 90),
        'R2': (2.7, 70.1, 180), 'C4': (13.6, 59.6, 0), 'R19': (19.5, 59.25, 0),
        'D14': (8.5, 75.15, 90)}   # load-dump TVS down 0.15 mm to make room for C1; its tracks still land inside the pads
for ref, (x, y, r) in MOVE.items():
    f = b.FindFootprintByReference(ref); f.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); f.SetOrientationDegrees(r)
# unlocked copper of other nets under the new spots
boxes = []
for ref in MOVE:
    bb = b.FindFootprintByReference(ref).GetBoundingBox(False)
    boxes.append((bb.GetX() - MM(0.3), bb.GetY() - MM(0.3), bb.GetRight() + MM(0.3), bb.GetBottom() + MM(0.3)))
RIP = {'/BUCK_CB', '/BUCK_SW', '/BUCK_FB', '/VBAT_P', '/+5V_AON', '/PWR_KEY_G'}
n = 0; gone = []   # keep removed items referenced: freeing them corrupts the SWIG bindings
for t in list(b.GetTracks()):
    if t.GetNetname() in RIP: b.Remove(t); gone.append(t); n += 1
for t in list(b.GetTracks()):
    if t.IsLocked(): continue
    tb = t.GetBoundingBox(); x0, y0, x1, y1 = tb.GetX(), tb.GetY(), tb.GetRight(), tb.GetBottom()
    if any(x0 <= c and x1 >= a and y0 <= d and y1 >= bb for a, bb, c, d in boxes): b.Remove(t); gone.append(t); n += 1
pcbnew.ZONE_FILLER(b).Fill(b.Zones()); b.Save(sys.argv[2]); print('removed', n)
