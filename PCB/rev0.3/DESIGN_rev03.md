# Car radio mainboard rev 0.3: RP2350B on the board

Rev 0.3 is rev 0.2 with the Raspberry Pi Pico 2 module replaced by an RP2350B chip soldered directly to
the board. Everything else is unchanged: car connections, power, audio, GNSS, display, USB hubs and the
phone ports. For those, see `../rev0.2/DESIGN_rev02.md` and `../rev0.2/DESIGN_REVIEW_rev02.md`.

The schematic is `carradio_peripheral_rev03.kicad_sch`, on one A0 sheet with 258 parts. The MCU is
section 13.

## Why

- **More GPIO.** The RP2350B has 48 GPIOs; the Pico 2 left about 26 usable, and all of them were taken.
  The spare pins now carry status lines that had nowhere to go in rev 0.2, and 10 more are brought out
  for later.
- **No sockets or flying wires.** USB runs straight from the chip to hub 1. In rev 0.2 it came from test
  pads on the back of the Pico. The two 1x20 sockets are gone, and socketed parts can work loose from
  vibration in a car.
- **Lower parked current.** A small LDO replaces the Pico's buck-boost regulator. The MCU can still sleep
  while parked, and the Pico's regulator quiescent current is gone.
- **Firmware carries over.** It is the same chip family, so the same Pico SDK and TinyUSB code works.

## MCU core (section 13)

The support circuit follows Raspberry Pi's Pico 2 schematic (Pico 2 datasheet, Appendix B). The RP2350B
pinout comes from the official KiCad library symbol. Every GPIO, USB, QSPI, crystal, RUN and SWD pin was
cross-checked against a second RP2350B design, the WeAct RP2350B core board schematic.

| Part | What | Notes |
|---|---|---|
| U20 | RP2350B, QFN-80 10x10mm, 0.4mm pitch | Use the EasyEDA/LCSC footprint. The exposed pad is GND. Needs JLCPCB assembly; it can't be hand-soldered reliably. |
| U21 | W25Q128JVS 16MB QSPI flash, SOIC-8 208mil | Same flash as the Raspberry Pi reference design. |
| U19 | AP2112K-3.3 LDO, from the always-on 5.2V | Powers the MCU, GNSS backup supply, light sensor and all 3.3V pull-ups (net +3V3_MCU). C80 1µF in, C81 10µF out. |
| L5 | 3.3µH, Abracon AOTA-B201610S3R3-101-T | Core regulator inductor (VREG_LX to +1V1_MCU). Raspberry Pi's hardware design guide warns that its orientation affects the regulator, so copy the Pico 2 layout for L5, C82 and C83. |
| C82, C83 | 4.7µF | VREG_VIN and the 1.1V DVDD output. |
| R80, C84 | 33Ω + 4.7µF | VREG_AVDD filter. |
| C85–C97 | 100nF | One per IOVDD pin (8) and DVDD pin (3), one at ADC_AVDD, and one shared by USB_OTP_VDD and QSPI_IOVDD, as on the Pico 2. |
| Y3, C99, C100, R82 | 12MHz ABM8-272-T3, 15pF load caps, 1k series resistor on XOUT | Values from the Pico 2 schematic. |
| R83, R84 | 27Ω | USB series resistors, to hub 1 port 1. |
| SW1, R81 | BOOTSEL button and 1k on QSPI_SS | Hold SW1 during reset to get the USB bootloader. A blank chip starts in the bootloader on its own. |
| SW2, R85, C101 | RESET button, 10k pull-up and 100nF on RUN | |
| J22 | SWD header, 1x4 | Pins: SWCLK, GND, SWDIO, RUN. Works with a Raspberry Pi Debug Probe. |
| D16, R86 | Status LED on GPIO25 | Same pin as the Pico's LED. |

The Pico module's parts are gone: J3/J4 sockets, J16 USB pads and the D3 OR-ing diode.

