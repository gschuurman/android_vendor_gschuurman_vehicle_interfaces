# Car radio peripheral board, rev 0.1 (rough design)

Replaces the perfboard between the car loom, the Raspberry Pi Pico 2 and the Khadas VIM3.
Derived from `android_vendor_gschuurman_vehicle_interfaces` (android-16) `mcu/main.py` and README,
`device_khadas_vim3/vehicle.mk`, the VHAL (`automotive/vhal`) and the VIM3 kernel DT
(`meson-khadas-vim3.dtsi`).

## Files

| File | What |
|---|---|
| `carradio_peripheral.kicad_sch` | Schematic (KiCad 7 format). Import in EasyEDA Pro with File > Import > KiCad. |
| `carradio_peripheral.kicad_pro` | Minimal KiCad project file, in case the importer wants a project. |
| `carradio_peripheral.pdf` | Printable schematic, to check before importing. |
| `carradio_peripheral_bom.csv` | BOM with LCSC numbers, MPNs and fitted/DNP status. |
| `carradio_peripheral_kicad.zip` | Schematic, project file and PDF zipped, for importers that want one archive. |
| `gen.py`, `sexp.py` | Script that generates the schematic and BOM. Edit it and rerun to change the design (needs KiCad's symbol library for the stock parts). |

Every connection is a net label placed on a pin, so the netlist is explicit and survives import.
KiCad's netlist export of this file gives 64 parts and 49 named nets, all with at least 2 pins.

## Block diagram

```
 Car loom (J1, 5.08mm pluggable)
  BATT+ ─ F1 PTC ─ D1 SS34 ─┬─ D2 SMBJ18A ─ GND
                            ├─ U1 TPS560430 buck ─ +5V_AON ─ D3 SS14 ─ Pico 2 VSYS
                            └─ R10/R11 divider ─ Pico GP26 (battery voltage)
  ACC   ─ F2 PTC ─ D4 SS34 ─┬─ D5 SMBJ18A ─ GND
                  (ACC_P)   ├─ R3 + U2 EL817 opto ─ Pico GP27 (ACC in)
                            └─ Q2 AO3401A high-side ─ J1.4 AMP REMOTE (+12V)
                                  ▲ Q3 AO3400A ◄─ Pico GP11 (R16) or VIM3 pin 37 (R17, DNP)
  REVERSE ─ R5 + U3 EL817 opto ─ Pico GP21 (reverse in)

 Pico 2 ─ GP2  ─ 1k ─ VIM3 pin 32 GPIOA_2  (reverse gear to VHAL)
        ─ GP5  ─ Q1 AO3400A open-drain ─ J5 ─ VIM3 POWER key (GPIOAO_7, active-low)
        ─ GP6  ◄─ 1k ─ VIM3 3.3V (pins 20/27)  (SBC rail sense)
        ─ GP10 ◄─ JP1 service jumper
        ─ GP0/GP1 ─ 1k ─ VIM3 UART_C (pins 15/16), optional link
 VIM3 pin 33 GPIOA_4 ─ 100R ─ J6 BL_EN     (backlight enable, VHAL)
 VIM3 pin 35 PWM_F   ─ 100R ─ J6 BL_PWM    (backlight PWM 32.768 kHz, VHAL)
 VIM3 I2C_AO 25/26 (or I2C_M3 22/23) ─ 0R jumpers ─ J7 BH1750 light sensor
```

## Pin map

**Pico 2.** The existing functions keep their pins and active-high polarity, so the current `main.py` runs unchanged.

| Pico pin | GPIO | Net | Use |
|---|---|---|---|
| 32 | GP27 | PICO_ACC_IN | ACC sense (opto U2) |
| 27 | GP21 | PICO_REV_IN | Reverse sense (opto U3) |
| 4 | GP2 | PICO_REV_OUT | Reverse out to VIM3 pin 32 |
| 7 | GP5 | PICO_PWR_BTN | High = press the VIM3 power key (via Q1) |
| 9 | GP6 | PICO_SBC_SENSE | VIM3 3.3V rail sense |
| 14 | GP10 | PICO_SERVICE | Service-mode jumper JP1 |
| 15 | GP11 | PICO_AMP_EN | **New:** amp remote on (needs a small firmware addition) |
| 31 | GP26/ADC0 | PICO_VBAT_ADC | **New:** battery voltage, 14.4V reads 2.6V (ratio 0.18) |
| 1 / 2 | GP0 / GP1 | PICO_TX / PICO_RX | **New, optional:** UART to VIM3 UART_C |
| 39 | VSYS | PICO_VSYS | 5.2V always-on supply via D3 |
| 36 | 3V3_OUT | +3V3_PICO | Opto collector supply, service jumper |

**VIM3 40-pin header** (Khadas numbering; J2 is a 2x20 IDC box header, so VIM3 pin v lands on IDC pad 2v-1 for v ≤ 20 and pad 2(v-20) for v > 20):

| VIM3 pin | Signal | Net | Use |
|---|---|---|---|
| 20, 27 | 3.3V | VIM3_3V3 | Rail sense for the Pico, BH1750 supply |
| 32 | GPIOA_2 (offset 51) | VIM3_REV | Reverse gear input (VHAL `gear.gpio.offset=51`) |
| 33 | GPIOA_4 (offset 53) | VIM3_BL_EN | Backlight enable (VHAL `backlight.enable.gpio.offset=53`) |
| 35 | PWM_F (GPIOH_5) | VIM3_BL_PWM | Backlight PWM (DT `pwm_f_h_pins`) |
| 25 / 26 | I2C_AO SCK/SDA | VIM3_I2C_AO_* | BH1750 (default, R25/R26 fitted) |
| 22 / 23 | I2C_M3 SCL/SDA | VIM3_I2C_M3_* | BH1750 alternative (R27/R28, DNP) |
| 15 / 16 | UART_C RX/TX | VIM3_UARTC_* | Optional Pico link (UART_C isn't enabled in the DT yet) |
| 37 | GPIOH_4 | VIM3_GPIOH4 | Amp remote control from Android, if you fit R17 instead of R16 |
| 5, 9, 14, 17, 21, 24, 28, 34, 40 | GND | GND | |
| 1, 2 | 5V | unused | The VIM3 isn't powered from this board (see open questions) |

## What changed compared to the perfboard, and why

- **Opto-isolated ACC and reverse inputs.** Each input drives an EL817 LED through 4.7k. The opto emitter drives the Pico pin with a 4.7k pull-down. That output is low-impedance and active-high, and the pull-down is well under the 8.2k the RP2350-E9 erratum calls for. The internal pull-downs the firmware enables are then harmless. The GP27 Schmitt workaround in `main.py` can stay.
- **Proper supply protection:** a PTC fuse, series Schottky for reverse polarity and a TVS on both BATT+ and ACC. The Pico gets a 36V-rated buck (TPS560430X). At light load it runs PFM with about 55µA quiescent current, so it doesn't undo the standby work in the firmware.
- **Power key is an open-drain MOSFET (Q1).** The VIM3 POWER key is active-low (`GPIOAO_7 GPIO_ACTIVE_LOW` in the DT), so Q1 pulls it to GND when GP5 goes high. This matches the firmware's "high = press" logic and never back-drives the VIM3.
- **1k series resistors on every Pico-to-VIM3 signal.** They limit back-feeding into the VIM3's IO pins while it is off and the Pico is still running.
- **New amplifier remote-trigger output** (J1 pin 4). A P-MOSFET high-side switch is fed from **ACC**, not permanent battery, so a hung Pico can never leave the amp on with the car off. The gate is driven at about -Vacc/2 and a 12V zener clamps it. It is sized for about 1A; typical remote-on inputs draw well under 100mA. SS34 clamps the kick from a long remote wire, and the green LED shows when it's on.

## Power budget (12V side)

| State | Pico (from README) | Board total from BATT+ | Notes |
|---|---|---|---|
| Car off (STATE_OFF) | 1–2 mA at 3.3V | ≈ 1 mA | Buck in PFM, divider 12µA, optos off. About 24 mAh/day. |
| Sleep pending (15 min) | 3–5 mA | ≈ 2 mA | |
| Running | 12–15 mA | ≈ 6 mA from BATT+, plus about 8 mA from ACC | ACC side covers the opto LEDs and amp LED, plus whatever the amp remote input draws. |

The VIM3 itself (several watts, peaking with USB camera, GNSS and touch) is **not** in this budget because this board doesn't power it.

## Parts and EasyEDA

LCSC numbers in the BOM were checked against JLCPCB/LCSC listings: TPS560430XDBVR C524782, EL817S1(C)(TU)-F C106900, SWPA4030S180MT C96895, BZT52C12-7-F C124196, SMBJ18A C49301917. The AO3400A, AO3401A, SS34, SS14, 1N4148W, 0603 resistors and 0603/0805/1206 capacitors come from the JLCPCB basic-parts list. The TPS560430 pinout, 18µH inductor, feedback network and 100nF bootstrap follow TI's datasheet recommendations for 5V output.

**Honest caveats:**
- I could not run EasyEDA Pro here, so the import itself is untested. The file opens and exports a clean netlist in KiCad 7.
- Footprint names in the file are KiCad library names, and EasyEDA may not map them. Don't draw footprints by hand. After import, swap each part to its EasyEDA library part by searching its LCSC number from the BOM ("Replace component"). That brings EasyEDA's own verified symbol and footprint.
- Connectors, the two PTC fuses and the LED have no LCSC number in the BOM on purpose. Pick them in the EasyEDA library by description: 5.08mm 5-pin pluggable terminal block, 2x20 2.54mm shrouded box header, two 1x20 2.54mm female headers for the Pico, JST-PH 2/3/4-pin, 1206 0.2A and 1812 0.75A 30V PTCs, 0805 green LED.
- Pico sockets: J3 pad n = Pico pin n. J4 pad n = Pico pin 20+n, and J4 pad 1 sits opposite J3 pad 20. Place the two rows 17.78mm (0.7") apart.

## Open questions (answers change the design)

1. **VIM3 header orientation.** The Khadas pinout lists pins 1–20 in one row and 21–40 in the other, and puts pin 1 opposite pin 21. J2's pad mapping depends on that. Please confirm with a multimeter before ordering: pins 1 and 2 (5V) should sit next to each other in the same row.
2. **VIM3 main power.** How is the VIM3 powered in the car today? This board leaves it alone. If you want the board to supply it (a 12V to 5V/5A buck, or 12V into the USB-C PD path), that is a sizeable addition, so I'd like your answer first.
3. **Power key wiring.** GP5 presses the VIM3 POWER key (GPIOAO_7), which isn't on the 40-pin header. J5 assumes a 2-wire lead to the key's pad, like I expect the perfboard has. Is that right?
4. **Light sensor bus.** `bh1750d` opens `/dev/i2c-1`, but the base DT only enables I2C_AO (pins 25/26). I2C_M3 (pins 22/23) is only enabled in the TS050 overlay, and U-Boot doesn't apply the DTBO. Which pins is the BH1750 on today? Jumpers R25–R28 cover both cases.
5. **Backlight signals.** J6 passes BL_EN and BL_PWM through at 3.3V with 100R. Does your display's backlight input accept 3.3V logic, or does it need 5V or a switched supply?
6. **Amp remote control.** Should the Pico (GP11, default) or Android (VIM3 pin 37) switch it? Either way it needs a small firmware or VHAL change, which I haven't made.
7. What is "not good enough" about the perfboard today (false wakes, missed reverse, noise)? That tells me which part of this design to harden further.

Sources for the VIM3 header: [Khadas VIM3 GPIO pinout](https://khadas.github.io/android/vim3/GPIOPinout.html), [Adafruit Blinka VIM3 issue](https://github.com/adafruit/Adafruit_Blinka/issues/564).
