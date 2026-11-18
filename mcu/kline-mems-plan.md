# Plan: MEMS 1.9 over K-line → car status dashboard + overheat alarm

Status 2026-11-18: plan only. Hardware: K-line module on J10 (rev 0.6), arriving in a few weeks.

Sources: github.com/james-portman/rover-mems-documentation (`ECUs/1.x-ECU-all/diagnostics`),
rover-mems-agent (`ecu-19.go`, `ecu-1x-shared.go`), rover-mems-android-application. The agent and app are
**GPL-3.0**: implement from the documented protocol, don't copy their code into our tree.

## What MEMS 1.9 gives us (and what it doesn't)

Protocol (MEMS 1.x, 1.9 only differs in the wake-up):
- K-line, 9600 8N1, single-byte commands, ECU echoes each byte then answers.
- Wake: ISO 9141 5-baud address `0x16` (200 ms per bit, done as GPIO/UART-break bit-banging) →
  ECU `55 76 83` → send `0x7C` (inverted `0x83`) → ECU echoes `7C E9`. Then the 1.3/1.6 sequence:
  `CA`, `75`, `F4` (heartbeat, answer `F4 00`), `D0` (ECU ID, 4 bytes).
- Then alternate `0x80` and `0x7D`: data frames, first byte after the echo = frame length.
- `0x80`: RPM (bytes 1-2), **coolant °C = byte 3 − 55**, ambient (4), intake air (5), fuel rail (6,
  often 0xFF), MAP kPa (7), battery 0.1 V (8), throttle pot 0.02 V (9), idle switch, fault bytes
  0x0D/0x0E (bit 0 of 0x0D = coolant sensor fault), idle setpoint/steps, ignition advance, coil dwell.
- `0x7D`: throttle angle, lambda voltage/status, closed loop, fuel trim, idle position, fan 1/2 bits.
- `0xCC` clears faults; 0x0x/0x1x/0x6x/0x8x/0x9x are actuator tests and adjustments.

**No oil temperature.** The MGF's MEMS 1.9 has no oil temp input. Oil temp (and ideally oil pressure)
needs an aftermarket sender (e.g. a sump-plug or filter-sandwich NTC sender) read by an ADC. J10 has
no ADC and no spare pin (3V3, GND, GP32 TX, GP33 RX, GP28 EN, VBAT_KLINE, 5V_AON), and the RP2350B ADC
pins (GPIO40-47) are not broken out. Options: a small sensor board on the EXP header (EXP_GP24-27;
GPIO24/25 = I2C0 SDA/SCL) with an I2C ADC (e.g. ADS1115: oil temp, oil pressure, spare) plus the float
switch on GP26/27; or an ADC line on J10 in the next main-board revision.

**Head gasket caveat:** when coolant is lost, the ECU's coolant sensor can sit in steam/air and read
*low* or jump around instead of high. A high-threshold alarm alone can miss exactly the failure we
care about. The alarm logic therefore also flags: rate of change (fast rise), implausible drops while
the engine is warm and running, coolant sensor fault bit, and loss of ECU data while the engine
runs. A coolant level (float) switch in the expansion tank would be the best extra input (EXP header).

## Where each part lives

```
ECU ──K-line── L9637D (module, J10) ── UART0 GP32/33, EN GP28 ── MCU fw (kline.c)
     raw 0x80/0x7D frames over the existing HID link (new MCU_MSG_KLINE_FRAME)
                                   │
                         VHAL (McuLink → MemsDecoder)
     ENGINE_COOLANT_TEMP, ENGINE_OIL_TEMP, ENGINE_RPM (standard)  + vendor MEMS_* props
            │                                     │
   CarStatus app: dashboard UI        CarStatus alarm service (persistent, priv-app)
                                      → pause media + full-screen overlay + chime
```