## GPIO map

GPIO0–29 keep the rev 0.2 Pico numbers wherever possible, so the firmware changes little. The one move
is the battery ADC: GP26 becomes GPIO40, because only GPIO40–47 have an ADC on the RP2350B.

| GPIO | Function | GPIO | Function |
|---|---|---|---|
| 0 / 1 | GNSS UART0 TX / RX | 24 | USB port 2 over-current (TPS2561 FAULT2), **new** |
| 2 | ACC | 25 | Status LED, **new** |
| 3 | Reverse | 26 | USB phone-port supply power good (LMR33630 PG), **new** |
| 4 / 5 | I2C0 SDA / SCL (light sensor + TPS55288) | 27 | Button: mute |
| 6 | Illumination | 28 | VIM3 5V supply enable (TPS55288 EN) |
| 7 | Handbrake | 29 | GNSS SAFEBOOT (recovery), **new** |
| 8 | VIM3 power key | 30 / 31 | Spare, J10 pins 4 / 8, **new** |
| 9 | Amp remote | 32–39 | Spare, expansion header J21, **new** |
| 10 / 11 | Backlight enable / PWM | 40 (ADC0) | Battery voltage (was GP26) |
| 12 | GNSS supply enable | 41 (ADC1) | 5V system rail, /2 divider, **new** |
| 13 | VIM3 on sense | 42 (ADC2) | Board temperature (NTC TH1), **new** |
| 14 | Service jumper | 43 | Hub 1 reset (pull low to reset), **new** |
| 15 | DAC mute | 44–47 | Not connected |
| 16 / 17 | Buttons: screen off / volume up | | |
| 18 / 19 | GNSS reset / PPS | | |
| 20 / 21 | UART1 on J10 (K-line later) | | |
| 22 | Button: volume down | | |
| 23 | USB port 1 over-current (TPS2561 FAULT1), **new** | | |

**New status inputs.** GPIO23/24/26 let the firmware see a shorted phone port or a failed USB supply,
and report it to Android. GPIO41 shows the 5V rail sagging. GPIO42 reads board temperature, so the
firmware can derate: for example, lower the phone-port current or dim the backlight when the dash gets
hot. Place TH1 next to the TPS55288 and LMR33630.

## RP2350-E9 check (pad latching)

**The erratum.** RP2350-E9: a GPIO used as an input with only the internal pull-down can latch at about
2V after it has been driven high and released, so the internal pull-down doesn't pull it low. The
workaround is an external pull-down of about 8.2k or less, or a pull-up instead. Every MCU pin was
checked:

