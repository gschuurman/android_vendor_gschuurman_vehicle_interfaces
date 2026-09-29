# Pico 2 firmware in C (UNREVIEWED DRAFT)

This is a first draft of C firmware (Pico SDK) to replace the MicroPython `../main.py`. It has not been
reviewed, built or tested, and is committed only so the work isn't lost. Don't flash it.

## What it does

- `main.c`: main loop, inputs, outputs, backlight PWM, battery ADC and watchdog.
- `power_sm.c`: the ACC-driven power state machine (wake, sleep and shut down the VIM3 via its power
  key).
- `proto.c`: a line-based text protocol over USB CDC (`/dev/ttyACM*`) for querying and setting
  peripheral state.

## Known gaps

- **Pin map.** `src/board.h` follows an early rev 0.2 pin map. It doesn't match the final
  `../../PCB/rev0.2/DESIGN_rev02.md` yet. Missing are the display buttons, the GNSS UART/enable/reset,
  DAC mute, the TPS55288 enable and its I2C setup, and the amp remote sequencing. GP12 is used for a
  reverse output that the board no longer has.
- **Link to Android.** The recommended link is a composite USB device: HID keyed by VHAL property IDs,
  plus CDC for GNSS passthrough. This draft still speaks the older text protocol over CDC, and
  `../PROTOCOL.md`, which the code refers to, doesn't exist yet.
- **Build.** There is no `CMakeLists.txt`, so it doesn't build yet.
