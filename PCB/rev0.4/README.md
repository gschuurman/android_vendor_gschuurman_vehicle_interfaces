# PCB rev 0.4: main board plus three plug-in modules

Rev 0.4 splits rev 0.3 into four boards so each one fits the JLCPCB 100 x 100 mm price tier, and spreads
the parts out for hand soldering (at least 0.8 mm between courtyards on every board).

| Board | Folder | Size | Layers | Holds |
|---|---|---|---|---|
| Main | `main/` | 100 x 100 mm, four M3 holes 4.5 mm in from each corner | 4 | RP2350B, TPS55288 VIM3/screen supply, always-on buck, car inputs, GNSS 3.3 V LDO, hub 1, HDMI-to-FPC screen adapter, loom connectors |
| GNSS module | `gnss/` | 26.5 x 31.5 mm | 2 | u-blox NEO-M9N, U.FL antenna receptacle with active-antenna feed, USB series resistors |
| Audio module | `audio/` | 36.5 x 41 mm | 2 | 2x PCM5102A, 2 LDOs, output filters |
| USB module | `usb/` | 36 x 55 mm (USB-A shells stick out 0.55 mm on the right) | 2 | Hub 2, two phone ports (LMR33630 5V/3A, TPS2561 limits, ESD), RTL-SDR USB-A socket |

Each board has its own schematic, PCB, PDF, netlist and BOM. **Status 2026-10-02: the three modules are routed (DRC clean); the main board is placed with the HDMI and TPS55288 copper in place, and its signal routing is still in progress.** All four come from `gen4.py` (`python3 gen4.py main|gnss|audio|usb`).

## Changes since the first rev 0.4 draft

- The NEO-M9N moved from the main board onto its own swappable GNSS module (Glenn, 2026-10-02). The antenna plugs into a
  U.FL receptacle J11 (Hirose U.FL-R-SMT-1, LCSC C88374); use a U.FL-to-SMA bulkhead pigtail to reach the car antenna.
- The GNSS module gets both USB and UART:
  - USB goes to hub 1 port 3 (it shows up as a CDC-ACM serial port, `/dev/ttyACM*`).
  - UART TX goes to the VIM3 UART_C RX (header pin 15) through R100 and to the RP2350B.
  - UART RX is driven by the VIM3 UART_C TX (header pin 16, through R101) or by the RP2350B, picked with
    solder jumper JP2: 1-2 VIM3 (default, bridged), 2-3 MCU. Cut the 1-2 trace and bridge 2-3 to hand GNSS
    config to the MCU.
- The RTL-SDR socket moved from hub 1 to hub 2 on the USB module, so USB module header pins 9 and 11 are now unused.
- J18 (VIM3 power, JST-XH) and J5 (power-on lead) now sit right below the VIM3 40-pin header at the top left.
- Parts now sit under the modules (MCU, hub 1, GNSS LDO, J21/J10), which freed space for wider spacing.
- Hub 1 (U13) now runs from the always-on +5V_AON instead of +5V_SYS, with a 10k pull-up (R104) on its reset pin.
  A blank RP2350B therefore enumerates as soon as 12V is applied, so the first flash works over USB (Glenn, 2026-10-02).

## How the modules stack

- The main board carries female sockets (8.5 mm tall): J27 (2x8) for GNSS, J23 (2x10) for audio, J25 (2x10) for USB.
- Each module has a male header (J28, J24, J26) **soldered on its underside**, pins pointing down. In KiCad the
  header footprint sits on the bottom layer, so pin n of the header lands on pin n of the socket.
- Each module PCB sits about 11 mm above the main board. Everything under a module is a low SMD part.
- One M2.5 standoff (11 mm) per module, at the far side from its header. Main-board positions:

| Module | Covers main board (x, y in mm) | Standoff hole on main |
|---|---|---|
| GNSS | 0-26.5, 19-50.5 | (3.2, 34.3) |
| Audio (turned 90°) | 27-63.5, 13-54 | (31.0, 16.5) |
| USB | 64-100, 32.5-87.5 (USB-A sockets on the right edge) | (67.8, 83.7) |

- J21 and J10 (main board headers) are under the USB module: unplug the module to reach them.
- SW1, SW2, JP1, Q2 and Q3 sit in the open strip between the audio and USB modules.

## Header pin maps

GNSS (J27 on main, J28 on module):

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | +3V3_GNSS (switched by the MCU) | 2 | +3V3_GNSS |
| 3 | GND | 4 | +3V3_MCU (NEO V_BCKP, keeps hot start) |
| 5 | not connected | 6 | GND |
| 7 | GNSS_USB_DP | 8 | GNSS_TXD |
| 9 | GNSS_USB_DM | 10 | GNSS_RXD |
| 11 | GND | 12 | GND |
| 13 | GNSS_RST | 14 | GNSS_PPS |
| 15 | GNSS_SAFEBOOT | 16 | GND |

