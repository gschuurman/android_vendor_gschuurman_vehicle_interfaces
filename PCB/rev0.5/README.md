# PCB rev 0.5: main board update

Rev 0.5 changes only the main board. The GNSS, audio and USB plug-in modules are unchanged; build them from `../rev0.4/`
(`gnss/`, `audio/`, `usb/`). Everything in `../rev0.4/README.md` (module stacking, header maps, GNSS notes, flashing,
hand soldering) still applies except where this file says otherwise.

| File | What |
|---|---|
| `main/carradio_peripheral_rev05.kicad_pcb` | routed main board, DRC 0 unconnected, no errors (warnings: silkscreen, unused fan-out stubs) |
| `main/carradio_peripheral_rev05.kicad_sch` / `.net` / `.pdf` | schematic (rev 0.4 with the expansion change below) |
| `main/carradio_peripheral_rev05_bom.csv` | BOM, same parts as rev 0.4 |
| `layout/main/` | scripts that made the changes (see `layout/README.md`) |
| `layout/schematic/gen5.py` | generator with the rev 0.5 pin map (see the note in `layout/README.md`) |

## Changes from rev 0.4

### 1. USB_UP (VIM3 to hub 1) is a real 90 Ω pair

USB_UP_DP/DM run from J2 (VIM3 header pins 7/5) to the CH334R hub U13 (pins 11/10, upstream port) at USB 2.0 high
speed. In rev 0.4 they were two unrelated single-ended tracks on In1/In2 (0.16 and 0.25 mm). Now:

- Edge-coupled pair on F.Cu over the solid In1 GND plane: 0.30 mm traces, 0.15 mm gap. That is about 90 Ω by the
  IPC-2141 estimate for the JLC04161H-7628 stack (outer prepreg about 0.21 mm, εr about 4.4). **Check this in JLCPCB's
  impedance calculator before ordering** and adjust width/gap if it disagrees; the USB net class now uses 0.30/0.15.
- DP 51.5 mm, DM 53.1 mm: 1.6 mm skew, about 10 ps, far inside the USB 2.0 budget.
- The pins are in mirrored order at the two ends, so DM's short stub at J2 runs on B.Cu under DP (one via). J2 is the
  uncontrolled ribbon end anyway.
- An In1 rule area "USB_UP reference" keeps tracks and vias out from under the pair, like the HDMI one.
- The IDC ribbon is not impedance controlled: keep it short. The GND pins next to header pins 5/7 help.

### 2. TPS560430 (U1, always-on +5V_AON buck) checked against the datasheet (TI SLVSE22B)

| Item | Datasheet | Board | OK |
|---|---|---|---|
| VIN range / abs max | 4-36 V / 38 V | VBAT_P behind SS34; SMBJ22A clamps at 35.5 V max | yes |
| EN | may be tied to VIN | tied to VIN (pin 4 on VBAT_P) | yes |
| Variant | X = 1.1 MHz PFM | TPS560430XDBVR | yes (PFM keeps the always-on light-load current low, IQ 80 µA) |
| VREF | 1.0 V ±1.5 % | R1 100k / R2 24k = **5.17 V** (5.06-5.28 V worst case) | yes, see note |
| Inductor (5 V, 1.1 MHz) | 18 µH, current rating above the 1.4 A max peak limit | SWPA4030S180MT 18 µH, Isat 1.4 A, Irms 1.1 A, 0.2 Ω | yes |
| COUT | 22 µF / 10 V (min about 8 µF effective) | C4 22 µF 25 V X5R 0805 | yes |
| CIN | ≥ 2.2 µF X5R/X7R, 2x VIN rating, plus 100 nF | C1 10 µF 50 V 1206, C2 100 nF 50 V | yes |
| CBOOT | 100 nF ≥ 16 V | C3 100 nF 50 V | yes |
| Load | 600 mA max | MCU + flash, GNSS LDO, hub 1, J10 pin 5: estimated 100-200 mA | yes |

Note on the output: 5.17 V (5.28 V worst case) suits the LDOs (AP2112K input up to 6 V, LP5907 recommended up to
5.5 V). I did not check the CH334R V5 limit; confirm it in its datasheet. For exactly 5.0 V use the datasheet pair
88.7k / 22.1k.

**Layout, the real problem:** in rev 0.4 the support parts sat far from U1 (C3 bootstrap 11 mm, input caps 9-17 mm,
feedback divider 17 mm, output cap C4 42 mm). Section 11 of the datasheet wants all of them tight at the pins. Rev 0.5
places C1/C2 at VIN/GND, C3 next to CB with a short link to L1's SW pad, R1/R2 next to FB, and C4 at L1's output, each
GND pad with its own via to the planes. R19 moved out of the way and D14 moved 0.15 mm down.

+5V_AON is now 0.5 mm wide over about 139 mm and at least 0.35 mm everywhere (rev 0.4: about 31 mm at 0.2 mm).

### 3. Fewer expansion pins (simpler MCU routing)

GPIO11, GPIO12, GPIO13, GPIO29 and GPIO34 are no longer broken out (no-connect on the RP2350B). That removes five
50-90 mm runs from the MCU across the board and frees five escape slots at the QFN. The expansion headers now carry:

J21 (1x10, under the USB module):

| Pin | rev 0.4 | rev 0.5 |
|---|---|---|
| 1 | +3V3_MCU | +3V3_MCU |
| 2 | EXP_GP34 | **LUX_SDA** (I2C1 SDA, shared with the light sensor bus) |
| 3 | EXP_GP29 | **LUX_SCL** (I2C1 SCL) |
| 4 | EXP_GP11 | not connected |
| 5 | EXP_GP12 | not connected |
| 6 | EXP_GP27 | EXP_GP27: SPI1 TX (MOSI) |
| 7 | EXP_GP26 | EXP_GP26: SPI1 SCK |
| 8 | EXP_GP25 | EXP_GP25: SPI1 CSn |
| 9 | EXP_GP24 | EXP_GP24: SPI1 RX (MISO) |
| 10 | GND | GND |

J10 (1x8): pins 1-7 unchanged (+3V3_MCU, EXP_GP32 / EXP_GP33 UART for the K-line board, EXP_GP28 general GPIO,
+5V_AON, GND, GND); pin 8 (was EXP_GP13) is not connected.

So the expansion offers one I2C bus, one full SPI port (its CS pin doubles as a GPIO), one UART and one free GPIO
(GPIO28; GPIO24-27 work as GPIO when SPI is not needed). The firmware pin table needs GPIO11/12/13/29/34 removed;
GPIO44-47 stay unused as before.

## Review items

- Check the USB pair width/gap in the JLCPCB impedance calculator (see 1).
- The MCU-area routes from rev 0.4 are grid-router output (stair-stepped). They pass DRC; tidy them in KiCad if you like.
- Parts may go on the bottom side if a later change needs room (Glenn, 2026-10-03); nothing needed it this time.
