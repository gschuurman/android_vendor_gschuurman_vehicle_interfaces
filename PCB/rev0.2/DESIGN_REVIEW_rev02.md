# Design review: mainboard rev 0.2 (2026-09-29)

Scope: the generated schematic `carradio_peripheral_rev02.kicad_sch`, checked against the TI datasheets
for the TPS55288, TPS560430 and LMR33630.

**Result:** the netlist is clean. The fixes below are already in the schematic and BOM, which now has
209 parts.

## 1. Connectivity check

The KiCad version here (7.0) has no command-line ERC, so I checked the exported netlist with a script
instead:

- No net has only one pin.
- No net is made of inputs alone.
- No net has two outputs fighting.

Every unconnected pin was reviewed and is unused on purpose. That covers:

- the spare VIM3 header pins
- Pico RUN, ADC_VREF, 3V3_EN and VBUS
- the unused FPC pins (12V, 3V3 out, audio, KEY/IO)
- NEO-M9N SAFEBOOT, D_SEL, EXTINT, LNA_EN and the unused I2C/USB pins
- hub 2 ports 3 and 4
- the LMR33630 PG pin and the TPS2561 FAULT pins

Two of these are worth a word:

- **TPS55288 FB/INT** becomes a fault output when internal feedback is used (datasheet pin table). It can
  float; the Pico reads the same faults from the STATUS register over I2C.
- **CH334R hub 1 RESET#/CDP** is left floating. I believe it has an internal pull-up, but I haven't checked that
  against the WCH datasheet. If it has none, tie the pin to HUB_3V3 through 10k.

## 2. Fixes applied to the schematic

| Part | Was | Now | Why |
|---|---|---|---|
| D2, D5, D13 | SMBJ18A | SMBJ22A | An 18V TVS starts conducting at 20V. A 24V jump start would trip the PTCs and reset the Pico, and a load dump would hit these small TVSs first. At 22V the diode stays off at 24V, and its 35.5V max clamp is below the 38V absolute max of the TPS560430 (TI datasheet). |
| D14 | SM8S24A suggested | SM8S22A | The SM8S24A clamps up to 38.9V, which is over the LMR33630's 38V absolute max (TI datasheet). The SM8S22A clamps at 35.5V max and still does not conduct at 24V. |
| Q2 (amp remote high side) | AO3401A, -30V | -60V P-FET (pick) | With the ACC TVS clamping at up to 35.5V, a -30V part is not enough. |
| Q3 (drives Q2 gate) | AO3400A, 30V | 2N7002, 60V | Its drain sees ACC through R13. |
| C48 (input bulk) | 100µF 35V | 100µF 50V | It sits at the 35.5V clamp level during a load dump. |
| R69 (TPS55288 ILIM) | 20k (16.5A, max 19A) | 30k (11A, max ~12.7A) | The old limit was above L3's 15A saturation current. 11A still delivers 25W at the output with only 3V at the input (cranking). |
| U17, U18 (new) | none | USBLC6-2SC6 on the two external USB ports | These ports are the ones people plug phones into, so they take the ESD hits. Place each one right at its connector. |

## 3. Power budget

| Rail | Loads | Estimate | Limit |
|---|---|---|---|
| +5V_SYS (TPS55288) | VIM3 ~2-2.5A under load, screen ~0.6A, RTL-SDR ~0.3A, 2 hubs ~0.15A | ~3.1A typical, ~3.8A peak | 5A |
| +5V_USB (LMR33630) | 2 phone ports | up to 2.9A | 3A |
| +5V_AON (TPS560430) | Pico ~25mA, NEO-M9N ~35mA, antenna ~15mA, light sensor and pull-ups | ~0.1A | 0.6A |

The VIM3 and screen figures are estimates. Measure the VIM3 current once it runs on the bench.

**JST-XH to the VIM3 (J18).** JST rates XH at 3A per contact. The VIM3 alone should stay under that. If
the bench measurement shows more than about 2.5A, switch J18 to a JST-VH or use two pins per pole.

**VIM3 input voltage.** The VIM3 accepts 5-12V and gets exactly 5.0V at the board. The lead then drops
roughly 0.1-0.15V at 3A. Have the Pico firmware write CDC[2:0]=010 or 011 (register 05h) when it enables
the TPS55288. That raises the output with load current (datasheet 7.3.12: +100mV at 5A for 001, up to
+700mV for 111). USB devices stay under 5.25V.

## 4. Heat

- **TPS55288** at 12V in and 5V/4A out loses roughly 1W, spread across Q11, Q12, L3, R74 and the IC. That
  is fine with the thermal pad stitched to the inner ground planes.
- **LMR33630** loses about 1.4W at 3A (both phones fast-charging) in one SO-8 PowerPAD. In a dash at 70°C
  that needs a solid copper pour under the thermal pad on a 4-layer board. If it runs hot, change R77 to
  56k, which sets 1.0A per port.
- **TPS560430** runs at under 0.2W.

## 5. Parked battery drain

The hardware draws about 0.1mA while parked: the TPS560430 quiescent current, the battery divider and
leakage.

The Pico is the real load. A running Pico 2 draws about 20mA at 5V, which is roughly 9mA from the
battery, or 0.2Ah per day. The firmware must put the RP2350 into dormant or sleep, woken by the ACC
input. Otherwise a car standing through the winter will go flat.

## 6. Layout rules (for part 3)

### HDMI (J13 to J14)

- Each TMDS pair (D0, D1, D2, CLK) is a 100Ω differential pair.
- Match the + and - traces within each pair to 0.15mm.
- Match all four pairs to each other within 1mm. HDMI allows much more skew, but on a run this short it
  costs nothing.
- Route on one layer next to the solid ground plane, with no vias, and keep the GND pins between the
  pairs connected.

The netlist makes this easy. HDMI pins 1-19 land on FPC pins 11-28 in the same order, at nearly the same
0.5mm pitch. If J13 and J14 face each other with pin 1 of J13 on the FPC pin 11 side, every pair runs
straight with no crossings, and the lengths come out matched almost for free.

### USB

- Every USB 2.0 pair is 90Ω differential and matched within 0.15mm inside the pair: VIM3 header to hub 1,
  hub to hub, and hubs to the ports.
- The header link runs through the IDC ribbon, so keep that ribbon short.

### Power stage

Keep the TPS55288 hot loops tight:

- the input caps, Q11 and Q12
- the SW2 node to the output caps

Keep the stage away from the GNSS antenna feed and from the RTL-SDR socket. Its 422kHz harmonics land in
the FM band.

### GNSS

- 50Ω coplanar line from the SMA jack to RF_IN, as short as possible.
- Ground via fence along the line.

## 7. Still open

- Bench check of the TPS55288 loop compensation (R71/C54/C55).
- Part numbers for everything marked "pick in library". That is part 2, which is next.