Audio (J23 on main, J24 on module):

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | VIM3_5V | 2 | VIM3_5V |
| 3 | GND | 4 | GND |
| 5 | I2S_BCLK | 6 | GND |
| 7 | I2S_LRCK | 8 | VIM3_I2S_MCLK (spare) |
| 9 | I2S_DOUT0 | 10 | I2S_DOUT1 |
| 11 | VIM3_I2S_DOUT2 (spare) | 12 | DAC_XSMT |
| 13 | LUX_SCL (spare) | 14 | LUX_SDA (spare) |
| 15 | GND | 16 | GND |
| 17 | LINE_FL | 18 | LINE_FR |
| 19 | LINE_RL | 20 | LINE_RR |

USB (J25 on main, J26 on module):

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | VSYS_IN (12V, for the 5V/3A buck) | 2 | VSYS_IN |
| 3 | GND | 4 | GND |
| 5 | +5V_SYS | 6 | +5V_SYS |
| 7 | GND | 8 | GND |
| 9 | not connected (was SDR) | 10 | HUB2_UP_DP |
| 11 | not connected (was SDR) | 12 | HUB2_UP_DM |
| 13 | GND | 14 | GND |
| 15 | MCU_USBP_PG | 16 | VIM3_PWR_EN |
| 17 | MCU_USBP_FAULT2 | 18 | MCU_USBP_FAULT1 |
| 19 | not connected | 20 | GND |

## GNSS in Android: what "native" needs

