# Vehicle Power Manager (MCU)

MicroPython firmware for a Raspberry Pi Pico 2 (RP2350) that acts as a power
manager between a vehicle's ignition and a single-board computer (SBC) such as
a Khadas VIM3. It watches the ACC (accessory/ignition) line and drives the
SBC's power button to turn it on, sleep it, and fully power it off, while
mirroring the reverse-gear signal through to the SBC.

The firmware is designed for low standby current — it keeps the Pico in
`lightsleep` whenever the car is off and only runs at full speed while the car
is running.

## Hardware

Target: **Raspberry Pi Pico 2 / RP2350**, CPU clocked down to **48 MHz** to
save power.

### Pinout

| Pin   | Direction | Function |
|-------|-----------|----------|
| GP27  | Input     | ACC (ignition) sense — RP2350 E9 Schmitt fix applied |
| GP21  | Input     | Reverse gear sense |
| GP2   | Output    | Reverse output to SBC |
| GP5   | Output    | Power-button output to SBC |
| GP6   | Input     | SBC 3.3 V power-rail sense |
| GP10  | Input     | Service-mode jumper (tie to 3.3 V to disable all actions) |
| GP25  | Output    | Onboard LED — debug signalling only |

All sense inputs use internal pull-downs and are active-high (drive to 3.3 V).

## Power states

| State                 | Current   | Behaviour |
|-----------------------|-----------|-----------|
| `STATE_OFF`           | ~1–2 mA   | `lightsleep` with pin-IRQ wakeup on ACC rising / reverse change |
| `STATE_SLEEP_PENDING` | ~3–5 mA   | `lightsleep(1000)` during the 15-minute shutdown countdown |
| `STATE_ON`            | ~12–15 mA | Active monitoring loop at 48 MHz (car running) |

## Behaviour

### Power on / wake
When ACC goes high (or the device boots with ACC already high), the manager
wakes or powers on the SBC:
- If the SBC rail is already powered (`GP6` high), it sends a short **wake**
  press (`SLEEP_PRESS_MS`, 120 ms).
- If the SBC is off, it sends a longer **power-on** press (`PWR_ON_PRESS_MS`,
  1000 ms).

### Crank handling
ACC typically dips while the starter motor cranks the engine. When ACC falls in
`STATE_ON`, the firmware waits out a **crank-ignore window**
(`CRANK_IGNORE_MS`, 2500 ms). If ACC recovers within that window, no action is
taken.

### Sleep and shutdown
If ACC stays low past the crank-ignore window, the manager requests an SBC
sleep with a short button press and enters `STATE_SLEEP_PENDING`, starting a
**15-minute** countdown (`FULL_OFF_DELAY_MS`). During this time:
- If ACC returns, the SBC is woken again.
- If the countdown expires with ACC still low, the manager sends a long
  **force-off** press (`PWR_OFF_PRESS_MS`, 3000 ms) and returns to
  `STATE_OFF`.

### Reverse mirroring
The reverse input (`GP21`) is mirrored to the reverse output (`GP2`) in all
states, including immediately after each wake from sleep, so the backup
camera signal stays live even while the SBC is shutting down.

### Service mode
Tying `GP10` to 3.3 V puts the unit in **service mode**: all power-button
actions (wake, power-on, sleep, power-off) are skipped. Useful for working on
the vehicle without the SBC cycling.

## Boot sequence

1. **Firmware-upload safe window** — on startup the LED blinks for
   `BOOT_SAFE_MS` (8000 ms). Connect Thonny and press `Ctrl+C` during this
   window to interrupt before the firmware takes over. Set `BOOT_SAFE_MS = 0`
   to disable.
2. `handle_boot()` reads the initial state:
   - ACC high (and `BOOT_IF_ACC_HIGH`) → wake/power on the SBC.
   - ACC low but SBC rail high → enter `STATE_SLEEP_PENDING` with the 15-minute
     countdown.
   - ACC low and SBC off → go to low-power idle (`STATE_OFF`).

## Key tunables

All timing constants live at the top of `main.py`:

| Constant            | Default     | Meaning |
|---------------------|-------------|---------|
| `PWR_ON_PRESS_MS`   | 1000 ms     | Power-on button press |
| `SLEEP_PRESS_MS`    | 120 ms      | Short wake / sleep press |
| `PWR_OFF_PRESS_MS`  | 3000 ms     | Force power-off press |
| `ACC_DEBOUNCE_MS`   | 80 ms       | ACC input debounce time |
| `CRANK_IGNORE_MS`   | 2500 ms     | Crank dip ignore window |
| `WAKE_SETTLE_MS`    | 1000 ms     | Ignore ACC falls just after waking |
| `FULL_OFF_DELAY_MS` | 15 min      | Sleep-to-power-off countdown |
| `BOOT_GRACE_MS`     | 10000 ms    | Ignore ACC falls just after boot |
| `LOOP_MS`           | 20 ms       | Active-state loop interval |
| `BOOT_IF_ACC_HIGH`  | `True`      | Power on the SBC if ACC is high at boot |
| `DEBUG`             | `False`     | Enable serial logging and LED patterns |

## Debug LED patterns

Active only when `DEBUG = True`:
- **Boot** — 3 quick blinks on startup.
- **ACC detected** — LED solid on while ACC is high.
- **Power-button press** — LED flashes rapidly for the duration of the press.

## RP2350 errata E9

GP27's input Schmitt trigger can latch high on the RP2350. The firmware works
around this by:
1. Driving GP27 low as an output to clear the latch.
2. Reconfiguring it as an input with pull-down.
3. Disabling the Schmitt trigger via the pad register **after** `Pin()` runs
   (so `Pin()` doesn't re-enable it).

## Installation

Copy `main.py` to the Pico's filesystem (e.g. with [Thonny](https://thonny.org/)
or `mpremote`). It runs automatically on boot. Use the boot safe window to
interrupt and re-flash.