1. **MCU firmware: transport only.** Wake-up, init, heartbeat, poll loop, reconnect when the ECU
   goes quiet / ignition cycles; forward each complete frame raw. No parsing of the frame layout in
   firmware: decoding changes then need a VHAL update (OTA), not an MCU flash (BOOTSEL reboots the
   VIM3 with the pull-down R72). Poll only while ACC is on; stop on SHUTDOWN_PREP. Never send
   actuator/adjustment commands (whitelist: `CA 75 F4 D0 80 7D`, optionally `CC` on request).
2. **VHAL: decode + publish.** One owner of the hidraw link already, gives permissions and multiple
   consumers (dashboard, alarm, HeadUnitDebug, cluster). Standard props where they exist
   (`ENGINE_COOLANT_TEMP`, `ENGINE_OIL_TEMP` from the sender, `ENGINE_RPM`), vendor props for the rest
   (IAT, MAP, battery, throttle, lambda, fuel trim, fan states, fault bits, ECU link state, frame age).
   Unit test the decoder against frames captured from the car.
3. **CarStatus app** (new, `automotive/carstatus`, like carmusic; no new fork): dashboard (coolant,
   oil, RPM, battery, IAT, MAP, fans, faults, live graphs, trip min/max), fault list, settings for
   thresholds. Read-only towards the ECU apart from an optional "clear faults".
4. **Alarm service in the same APK, persistent priv-app** (`android:persistent`, started at boot,
   restarted by the system), independent of whether the dashboard is open:
   - thresholds with hysteresis (coolant caution 105 °C / alarm 110 °C, confirmed by the user 2026-11-18; oil
     alarm per sender, e.g. 130 °C) + the plausibility rules above;
   - pause music: take transient audio focus with an emergency/safety usage (pauses media and AA
     audio) and also pause active MediaSessions explicitly (MEDIA_CONTENT_CONTROL, priv-app);
   - big full-screen overlay (TYPE_APPLICATION_OVERLAY, also above Android Auto projection) with the
     value, trend and "pull over, stop the engine"; chime; acknowledge button; re-alarm if it keeps
     rising; log every event (Room) so it can be reviewed later.
5. **Session logging (on request)** in the CarStatus app, for analysing a drive afterwards (e.g.
   coolant behaviour before a head gasket failure):
   - start/stop from the dashboard (optionally "auto-start every drive" as a setting); a small
     recording indicator while active; recording survives the dashboard closing (foreground service).
   - records every decoded field from both frames at full poll rate (~5-10 Hz) plus the **raw frames**
     (so a later decoder fix can re-decode old sessions), GNSS position/speed, battery, ambient/lux,
     and alarm/plausibility events as markers. User can add a marker ("steam", "gauge dropped").
   - storage: one Room/SQLite DB per session (or one DB, sessions table) on /data; a 1 h drive at
     10 Hz is a few MB. Retention setting (keep last N / auto-delete after N days).
   - on-device review: session list, graphs over time with zoom (coolant, IAT, RPM, fans, MAP,
     lambda, trims) and event markers; coolant vs fan-state view is the useful one for cooling issues.
   - export: CSV (one row per sample) + the raw-frame log, shared to USB stick / adb pull / share
     sheet, for analysis on the PC.
   - ACC off / deep sleep: close the session cleanly on SHUTDOWN_PREPARE; a new drive starts a new
     session.
6. **Optional MCU-side backstop:** the firmware can still read byte 3 of the 0x80 frame and drive a
   buzzer/LED on a spare pin if coolant passes a hard limit, so an Android hang doesn't silence it.

## Steps
1. Module design: L9637D + K-line protection on J10; separate sensor board (I2C ADC + float switch)
   on the EXP header if oil temp/pressure and coolant level are wanted.
2. MCU: `kline.c` (5-baud wake via GPIO, then UART0), protocol msg, host test with a fake ECU.
3. VHAL: MemsDecoder + props + tests; HeadUnitDebug page with raw frames.
4. Capture real frames from the car (idle, warm-up, fan on) to confirm offsets.
5. CarStatus app: alarm service first, then the dashboard, then session logging + export.
6. Bench test of the alarm with injected values (mcutool/VHAL debug inject), then in the car.
