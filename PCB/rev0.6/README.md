# PCB rev 0.6: main board with a K-line module socket

Rev 0.6 is rev 0.5 (`../rev0.5/`, kept as the reference) plus a socket for a stackable K-line module. Only the main
board changes; the GNSS, audio and USB modules are the rev 0.4 boards (`../rev0.4/gnss|audio|usb`). Everything in
`../rev0.5/README.md` (USB_UP pair, TPS560430 layout, expansion pins) and `../rev0.4/README.md` still applies except
J10, described here.

Order files for all four boards are in `fab/` (see `fab/README.md`).

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
- Module boards (rev 0.4): 0 unconnected. KiCad 10's DRC reports "starved thermal" errors there (fewer thermal spokes
  than the minimum on some GND pads): audio J24 pin 3; USB module U15 pin 9, U16 pins 1/11 and C69 pin 2. The pads
  are connected, but U16 is the module's 5 V / 3 A buck, so its GND pins should get solid zone connections before
  ordering. They are not changed here.
