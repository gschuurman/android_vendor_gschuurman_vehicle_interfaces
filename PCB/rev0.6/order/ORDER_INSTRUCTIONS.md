# Car radio rev 0.6: JLCPCB order

Four boards, one folder each. Every folder has the same four files:

| File | Upload where |
|---|---|
| `*_gerbers.zip` | PCB order page, "Add gerber file" |
| `*_bom.csv` | PCB Assembly step, "BOM file" |
| `*_cpl.csv` | PCB Assembly step, "CPL file" |
| `*_schematic.pdf` | not uploaded; reference for checking parts |

| Folder | Board | Size | Layers |
|---|---|---|---|
| `main/` | main board rev 0.6 | 100 x 100 mm | 4 |
| `gnss/` | GNSS module rev 0.4 | 26.5 x 31.5 mm | 2 |
| `audio/` | audio module rev 0.4 | 36.5 x 41 mm | 2 |
| `usb/` | USB module rev 0.4 | 36 x 55 mm | 2 |

Order each board as its own item (four uploads), then check out together.

## 1. Main board (`main/`)

1. Upload `carradio_main_rev06_gerbers.zip`. JLC should detect 4 layers and 100 x 100 mm.
2. PCB options:
   - Base material FR-4, layers **4**, thickness **1.6 mm**
   - **Impedance control: Yes**, layer stack-up **JLC04161H-7628**
   - Outer copper 1 oz, inner copper 0.5 oz
   - Via covering: tented
   - Min via hole size / diameter: pick the option that allows **0.2 mm holes / 0.45 mm pads** (the board's vias)
   - Surface finish: **ENIG** (recommended: 0.4 mm QFN, 0.5 mm FPC connector)
   - Mark on PCB: your choice ("Remove mark" or "specify a location")
3. PCB Assembly: on, **top side**, "Economic" or "Standard" (Standard if JLC asks for it because of the QFN/VQFN parts).
4. Upload `carradio_main_rev06_bom.csv` and `carradio_main_rev06_cpl.csv`.
5. On the parts page:
   - **J10** (2x4 female socket) and **J27** (2x8 female socket) have no part number: set them to "do not place" and
     hand-solder them, or pick an equivalent 2.54 mm, 8.5 mm tall socket from JLC's library.
   - **J23, J25** use BOOMELE C30867 (2x10 female, 8.5 mm). It was out of stock on 2026-10-01; any 2x10 2.54 mm 8.5 mm
     socket fits, or hand-solder.
   - **U20 RP2350B** (C42415655): if out of stock, the RP2354B (C39843328) has internal flash; then leave U21 unfitted.
   - Fix any other part JLC marks as missing or out of stock with an equivalent (same value, package and rating).
6. On the placement preview, **check the rotation of every IC, transistor, diode and connector** (pin 1 dots,
   polarity marks). KiCad and JLC disagree on the zero angle of some footprints; rotate in the preview where needed.
7. JP2 is a solder jumper made of copper, not a part. It ships bridged 1-2 (GNSS RX from the VIM3).

## 2. GNSS module (`gnss/`)

1. Upload `carradio_gnss_rev04_gerbers.zip`: 2 layers, 1.6 mm, 1 oz, HASL or ENIG.
2. Optional before ordering: check the 1.0 mm RF trace (U.FL to the NEO-M9N) against JLC's impedance calculator for
   50 Ω on a 2-layer 1.6 mm board.
3. PCB Assembly: top side, upload `carradio_gnss_rev04_bom.csv` and `carradio_gnss_rev04_cpl.csv`.
4. **J28** (2x8 male header) has no part number: "do not place", hand-solder it on the **bottom** side, pins pointing
   down.

## 3. Audio module (`audio/`)

1. Upload `carradio_audio_rev04_gerbers.zip`: 2 layers, 1.6 mm, 1 oz, HASL or ENIG.
2. PCB Assembly: top side, upload `carradio_audio_rev04_bom.csv` and `carradio_audio_rev04_cpl.csv`.
3. The header J24 is on the bottom side: if JLC does not place it, hand-solder it, pins pointing down.

## 4. USB module (`usb/`)

1. Upload `carradio_usb_rev04_gerbers.zip`: 2 layers, 1.6 mm, 1 oz, HASL or ENIG.
2. PCB Assembly: top side, upload `carradio_usb_rev04_bom.csv` and `carradio_usb_rev04_cpl.csv`.
3. The header J26 is on the bottom side: if JLC does not place it, hand-solder it, pins pointing down.

## Open points to decide before paying

- **USB module U16 (5 V / 3 A buck):** KiCad 10 flags "starved thermal" on its GND pins 1 and 11 (also U15 pin 9 and
  C69 pin 2; on the audio module J24 pin 3). They are connected, but with fewer thermal spokes than the rule wants.
  Solid connections on U16's GND pins are advisable for a 3 A converter; ask for that fix before ordering the USB module
  if you want it.
- **USB_UP pair on the main board:** confirm in JLC's impedance calculator that 0.30 mm traces with a 0.15 mm gap give
  about 90 Ω on JLC04161H-7628.
- **Hub supply:** the always-on buck makes 5.17 V; check the CH334R's V5 limit in its datasheet (all other loads are
  fine).

## After delivery

- Hand-solder the sockets/headers left out of assembly (J10, J27, J28, and J23/J25/J24/J26 if not placed).
- Standoffs: M2.5 x 11 mm for the GNSS, audio and USB modules, M2 x 11 mm for a future K-line module (H8).
- Flash the RP2350B over USB (hold SW1, tap SW2) or SWD on J22; see `../../rev0.4/README.md`, "Flashing the RP2350B".
