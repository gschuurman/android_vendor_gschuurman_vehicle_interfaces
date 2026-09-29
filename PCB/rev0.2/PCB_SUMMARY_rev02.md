# Car radio mainboard rev 0.2: feature summary

This board is for a 1996 MG F. It carries the VIM3 (Android Automotive) and a Pico 2
(vehicle MCU), plus everything that connects them to the car.

The schematic is `carradio_peripheral_rev02.pdf`: 209 parts on one A1 sheet. The full details
are in `DESIGN_rev02.md`.

## 1. Car connections (ISO 10487)

**ISO A**, through a pigtail (J1):

| Pin | Use |
|---|---|
| A1 | Reverse lamp |
| A2 | Handbrake. It may stay unwired; the VHAL then uses GPS speed. |
| A3 | Amp remote out |
| A4 | Permanent +12V |
| A5 | Only if R57 is fitted |
| A6 | Illumination |
| A7 | ACC |
| A8 | Ground |

**ISO C1** (J8) carries the 4 line outs:

| Pin | Use |
|---|---|
| 1 | Rear L |
| 2 | Rear R |
| 3 | Front L |
| 4 | Front R |
| 5 | Line ground |
| 6 | Amp remote |

**Inputs.** There are 4 opto-isolated inputs: ACC, illumination, reverse and handbrake. The
handbrake input is for a switch that closes to ground. Each input has a fuse or series resistor,
a clamp and a filter.

**Amp remote.** This is a 12V high-side switch fed from ACC and controlled by the Pico. It has
its own fuse, a flyback diode and a TVS, and it can't stay on without ACC.

## 2. Power

**Always-on 5.2V** for the Pico and the GPS comes from a TPS560430 buck (600 mA, about 55 µA
quiescent). It is protected by a PTC, a reverse-polarity diode and a TVS.

**System 5V at 5A** feeds the VIM3 (J18, JST-XH to VIN), the screen and the USB hubs. It comes from a TI
TPS55288 buck-boost:
- It accepts 3V to 36V in, so it holds 5V through cranking and high RPM.
- It runs from permanent +12V, so the VIM3 can finish its Android shutdown after ACC drops.
- The input is protected by a 7.5A blade fuse, a reverse-polarity MOSFET, a load-dump TVS (SM8S22A) and
  bulk capacitors.
- The Pico switches it on with GP28 and turns the output on over I2C.
- The output current limit is 5A (adjustable up to 6.35A).

**USB port 5V at 3A** is a separate LMR33630 buck. Each external port is limited to about 1.4A.

**DAC supplies** are two low-noise LP5907 LDOs, one analog and one digital.

**GPS supply** is its own LP5907, switched off while parked. A backup supply keeps the almanac.

## 3. Pico 2 (vehicle MCU)

- **Vehicle signals:** ACC, reverse, illumination, handbrake, and battery voltage (ADC).
- **Outputs:** amp remote, VIM3 power key (wake), DAC mute, and the enable for the 5V system
  supply.
- **Screen:** backlight enable and PWM go straight to the panel. The PWM is inverted, so 0V is
  brightest.
- **Display buttons** on J12: screen off, volume up, volume down and mute.
- **Other:** BH1750 light sensor (I2C), GPS UART with reset and PPS, VIM3-on sense, and a
  service jumper.
- **Link to Android:** USB through the on-board hub, as HID for vehicle data plus CDC for GPS
  passthrough. Volume and mute are sent as standard media keys.
- **Expansion header:** UART1 (GP20/21), reserved for a later K-line/MEMS add-on.

## 4. Audio

The VIM3's TDM-B I2S (header pins 29/31/32/33) feeds 2× PCM5102A DACs, one for the front pair
and one for the rear pair.
- Output is 2.1 Vrms line level, 24/32-bit, up to 384 kHz, to the JBL amp over ISO C1.
- The Pico sequences the mute with the amp remote so there are no pops.
- There is a ground-lift option in case of alternator whine.

## 5. GPS

A u-blox NEO-M9N sits on the board with an SMA active antenna (antenna supply fed through the
RF line). It connects to the Pico over a UART, and the Pico passes it through to Android.

## 6. Display (Waveshare 70H-1024600 adapter built in)

- An HDMI jack takes a short cable from the VIM3.
- A 40-pin FPC connects to the panel.
- The panel's 5V comes from the board.
- Touch USB goes to the on-board hub.

## 7. USB (no USB cables to the VIM3)

The link to the VIM3 runs over header pins 3/4.

**Hub 1 (CH334R):**
1. Pico
2. Touch
3. RTL-SDR (FM/DAB+). The dongle plugs into an internal USB-A socket.
4. Hub 2

**Hub 2 (CH334R):** two external USB-A ports for a phone and similar devices.

## Please check

Confirmed by Glenn: header pin 1 sits opposite pin 21, the harness matches ISO A/C1, and the VIM3
is powered through VIN (J18 is now the JST-XH 2-pin that fits his lead), and header pins 3/4 work as
USB. The FPC pinout and orientation now follow the Waveshare adapter schematic: pin 1 is on the
right, seen from the top with the ribbon leaving the board edge. 5V is on pins 4-6.

1. **Ordering:** every part now has a checked LCSC number; see ORDERING_rev02.md for the few to check before ordering.

## Not done yet

- PCB layout. The HDMI and USB pairs need controlled impedance, and a 4-layer board is
  recommended.
- Bench-checking the TPS55288 loop.
- Firmware (C, TinyUSB).
- VHAL, device tree and audio HAL changes.
