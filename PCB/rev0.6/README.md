# PCB rev 0.6: main board with a K-line module socket

Rev 0.6 is rev 0.5 (`../rev0.5/`, kept as the reference) plus a socket for a stackable K-line module. The GNSS and
audio modules are the rev 0.4 boards (`../rev0.4/gnss|audio`); the USB module is `usb/` (rev 0.4 with the fix below). Everything in
`../rev0.5/README.md` (USB_UP pair, TPS560430 layout, expansion pins) and `../rev0.4/README.md` still applies except
J10, described here.

Everything to order and hand-assemble the four boards is in `order/` (see `order/ORDER_INSTRUCTIONS.md`); `fab/` holds
the same Gerbers plus JLC assembly BOM/CPL files in case of a PCBA order.

## USB module rev 0.6

`usb/carradio_usb_rev06.*` is the rev 0.4 USB module with solid zone connections on the GND pads of the 5 V / 3 A buck
U15 (LMR33630, pin 1 and the PowerPAD), the port switch U16 (TPS2561, pin 1 and the exposed pad) and C69. KiCad 10 had
flagged them as starved thermals. DRC: 0 unconnected, no errors.

## Impedance-controlled pairs (JLCPCB calculator)

JLCPCB's impedance calculator for JLC04161H-7628 (L1 over L2) gives 0.334 / 0.300 mm for 90 Ω and 0.2187 / 0.20 mm
for 100 Ω edge-coupled pairs. Rev 0.6 uses them:

- **USB_UP** (VIM3 to hub 1): re-routed at **0.32 mm / 0.30 mm gap** (rev 0.5: 0.30 / 0.15; the tight gap put it
  below 90 Ω). 0.32 instead of 0.334 so the pair fits the gap between U13's pins and the J23 socket; that is about 1 Ω
  higher. DP 51.3 mm, DM 53.2 mm. The In1 keep-out under it is 0.5 mm each side, opened at U13's pin escapes and for
  two vias beside the pair (`pairkeep.py` BUF / EXCLUDE_FP / EXCLUDE_XY).
- **HDMI** D0, D1, D2, CLK (J13 to J14): rebuilt by `hdmipairs.py` as coupled **0.2187 mm / 0.20 mm** pairs. Before
  they were 0.20 mm traces 0.80 mm apart (about 140 Ω, each trace closer to the neighbouring pair than to its partner).
  Each pair now runs centred over its GND pin with a short 45° jog at both connectors; P/N lengths match within 0.69 mm
  (about 5 ps).
- Net classes in the project: USB 0.32 / 0.30, HDMI 0.2187 / 0.20.

## J10: K-line module socket

In rev 0.5, J10 was a 1x8 male header under the USB module with no battery voltage. Now it is a **2x4 female socket,
8.5 mm tall** (same family as J23/J25/J27) at (82, 29) mm, in the free strip between the HDMI pairs and the USB module.
A K-line module stacks on it like the other modules: male header on its underside, about 11 mm above the main board,
held by one **M2 standoff at H8 (69.6, 18.5)**.

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | +3V3_MCU | 2 | GND |
| 3 | EXP_GP32: RP2350B UART TX (to the transceiver TXD) | 4 | EXP_GP33: UART RX (from RXD) |
| 5 | EXP_GP28: enable / sleep, or an L-line driver | 6 | GND |
| 7 | VBAT_KLINE: protected battery voltage through F6 | 8 | +5V_AON (if the transceiver wants 5 V) |

- **F6** (BHFUSE BSMD1206-020-30V, LCSC C883118, 200 mA hold / 460 mA trip) feeds pin 7 from VBAT_P (after the
  reverse-polarity diode and load-dump TVS). A fault on the module trips F6, not F1, so the always-on 5 V supply and
  the MCU keep running.
- **Module outline:** up to about 25 x 17 mm, over x 67-91, y 15-32 mm on the main board. That clears the HDMI
  connector J13 (top), the screen FPC J14 and its latch (right edge) and the USB module (below y 32.5). The parts under
  it are low SMD parts and the HDMI pairs, which the module only flies over. Socket pin 1 is at (78.19, 27.63).
- **Car side:** the module brings the K-line in through its own connector, e.g. a JST to the OBD-II socket
  (pin 7 K-line, pins 4/5 GND). Pin 16 is not needed because VBAT comes from J10 pin 7.
- **Transceiver:** a K-line part such as ST L9637D or a LIN transceiver such as TJA1021 (LIN is electrically close and
  often used for K-line at 10.4 kbaud). Check that TXD accepts 3.3 V logic and RXD is open-drain or 3.3 V compatible;
  pull RXD up to J10 pin 1.
- **Firmware:** UART on GPIO32/33 at 10.4 kbaud; for the ISO 9141 / KWP2000 slow init, switch GPIO32 to SIO and
  bit-bang the 5-baud address byte. GPIO28 drives enable/sleep.

The socket and standoff stay outside the HDMI corridor (In1 "HDMI reference" keep-out), so the HDMI ground reference
is untouched. J21 (SPI1 + I2C under the USB module) is unchanged from rev 0.5.

## Status

- Main board: DRC 0 unconnected, no errors (warnings: silkscreen, unused fan-out stubs); schematic parity same as rev 0.5.
- USB module rev 0.6: DRC 0 unconnected, no errors. GNSS module: clean. Audio module: one starved-thermal warning on
  the through-hole header J24 pin 3 (fine for hand soldering).