| Pins | What drives them | Resistor | OK |
|---|---|---|---|
| GPIO2, 3, 6, 7 (opto inputs) | Opto emitter | 4.7k pull-down (R4, R6, R30, R32) | yes |
| GPIO13 VIM3 sense | VIM3 3.3V via 1k | 4.7k pull-down (R8) | yes |
| GPIO14 service jumper | Jumper to 3.3V | 4.7k pull-down (R9) | yes |
| GPIO16, 17, 22, 27 buttons | Switch to GND | 10k pull-up | yes (E9 affects pull-downs only) |
| GPIO23, 24, 26 fault/PG | Open drain | 10k pull-up (R87–R89) | yes |
| GPIO4, 5 I2C | Open drain | 4.7k pull-up (R33, R34) | yes |
| GPIO19 GNSS PPS | GNSS module, floats when the GNSS is off | 4.7k pull-down (R94), **new** | yes |
| GPIO1 GNSS RX | GNSS TX, floats when the GNSS is off | 4.7k pull-down (R95), **new** | yes |
| GPIO40, 41, 42 ADC | Dividers / NTC | Firmware disables the digital input buffer (the SDK's `adc_gpio_init` does this) | yes |
| GPIO8, 9, 12, 15, 28 outputs | MCU | Off-state resistor so the load stays off during reset: R19, R15, R35, R47, R72 | yes |
| GPIO10 backlight enable | MCU | 100k pull-down (R96), **new**: backlight off until the firmware decides | yes |
| GPIO11 backlight PWM, GPIO0 GNSS TX, GPIO25 LED | MCU outputs | none needed | yes |
| GPIO18 GNSS reset, GPIO29 GNSS safeboot, GPIO43 hub reset | Firmware only ever drives these low; otherwise input, never read | 1k series. The GNSS pins have internal pull-ups; for the CH334R reset pin, see the note in the rev 0.2 design review | yes, if the firmware never reads them |
| RUN | Button / debug probe | 10k pull-up (R85) | yes |
| GPIO20, 21, 30–39 expansion, GPIO44–47 | Nothing on the board | none | See firmware rule 1 |

**Firmware rules that go with this:**

1. Unused and expansion pins (GPIO20, 21, 30–39, 44–47): at boot, set them to input with the input
   buffer disabled, or to output-low, until an add-on uses them. An add-on board that uses one as an
   input needs its own pull-up, or a pull-down of 8.2k or less.
2. While the GNSS supply (GPIO12) is off, drive GNSS TX (GPIO0) low or leave it as an input. Otherwise it
   back-powers the unpowered module through R37.
3. Never enable the internal pull-down on a pin and rely on it alone.

## Open items

- **Parts.** Every new part has a checked LCSC number, and both Raspberry Pi reference parts are stocked (L5
  C42411119, Y3 C20625731). The RP2350B's own LCSC stock was unclear on 2026-09-29, so check it in the
  JLCPCB parts search.
  - **Fallback:** the RP2354B (C39843328, in stock, $1.48) is the same chip with 2MB flash inside. If you fit
    it, leave U21 unfitted, because the internal flash uses the same chip select.
  - **Switches:** LCSC lists the TL3342 package as 5.2x5.2mm, so take SW1/SW2's footprint from the LCSC
    library.
  - The lookup table is in `lcsc_lookup/picks_mcu.md`.
- Update `board.h` in `mcu/firmware` to this pin map. The draft firmware still follows an early rev 0.2
  pin map.
- Layout: keep the QSPI flash and crystal within a few millimetres of U20. Copy the Pico 2 layout for
  the core regulator (L5, C82, C83). Route the USB pair to hub 1 as a 90Ω pair.

## Importing into KiCad

The schematic is KiCad 7 format and opens in KiCad 7, 8 and 9. All symbols are embedded in the file, so
it needs no extra symbol libraries. I checked it with KiCad 7's command-line tools: the file loads, and
the netlist and PDF export cleanly. KiCad's own ERC has not been run, because KiCad 7's command line has
no ERC. Run Inspect > Electrical Rules Checker once in the GUI. Expect some "power pin not driven"
warnings on nets fed through a diode or fuse. Those need PWR_FLAG symbols, not wiring changes.

**Footprints.** Every footprint name was checked against the KiCad libraries. Four parts need attention
before "Update PCB from Schematic":

| Part | Issue | Fix |
|---|---|---|
| U12 TPS55288 (LCSC C2864583) | No KiCad library footprint | Run `easyeda2kicad --full --lcsc_id=C2864583` (pip package easyeda2kicad), or take TI's footprint from the TPS55288 product page. |
| F4 Littelfuse 01530008Z (C206907) | No KiCad library footprint | `easyeda2kicad --full --lcsc_id=C206907` |
| J14 XUNPU FPC-05FB-40PH20 (C2856837) | The schematic uses the Hirose FH12 footprint, and the XUNPU pads may differ | `easyeda2kicad --full --lcsc_id=C2856837` and swap it in |
| U20 RP2350B QFN-80, U21 SOIC-8 208mil | In the current KiCad library (8/9), not in KiCad 7 | Nothing, on KiCad 8 or later |

The TL3342 switches use KiCad's own SW_SPST_TL3342 footprint.
