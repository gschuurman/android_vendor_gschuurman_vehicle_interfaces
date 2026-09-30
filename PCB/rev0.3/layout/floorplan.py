# Floorplan for rev 0.3. mm, origin top-left, y down. put_bb keywords: rot, left/right/cx, top/bottom/cy (courtyard based)
W, H = 109.0, 92.0
FIXED = [
    # ---- top edge: VIM3 ribbon, HDMI in, display
    ('J2',  dict(rot=90, left=1.0, top=0.5)),
    ('J13', dict(rot=180, left=62.5, top=0.5)),
    ('J14', dict(rot=180, left=82.5, top=0.3)),
    # ---- right edge: USB-A (RTL-SDR, two phone ports)
    ('J17', dict(rot=90, right=W + 0.55, top=22.5)),
    ('J19', dict(rot=90, right=W + 0.55, top=40.0)),
    ('J20', dict(rot=90, right=W + 0.55, top=57.5)),
    # ---- bottom edge: car loom, fuse, VIM3 power, line out, buttons, light sensor, power key
    ('J1',  dict(rot=0, left=1.0, bottom=H - 0.5)),
    ('F4',  dict(rot=90, left=18.8, bottom=H - 0.8)),
    ('J18', dict(rot=0, left=38.5, bottom=H - 0.5)),
    ('J8',  dict(rot=0, left=62.0, bottom=H - 0.5)),
    ('J12', dict(rot=0, left=77.0, bottom=H - 0.5)),
    ('J7',  dict(rot=0, left=90.5, bottom=H - 0.5)),
    ('J5',  dict(rot=0, left=102.0, bottom=H - 0.5)),
    # ---- left edge: GNSS antenna, expansion, SWD
    ('J21', dict(rot=0, left=0.5, top=31.0)),
    ('J22', dict(rot=0, left=0.5, top=58.0)),
    # ---- GNSS
    ('J11', dict(raw=(4.6, 20.0, 180))),
    ('U7',  dict(rot=0, left=8.2, top=11.5)),
    ('U6',  dict(rot=0, cx=25.0, cy=14.0)),
    ('Q2',  dict(rot=0, cx=25.0, cy=19.0)),
    ('Q3',  dict(rot=0, cx=25.0, cy=23.5)),
    # ---- opto inputs
    ('U2',  dict(rot=0, cx=13.0, cy=34.0)),
    ('U3',  dict(rot=0, cx=13.0, cy=40.5)),
    ('U4',  dict(rot=0, cx=13.0, cy=47.0)),
    ('U5',  dict(rot=0, cx=13.0, cy=53.5)),
    ('Q1',  dict(rot=0, cx=24.0, cy=61.0)),
    # ---- always-on 5V buck
    ('U1',  dict(rot=0, cx=8.5, cy=66.0)),
    # ---- VIM3 5V buck-boost
    ('Q10', dict(rot=0, cx=26.0, cy=74.5)),
    ('D14', dict(rot=90, cx=8.5, cy=75.0)),
    ('C48', dict(rot=0, cx=17.5, cy=66.5)),
    ('U12', dict(rot=0, cx=34.0, cy=66.0)),
    ('Q11', dict(rot=0, cx=29.0, cy=66.0)),
    ('Q12', dict(rot=0, cx=34.0, cy=61.0)),
    ('L3',  dict(rot=0, cx=45.3, cy=66.0)),
    ('R74', dict(rot=90, cx=56.0, cy=64.0)),
    ('C60', dict(rot=0, cx=57.4, cy=74.2)),
    ('TH1', dict(rot=0, cx=40.0, cy=74.5)),
    ('J10', dict(rot=90, left=38.0, top=78.3)),
    # ---- MCU
    ('U20', dict(rot=0, cx=45.0, cy=33.0)),
    ('U21', dict(rot=90, cx=33.0, cy=33.0)),
    ('Y3',  dict(rot=0, cx=45.0, cy=42.5)),
    ('U19', dict(rot=0, cx=37.0, cy=44.0)),
    ('SW1', dict(rot=0, cx=30.0, cy=45.0)),
    ('SW2', dict(rot=0, cx=30.0, cy=51.5)),
    ('JP1', dict(rot=90, cx=40.0, cy=50.5)),
    # ---- USB hubs + phone ports
    ('U13', dict(rot=0, cx=74.0, cy=30.0)),
    ('Y1',  dict(rot=0, cx=74.0, cy=36.0)),
    ('U14', dict(rot=0, cx=84.0, cy=47.0)),
    ('Y2',  dict(rot=0, cx=84.0, cy=53.0)),
    ('U17', dict(rot=0, cx=90.8, cy=47.0)),
    ('U18', dict(rot=0, cx=89.5, cy=63.5)),
    ('U16', dict(rot=0, cx=88.5, cy=69.0)),
    ('U15', dict(rot=0, cx=86.0, cy=76.0)),
    ('L4',  dict(rot=0, cx=97.0, cy=79.0)),
    # ---- audio
    ('U8',  dict(rot=0, cx=66.8, cy=66.0)),
    ('U9',  dict(rot=0, cx=76.8, cy=66.0)),
    ('U10', dict(rot=0, cx=66.8, cy=74.5)),
    ('U11', dict(rot=0, cx=76.8, cy=74.5)),
]
# no auto-placed parts here: the HDMI fan-out under J13/J14
KEEPOUT = [(62.5, 5.5, 100.5, 22.0)]
HOLES = []
