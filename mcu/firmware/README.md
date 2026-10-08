# Peripheral board firmware (RP2350B, board rev 0.6)

C firmware for the RP2350B on the car radio peripheral board, built with the Pico SDK and TinyUSB.
It replaces the MicroPython `../main.py` (which stays for the old perfboard and Pico 2 setup).
Not yet run on hardware: the rev 0.6 boards are on order.

## What it does

- **VIM3 power.** Switches the TPS55288 5 V supply (EN pin plus the MODE.OE bit over I2C), presses the
  VIM3 power key through the PhotoMOS U22, and follows Android's AAOS power protocol:
  ACC off → `AP_POWER_STATE_REQ SHUTDOWN_PREPARE/CAN_SLEEP` → Android suspends → after the off delay
  (15 min, settable) the MCU wakes it with the key and asks for `SHUTDOWN_ONLY` → when the VIM3 3.3 V
  rail drops the supply is cut. ACC back during any of this wakes or keeps the VIM3. Crank dips under
  2.5 s are ignored. Low battery (under 11.6 V for a minute while parked) ends the suspend early.
  State machine: `src/power_sm.c`, scenarios in `test/test_power_sm.c`.
- **Car inputs** (ISO A): ACC, reverse, illumination and handbrake, debounced, sent as `IGNITION_STATE`,
  `GEAR_SELECTION`, `NIGHT_MODE` and the raw handbrake bit. The VHAL turns the handbrake into
  `PARKING_BRAKE_ON`, falling back to GNSS speed while the wire has never been seen engaged.
- **Display.** Backlight enable and PWM (inverted, 32.768 kHz as before); brightness and screen power
  come from the VHAL. The screen button toggles the backlight directly and reports it.
- **Media keys.** Volume up/down and mute buttons are a standard USB HID consumer-control interface, so
  Android handles them as normal keys.
- **Audio.** DAC soft mute (XSMT) and the amp remote output (ISO A3), sequenced against pops: DACs
  unmute when the VHAL link is up (or 30 s after the VIM3 starts), the amp follows 0.5 s later and
  goes off first. Amp mode off / on / auto.
- **GNSS.** Switches the GNSS module supply (off while the VIM3 sleeps; V_BCKP stays on), reset and
  safeboot, and reads the module's NMEA on UART1 (autobaud 38400/9600/115200/230400) for
  `PERF_VEHICLE_SPEED` and the fix state. Android uses the module itself over its own USB port.
- **Monitoring.** Battery voltage, the 5 V rail, board temperature (NTC), BH1750 light level, USB
  phone-port power-good and over-current flags, TPS55288 fault flags.
- **USB hub.** Hub 1 is held in reset while the VIM3 is off.
- Watchdog (2 s). Unused pins are parked as inputs with the input buffer off (RP2350-E9).

## Link to the VHAL

A composite USB device, VID:PID `2e8a:ca50`:

- Interface 0: vendor HID (usage page 0xFF00), 64-byte reports, `/dev/hidraw*` on Android.
  Messages carry VHAL property IDs; the layout is in `../protocol/mcu_protocol.h`, shared with the
  VHAL. The VHAL sends a heartbeat every second; on each (re)connect the MCU sends its info and a full
  snapshot.
- Interface 1: HID consumer control (the display buttons).

No CDC serial port: the GNSS HAL opens every `/dev/ttyACM*` and changes baud rates, and the 1200-baud
bootloader trick must not fire by accident.

On the VIM3, `mcutool status | watch | set NAME V0 | bootsel` (adb root) shows and pokes the MCU.

## Pin map

`src/board.h`, taken from the rev 0.6 main-board netlist (U20). Rev 0.4's table in
`PCB/rev0.4/README.md` matches except that GPIO11/12/13/29/34 are now unconnected and GPIO28/32/33 go
to the K-line socket J10.

## Building

Needs CMake, `arm-none-eabi-gcc` and the Pico SDK 2.x (tested with SDK 2.2.0 and GCC 13.2).

```
export PICO_SDK_PATH=/path/to/pico-sdk     # or: cmake -DPICO_SDK_FETCH_FROM_GIT=on
cmake -S . -B build
cmake --build build -j
# -> build/carradio_mcu.uf2
make -C test                               # host tests: power state machine, NMEA, USB link
```

## Flashing

- **SWD** (J22: SWCLK, GND, SWDIO, RUN) with a Raspberry Pi Debug Probe:
  `openocd -f interface/cmsis-dap.cfg -f target/rp2350.cfg -c "program build/carradio_mcu.elf verify reset exit"`.
- **USB from a PC:** hold BOOTSEL (SW1), tap RESET (SW2); the chip shows up as a drive `RP2350`
  through hub 1. Copy the `.uf2` or use `picotool load -x`.
- **USB from the VIM3:** `mcutool bootsel`, then `picotool load -x carradio_mcu.uf2`. Only with the
  R72 change below; the tool refuses otherwise.

**R72 (rev 0.6).** R72 (100k) pulls VIM3_PWR_EN low, and the RP2350B's own pull-down is on during
reset. So any MCU reset, including the reboot into BOOTSEL, switches the TPS55288 off and the VIM3
loses power. Replacing R72 with a **10k pull-up to +3V3_MCU** keeps the supply on through MCU resets
(10k, because the internal pull-down of about 50k would hold a 100k pull-up below the EN threshold).
The firmware reads the pin at start-up and handles both: with the pull-up it adopts a running VIM3
after a reset. Cost of the pull-up: while the MCU is blank or held in reset, the TPS55288 sits enabled
with its output off and draws its standby current from the battery (not measured).

Note: while the VIM3 is off, the firmware holds hub 1 in reset, so a PC on the J2 breakout cable only
sees the MCU in BOOTSEL mode or with the service jumper fitted.

## Service jumper (JP1)

Fitted: the VIM3 is powered regardless of ACC, the power key is never pressed and the supply is never
cut. For bench work.

## Not done yet

- K-line (J10, GPIO28/32/33): pins parked; no MEMS 1.9 code.
- Lowest-power idle while parked: the MCU idles with WFE at the default clock. Dormant mode with ACC
  as the wake source would cut the parked current further.
- GNSS TX (GPIO4) is never driven, so with JP2 set to 2-3 (GNSS RX from the MCU) nothing reaches the
  module's RX.
- Everything is untested on hardware. First checks: TPS55288 OE over I2C, power-key timing with the
  PhotoMOS, the R72 behaviour, USB re-enumeration after the VIM3 resumes.
