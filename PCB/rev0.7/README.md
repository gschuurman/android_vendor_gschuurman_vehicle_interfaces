# PCB rev 0.7: two-camera capture

Rev 0.7 only changes the USB module and adds a capture module, in two versions: `capture_1cam/` (one camera)
and `capture_2cam/` (two cameras). Both plug into the same J29 socket on the USB module; build one of them. The main, audio and
GNSS boards stay at rev 0.6.

## Two-camera capture module (`capture_2cam/`)

Two MacroSilicon MS2107 (LCSC C42374499, LQFP-48), one per camera: analog CVBS in, USB 2.0 UVC out,
behind a CH334R 4-port hub (U10, C4154405) so both share the USB module's single J29 port. Android sees two
normal external cameras (default VID:PID 534d:0021 each), so no driver is needed. The RearViewCamera app
currently opens the first external camera; it needs a setting (or a USB-path match) to pick the reverse one.

- 36 x 67.5 mm, 2 layers. Same outline and H1 as the USB module, extended 12.5 mm downward to the main board's
  bottom edge (the USB module's right edge is already the main board edge).
- J1 (CAM1) and J101 (CAM2): JST PH 2-pin video in (1 = CVBS, 2 = GND), each with 75 ohm termination, 47 nF
  coupling and a USBLC6 ESD clamp.
- J2: 2x3 2.54 mm male header on the bottom side, plugs into USB module J29 and feeds the hub upstream.
- Hub port 1 camera 1, port 2 camera 2, port 3 to J3 (1x4 pads, not fitted: 5 V, D-, D+, GND) for an
  optional third capture board or a test device, port 4 unused.
- Each channel: 12 MHz crystal, internal LDOs, status LED (D1/D101). EEPROMs U3/U103 and R5/R105 are DNP and
  sit on the underside; fit one only to give a camera its own USB name/IDs (ms-tools).
- Routed, DRC 0 unconnected, no copper errors (silkscreen warnings only; H1 is a board-only part).
- Each camera's own 12 V still comes from the reverse-lamp (or other) feed, not from this board.

### How many cameras

Each MS2107 sends uncompressed YUV, about 21 MB/s per PAL/NTSC camera. Everything shares the VIM3 header's
single USB 2.0 High Speed link, which can reserve about 48 MB/s for video, so two cameras can stream at once
(about 41 MB/s) with the RTL-SDR (about 5 MB/s, bulk) still fitting. A third camera on J3 only works if it does
not stream at the same time as the other two. These are calculated numbers, not measured.

### USB pair lengths (mm)

| Pair | D+ | D- |
|---|---|---|
| J2 to hub (upstream; D+ hand-routed on B.Cu between the J2 GND pins) | 12.6 | 10.4 |
| hub to camera 1 | 33.1 | 32.3 |
| hub to camera 2 | 57.1 | 64.8 |
| hub to J3 (not fitted) | 33.2 | 39.0 |

On the USB module D+ is already about 12.7 mm longer than D- (hub 2 to J29), so the upstream skew is about
15 mm in total. Fine for USB 2.0 High Speed in practice; a meander would tidy it if wanted.

## Single-camera capture module (`capture_1cam/`)

The first rev 0.7 board: one MS2107 wired straight to J2, no hub. 36 x 55 mm, the USB module's exact outline.
Same input circuit (J1 JST PH, 75 ohm, 47 nF, USBLC6), optional EEPROM U3/R5 (DNP) on the top side, status
LED D1. Routed, DRC 0 unconnected, no copper errors. USB pair J2 to MS2107: D+ 14.0 mm, D- 10.7 mm; with the
USB module that is about 16 mm of skew in total. Draws about 0.2 A; the 1.1 A F7 covers it too.

## USB module change (`usb/`)

- J29 2x3 female socket (CJT A2541HWV-2x3P, C239343, 8.5 mm body): 1/2 +5V_CAP, 3 D+, 4 D-, 5/6 GND. Wired
  to hub 2 (U14 CH334R) port 4, which was unused. Hub 2 is now full (two phone ports, SDR, capture).
- F7 1.1 A PTC (Bourns MF-NSMF110-2, C89654) feeds +5V_CAP from +5V_SYS, so the capture board only has power
  while the VIM3 is on. Load: hub + two MS2107, about 0.5 A.
- One B.Cu GND track near J29 removed; GND still reaches everything via the pours.
- DRC 0 unconnected, no copper errors. All rev 0.6 symbol UUIDs unchanged.

## Stack

The capture board sits about 11 mm above the USB module (8.5 mm socket + 2.5 mm header spacer), clear of the
USB-A sockets. Use an M2.5 x 11 standoff at H1 on top of the USB module's H1 standoff. Check the USB-A socket
height on the real parts before ordering. The extra 12.5 mm overhangs the main board's bottom strip above the
display-button (J12) and light-sensor (J7) plugs, about 22 mm up; leave room for their wires to bend.

## Regenerating

- `layout/capture_gen_1cam.py` / `capture_gen_2cam.py` write the capture schematics and BOMs (2cam: one `channel(k)`
  per camera, nets CAMk_*, refs +100 for camera 2). Run them inside the matching folder.
- `layout/gen7.py usb` writes the USB module schematic (new parts appended at the end
  so rev 0.6 UUIDs stay put).
- `layout/usb07.py` / `usb07_post.py` and `capture_pcb_1cam.py` / `capture_pcb_2cam.py` / `capture_post.py` do
  placement and post-Freerouting cleanup (KiCad 10 pcbnew Python).

## Bring-up wizards

Step-by-step bench wizards (multimeter first, then first power): `usb/WIZARD.html`, `audio/WIZARD.html`,
`capture_1cam/WIZARD.html` and `capture_2cam/WIZARD.html`. See `../wizard/README.md`.