Today the project's GNSS HAL (`usb_gnss_hal/`, AIDL IGnss) reads NMEA from a hard-coded `/dev/ttyAML6` at 9600 baud
and sends UBX config itself. Android has no stock NMEA/serial GNSS HAL (AOSP's default one is a mock), so a HAL
of our own stays in the picture either way. "Native" here means letting the Linux kernel own the device.

UART path (kernel GNSS subsystem, `/dev/gnss0`):
1. Kernel config (vim3 fragment): `CONFIG_GNSS_SERIAL=m` and `CONFIG_GNSS_UBX_SERIAL=m` (`CONFIG_GNSS=m` is already on).
2. Device tree: a child node under `&uart_C`:
   `gnss { compatible = "u-blox,neo-m8"; current-speed = <38400>; };`
   The ubx driver has no M9 entry, but the neo-m8 binding works the same for the M9N. The driver also
   handles the `vcc`/`v-bckp` supplies if they are described; here the MCU switches the supply, so they can be left out.
3. HAL: open `/dev/gnss0` instead of `/dev/ttyAML6`, plus ueventd and sepolicy rules for `/dev/gnss*`.
   This also removes the clash between the `ttyAML.*` gnss label and the serial console.
4. Baud: the NEO-M9N UART default is 38400 (from memory; check the M9N integration manual), while the HAL uses 9600.

USB path (kept for the existing HAL design):
1. The NEO-M9N enumerates as u-blox VID 0x1546, CDC-ACM; `cdc-acm.ko` is already loaded, so it appears as `/dev/ttyACM*`.
2. Add a ueventd rule and a udev-style stable symlink by VID (or have the HAL scan `/sys/class/tty/ttyACM*` for VID 1546),
   plus sepolicy for that device.

Both paths can run at the same time; NEO-M9N outputs the same NMEA on UART and USB.

## RP2350B GPIO map (rev 0.4)

Re-assigned on 2026-10-02 so each signal leaves the QFN on the side facing its destination, which makes routing
possible. This replaces the rev 0.3 map in DESIGN_rev03.md; the draft firmware's pin table needs the same update.
Expansion nets are named after their GPIO (EXP_GPn).

| GPIO | Net | Notes |
|---|---|---|
| GPIO0 | MCU_BL_EN |  |
| GPIO1 | MCU_BL_PWM |  |
| GPIO2 | MCU_HUB_RST |  |
| GPIO3 | MCU_GNSS_PPS |  |
| GPIO4 | MCU_GNSS_TX | UART1 TX to GNSS (via JP2 2-3) |
| GPIO5 | MCU_GNSS_RX | UART1 RX from GNSS |
| GPIO6 | MCU_SBC_SENSE |  |
| GPIO7 | MCU_GNSS_RST |  |
| GPIO8 | MCU_GNSS_SAFEBOOT |  |
| GPIO9 | MCU_GNSS_EN |  |
| GPIO10 | MCU_DAC_MUTE |  |
| GPIO11 | EXP_GP11 | expansion header J10/J21 |
| GPIO12 | EXP_GP12 | expansion header J10/J21 |
| GPIO13 | EXP_GP13 | expansion header J10/J21 |
| GPIO14 | MCU_PARK_IN |  |
| GPIO15 | MCU_PWR_KEY |  |
| GPIO16 | MCU_BTN_MUTE |  |
| GPIO17 | MCU_BTN_VOLUP |  |
| GPIO18 | MCU_BTN_SCREEN |  |
| GPIO19 | MCU_SERVICE |  |
| GPIO20 | MCU_AMP_EN |  |
| GPIO21 | MCU_LED |  |
| GPIO22 | MCU_BTN_VOLDN |  |
| GPIO23 | MCU_VIM3_PWR_EN |  |
| GPIO24 | EXP_GP24 | expansion header J10/J21 |
| GPIO25 | EXP_GP25 | expansion header J10/J21 |
| GPIO26 | EXP_GP26 | expansion header J10/J21 |
| GPIO27 | EXP_GP27 | expansion header J10/J21 |
| GPIO28 | EXP_GP28 | expansion header J10/J21 |
| GPIO29 | EXP_GP29 | expansion header J10/J21 |
| GPIO30 | LUX_SDA | I2C1 SDA (light sensor, TPS55288, audio module) |
| GPIO31 | LUX_SCL | I2C1 SCL |
| GPIO32 | EXP_GP32 | J10 pin 2 (K-line UART TX) |
| GPIO33 | EXP_GP33 | J10 pin 3 (K-line UART RX) |
| GPIO34 | EXP_GP34 | expansion header J10/J21 |
| GPIO35 | MCU_REV_IN |  |
| GPIO36 | MCU_USBP_PG |  |
| GPIO37 | MCU_ILLUM_IN |  |
| GPIO38 | MCU_USBP_FAULT2 |  |
| GPIO39 | MCU_USBP_FAULT1 |  |
| GPIO40 | MCU_VBAT_ADC | ADC0 battery voltage |
| GPIO41 | MCU_5VSYS_ADC | ADC1 5V rail |
| GPIO42 | MCU_TEMP_ADC | ADC2 board temperature |
| GPIO43 | MCU_ACC_IN |  |
| GPIO44 | unused |  |
| GPIO45 | unused |  |
| GPIO46 | unused |  |
| GPIO47 | unused |  |

## Flashing the RP2350B

- Over USB: hold SW1 (BOOTSEL), tap SW2 (RESET); the chip shows up as a USB drive `RP2350` on whatever hosts hub 1.
  A blank flash starts the bootloader by itself. The host is normally the VIM3 (`picotool` from a root adb shell), or a PC
  on a breakout cable to J2 pins 2-5 (5V, D-, D+, GND) with the board off the VIM3 and 12V applied.
- Over SWD: J22 (SWCLK, GND, SWDIO, RUN) with a Raspberry Pi Debug Probe or a Pico running `debugprobe`, for recovery and debugging.
- Firmware should hold hub 1 in reset (MCU_HUB_RST low) while the VIM3 is off, to save parked current and keep the hub's
  D+ pull-up off the unpowered VIM3.

## Hand soldering

Most parts are 0805 or larger SOIC/SOT parts. These need hot air or a hotplate with paste, not an iron:
- RP2350B (QFN-80, 0.4 mm pitch), TPS55288 (VQFN-HR), NEO-M9N (LGA), Q11/Q12 and U16 (VSON/QFN power packages).
- J13 (HDMI) and J14 (0.5 mm FPC) have fine-pitch SMD pins; drag soldering with flux works, but check for bridges.
Ordering the bare boards with only those parts assembled by JLCPCB is an option.

## Main board notes

- HDMI J13 (top edge) to the screen FPC J14 (right edge) is routed on F.Cu over the In1 ground plane with no vias.
  Each pair is matched to 0.001 mm. An In1 rule area keeps vias out from under the runs.
- J14 keeps pin 1 on the right when seen from the top with the ribbon leaving the board edge.
- The TPS55288 power stage (U12, Q11/Q12, L3, gate resistors, snubber, net ties) is carried over from rev 0.3
  with its copper. +5V_SYS reaches J18 through an In2 copper strip.

## GNSS module notes

- The U.FL receptacle J11 sits at the module's left side, about 3 mm from the main board's left edge, so a pigtail can leave sideways.
- The RF line from J11 to the NEO is a 1.0 mm trace over solid B.Cu ground with stitching vias; B.Cu under it has
  no tracks. Check the 50 Ω width with the JLCPCB impedance calculator for the 2-layer 1.6 mm stack before ordering.
- L2 (active-antenna feed choke) is 0402, the one tiny passive left.

## Open items before ordering

- LCSC numbers for the 2x8 socket J27 and 2x8 header J28 (any 2.54 mm, 8.5 mm female socket fits).
- J23/J25 socket part C30867 was out of stock at LCSC on 2026-10-01; any 2x10 2.54 mm 8.5 mm female socket fits.
- The USB module's LMR33630 buck layout is auto-routed with widened copper; not yet checked against TI's layout guide.
- Bench test the TPS55288 loop (unchanged from rev 0.3).

## Layout scripts

`layout/` holds the scripts that made the boards (run in the `kicad/kicad:10.0` Docker image). See rev 0.3's
`layout/README.md` for the shared tools.
