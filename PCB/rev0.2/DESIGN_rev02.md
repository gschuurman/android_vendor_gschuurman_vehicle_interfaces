# Car radio peripheral board, rev 0.2 (rough design, 2026-09-29)

For a 1996 MG F: VIM3 running AAOS, plus a Pico 2 as the vehicle MCU. It adds four channels of
line-out audio and an on-board u-blox NEO-M9N. The Pico takes over everything that isn't
audio.

## Files

| File | What |
|---|---|
| `carradio_peripheral_rev02.kicad_sch` / `.kicad_pro` | KiCad 7 schematic. Import it in EasyEDA Pro with File > Import > KiCad (zip below). |
| `carradio_peripheral_rev02_kicad.zip` | Project zip for import. |
| `carradio_peripheral_rev02.pdf` | Schematic on A1, one sheet. |
| `carradio_peripheral_rev02_bom.csv` | BOM with LCSC numbers where verified. |
| `gen2.py` + `sexp.py` | Generator script (`python3 gen2.py`). |
| `AUDIO.md` | Background on the audio choice. |

Rev 0.1 files remain alongside for comparison.

## What changed from rev 0.1

- **Car connection is ISO 10487.** Micro-Fit headers are on the board, with a short ISO
  pigtail. Pin numbering on each header equals the ISO pin number.
  - **J1 = ISO A** (Glenn's layout, 2026-09-29):
    - A1 reverse lamp +12V
    - A2 handbrake switch
    - A3 amp remote out
    - A4 permanent +12V
    - A5 amp remote too, but only if R57 (0 Ω, not fitted) is fitted
    - A6 illumination
    - A7 ACC
    - A8 ground
  - **J8 = ISO C1:**
    - 1 rear L
    - 2 rear R
    - 3 front L
    - 4 front R
    - 5 line-out ground
    - 6 remote
  - There is no separate aux plug. K-line is only reserved on the expansion header.
- **Reverse, backlight enable and backlight PWM moved from the VIM3 header to the Pico.** The
  VHAL reads and sets them over the USB link. Header pins 32, 33 and 35 now carry audio.
- **Four opto inputs:** ACC, ILLUM, REVERSE and PARK.
  - PARK is wired for the MG F handbrake switch, which switches to ground. Its LED is fed from
    ACC and the switch sinks it.
  - A series diode blocks reverse voltage when ACC is off.
  - **If the handbrake wire can't reach the radio, leave A2 unwired.** The input then reads
    "not engaged". AAOS uses PARKING_BRAKE_ON to lock video and some settings while driving, so
    the VHAL should then report the brake as on whenever GNSS speed is about 0 and the car isn't
    in reverse.
- **Amp remote** is still a P-MOSFET high-side switch fed from ACC and driven by Pico GP9.
  - No opto is needed, because the Pico and the amp share car ground.
  - It now has its own PTC (F3), a flyback diode and a TVS, so a shorted remote wire can't pull
    ACC down.
  - It drives ISO A3 and C1-6, and A5 as well if R57 is fitted.
- **Audio:** VIM3 TDM-B I2S goes into two PCM5102A DACs.
  - Lane 0 (pin 31) feeds front, lane 1 (pin 33) feeds rear.
  - BCLK is on pin 29 and LRCK on pin 32, each through a 33 Ω series resistor.
  - Each DAC has its own supply decoupling. There are two LP5907 LDOs (analog and digital),
    fed from the VIM3 5V, so the DACs are only powered while the VIM3 is on.
  - The output is the datasheet 470 Ω / 2.2 nF C0G filter, giving 2.1 Vrms line level.
  - The Pico GP15 drives XSMT (soft mute). A 10k pull-down keeps the DACs muted by default.
  - R56 is a ground-lift option for alternator whine: fit 0 Ω, or 10 Ω.
- **GNSS:** NEO-M9N-00B (LCSC C5119087).
  - UART0 to the Pico (GP0/GP1) through 1k resistors. The Pico bridges it to Android as USB CDC.
  - GP18 drives reset, and GP19 receives the PPS pulse.
  - VCC comes from its own LP5907, switched by GP12, so it is off while parked.
  - V_BCKP comes from the always-on Pico 3V3, for hot starts.
  - Active antenna on an SMA: VCC_RF feeds it through 10 Ω and a 27 nH choke.
- **Display buttons (J12, JST-PH 5P):** screen off, volume up, volume down, mute, then GND.
  - Each is a button to ground with a 10k pull-up, a 1k series resistor and a 100 nF filter.
  - The Pico sends volume and mute to Android as USB HID consumer keys, which Android handles
    natively.
  - Screen off switches the backlight directly from the Pico and is reported to the VHAL.
- **Display adapter built in (Waveshare 70H-1024600).** The Waveshare "HDMI LCD Adapter" is
  only connectors, so the board now carries its parts directly. The panel's own driver board
  stays on the back of the panel.
  - J13 HDMI-A receptacle: a short HDMI cable comes in from the VIM3.
  - J14 40-pin 0.5 mm FPC to the panel. Pinout checked against the Waveshare "HDMI LCD Adapter"
    schematic that Glenn supplied:
    - 1-3: 12V, not connected (R1 is not fitted on the adapter)
    - 4-6: 5V
    - 7: 3V3 out, unused
    - 8-10: GND
    - 11-22: TMDS with GND between the pairs
    - 23-28: CEC, SCL, SDA, GND, HDMI 5V, HPD
    - 29-32: audio, unused
    - 33/34: touch USB
    - 35: GND
    - 36/37: backlight PWM/EN
    - 38-40: KEY/IO0/IO1, unused
    - mounting tabs: GND
  - **Orientation (as on the adapter):** seen from the component side with the ribbon leaving
    the board edge, pin 1 is on the right and pin 40 on the left.
  - The touch controller's USB goes to the on-board hub (see below).
  - The panel's 5V (about 0.45 A) comes from the board's switched 5V rail (+5V_SYS), not from the
    VIM3's USB. That rail comes from the new 5V/5A supply below.
  - Backlight EN/PWM go straight from the Pico to the panel, so the old backlight plug J6 is gone.
    Waveshare's PWM is inverted: 0 V is brightest.
  - The FPC connector is a dual-contact type (top and bottom), so the cable's contact side
    doesn't matter. Route TMDS as 100 Ω differential pairs.
- **5V/5A system supply for the VIM3, screen and hub (section 10).** It runs from permanent
  +12V (ISO A4), so the VIM3 can finish its Android shutdown after ACC drops.
  - **Input stage:** 7.5A blade fuse, then a P-MOSFET for reverse-polarity protection, a
    load-dump TVS, and 100 µF plus 2×10 µF of input capacitance.
  - **Converter:** TI TPS55288 buck-boost (LCSC C2864583) with two CSD18543Q3A buck-side
    MOSFETs (C840100) and a 4.7 µH inductor with 15 A or more saturation current. It runs at
    about 420 kHz. It covers 3 V to 36 V in, so it holds 5 V through cranking and through a
    high charging voltage.
  - **Output:** 4×22 µF ceramic plus 220 µF polymer. A 10 mΩ sense resistor gives a 5 A output
    limit, adjustable over I2C up to 6.35 A.
  - **Control from the Pico:** GP28 drives EN (100k pull-down). The chip powers up with its
    output off, so the Pico writes the OE bit over I2C0 at address 0x74 (MODE = 0 Ω: internal VCC,
    forced PWM). The default output voltage is 5.0 V (internal feedback).
  - **Compensation (8.2k + 4.7 nF, 22 pF):** calculated from the datasheet equations for a
    2.5-4 kHz crossover. Check it on the bench.
  - **Output connector:** J18 is a JST-XH 2-pin header (pin 1 +, pin 2 −). It mates with Glenn's existing
    VIM3 VIN lead. The VIM3 VIN accepts 5-12 V (Khadas docs). XH contacts are rated 3 A, which
    is enough for the VIM3 alone.
    The panel (J14) and the hub use the same rail.
  - Component values and pinout come from the TI datasheet SLVSF01B that Glenn supplied.
- **USB hub, no USB cables (section 11).** A WCH CH334R 4-port hub (C4154405, QSOP-16, 12 MHz
  crystal) has its upstream port on VIM3 header pins 3/4.
  - The Khadas forum identifies those pins as port 4 of the VIM3's on-board hub. Glenn confirmed they work as USB.
  - **Downstream ports:**
    1. Pico USB (J16: wire to Pico TP2 D- / TP3 D+, or route directly if the Pico is
       surface-mounted with a TP-pad footprint)
    2. Screen touch
    3. RTL-SDR: board-mounted USB-A J17, PTC-fused. The existing dongle plugs in with its
       USB-A to USB-C cable.
    4. A second CH334R hub for the external ports.
  - The hub is powered from the 5V system rail, so it is off whenever the VIM3 is off.
- **RTL-SDR (FM / DAB+):** kept as the existing dongle, plugged into an internal USB-A port.
  - I didn't build the RTL2832U and tuner chips onto the board. It needs careful RF layout, a
    TCXO and tuner parts that are hard to source, and it can't be done reliably from here.
  - Antennas:
    - FM: the car's FM antenna (DIN plug) needs a DIN-to-SMA adapter.
    - DAB+: needs its own Band III antenna. An active one can be powered by the dongle's bias-T
      if it has one (RTL-SDR Blog V4 does).
- **External USB ports, for a phone etc. (section 12):**
  - Two USB-A ports, J19 and J20, behind a second CH334R hub. Its RESET#/CDP is tied high to
    enable BC1.2 CDP; WCH says support depends on package and batch. Without CDP, phones
    charge at 500 mA while connected for data.
  - The ports have their own 5V/3A buck, an LMR33630ADDAR (C841384) fed from the protected
    +12V, so phone charging doesn't load the VIM3 rail. Values come from TI's 5V/3A example.
  - A TPS2561 dual power switch (C140303) limits each port to about 1.44 A (RILIM 39k), with
    100 µF per port.
  - The ports are powered only while the VIM3 supply is on (GP28).
  - Board-mount USB-A sockets are the default. They can also be JST leads to dash-mount
    sockets.
  - All USB traffic shares the VIM3 header's USB 2.0 link (480 Mbit/s). That's plenty for the
    RTL-SDR (about 40 Mbit/s), touch, the Pico and a phone.
- **K-line (MEMS 1.9)** is reserved only. UART1 (GP20/GP21) goes to expansion header J10. A small L9637D add-on board can come later.

## Pico 2 pin map (rev 0.2)

| GPIO | Use | GPIO | Use |
|---|---|---|---|
| GP0 / GP1 | UART0 to GNSS RXD / TXD | GP12 | GNSS LDO enable |
| GP2 | ACC in | GP13 | VIM3 3V3 sense (VIM3 on/off) |
| GP3 | REVERSE in | GP14 | Service jumper |
| GP4 / GP5 | I2C0 SDA / SCL, BH1750 light sensor | GP15 | DAC mute (XSMT) |
| GP6 | ILLUM in | GP18 | GNSS reset |
| GP7 | PARK in | GP19 | GNSS PPS |
| GP8 | VIM3 power key (via Q1) | GP20 / GP21 | UART1, K-line reserved (J10) |
| GP9 | Amp remote | GP16 / GP17 / GP22 / GP27 | Display buttons: screen off, vol+, vol-, mute (J12) |
| | | GP28 | Enable for the 5V/5A VIM3 supply |
| GP10 | Backlight enable | GP26 | Battery voltage (1M / 220k) |
| GP11 | Backlight PWM | USB (TP2/TP3) | To the on-board hub: HID vehicle data + CDC GNSS |

## VIM3 header use (rev 0.2)

- **Pins 1 and 2 (5V):** supply the DAC LDOs.
- **Pins 20 and 27 (3V3):** VIM3-on sense.
- **Audio:**
  - 29 BCLK
  - 32 LRCK
  - 31 DOUT0 (front)
  - 33 DOUT1 (rear)
- **Free:** pin 35 is TDM-B lane 3, spare for a sub or a third pair. Pin 30 (MCLK) isn't used.
- **No longer used from the header:** UART_C, I2C, and pin 37.
- **Power key:** J5 still goes to the VIM3 power-key pad (GPIOAO_7), which remains the wake line.

## Power-up and power-down order (firmware)

1. When ACC comes on, the Pico presses the VIM3 power key.
2. When the VIM3 3V3 sense is high, the DACs have power. The Pico waits for Android to report it
   is ready, unmutes the DACs, then switches on the amp remote after about 2 s.
3. When ACC goes off, the amp remote goes off first, then the DACs mute. After that the AAOS
   shutdown handshake runs. The GNSS LDO goes off once the VIM3 is down, and V_BCKP keeps the
   almanac.

## Verified vs. to check

Checked against the datasheets:
- The PCM5102A pinout (TI PCM510xA datasheet, TSSOP-20).
- The NEO-M9N pinout and supply ranges (u-blox NEO-M9N-00B datasheet).
- The TPS560430 pinout.
- KiCad's library symbols for these three parts use the same pin numbers.

LCSC numbers were verified for the ICs, FETs, diodes, optos and all passives listed in the BOM.
Among them: LP5907MFX-3.3/NOPB is C80670, the 470 Ω resistor is C23179, the 2.2 nF C0G is
C28260, the 10 Ω is C22859 and the 10 µF 25V is C15850.

Please check or pick in EasyEDA:
- **Micro-Fit headers, SMA jack, 27 nH RF inductor, PTCs, LED, JST-PH and pin headers:** these are
  marked "pick in library". Choose a library part that has an LCSC number. I did not guess
  these footprints.
- **NEO-M9N footprint:** use the EasyEDA library part for C5119087, not a hand-drawn one.
  Lay out RF_IN as a short 50 Ω coplanar trace.
- **RF_IN DC blocking:** I'm relying on RF_IN being DC-blocked inside the module when the antenna
  is fed through the inductor, which is how u-blox shows it. Confirm this in the NEO-M9N
  integration manual before layout.
- **Confirmed by Glenn on 2026-09-29:** VIM3 header pin 1 sits opposite pin 21, and the harness
  matches the ISO A/C1 pin use.
- **VIM3 header USB (pins 3/4):** confirmed working as a USB host port by Glenn (2026-09-29).

## Software work this implies (not started)

- **Kernel DT:** tdmif_b, tdmout_b and frddr; an axg-sound-card link with two `pcm5102a` codecs
  (lane masks 0 and 1); build `snd-soc-pcm5102a.ko`. Also drop the header GPIO uses for reverse
  and backlight.
- **Audio HAL:** card name and 4-channel output. Fade and balance already exist.
- **VHAL:** reverse, backlight, ILLUM, PARK, amp and battery voltage come from the Pico link
  instead of VIM3 GPIO and PWM.
- **Pico firmware:** C with TinyUSB (HID + CDC GNSS bridge), plus the new pin map above.
