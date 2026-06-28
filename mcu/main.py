import machine
import time
from micropython import const

# =========================================================
# SIMPLE VEHICLE POWER MANAGER FOR PICO 2 / KHADAS VIM3
# =========================================================
#
# Pinout:
#   GP27 -> ACC input          (RP2350 E9 fix applied — Schmitt disabled)
#   GP21 -> Reverse input
#   GP2  -> Reverse output to SBC
#   GP5  -> Power button output to SBC
#   GP6  -> SBC 3.3V power sense input
#   GP10 -> Service mode input (jumper to 3.3V to disable actions)
#
# Power strategy:
#   STATE_OFF           ~1–2 mA   lightsleep + pin IRQ wakeup on ACC
#   STATE_SLEEP_PENDING ~3–5 mA   lightsleep(1000) during 15-min wait
#   STATE_ON            ~12–15 mA active at 48 MHz (car is running)
# =========================================================

# ---- Reduce CPU clock first — saves ~40% active power ---
machine.freq(48_000_000)

# ---------------- PIN CONFIG ----------------

PIN_ACC_IN        = const(27)
PIN_REV_IN        = const(21)
PIN_REV_OUT       = const(2)
PIN_PWR_BTN_OUT   = const(5)
PIN_SBC_PWR_SENSE = const(6)
PIN_SERVICE_MODE  = const(10)

# ---------------- TIMING ----------------

PWR_ON_PRESS_MS   = const(1000)
SLEEP_PRESS_MS    = const(120)
PWR_OFF_PRESS_MS  = const(3000)

ACC_DEBOUNCE_MS   = const(80)
CRANK_IGNORE_MS   = const(2500)
WAKE_SETTLE_MS    = const(1000)
FULL_OFF_DELAY_MS = const(15 * 60 * 1000)

LOOP_MS           = const(20)    # Active-state loop interval
BOOT_GRACE_MS     = const(10000)

BOOT_IF_ACC_HIGH  = True
DEBUG             = False

# ---------------- STATES ----------------

STATE_OFF           = const(0)
STATE_ON            = const(1)
STATE_SLEEP_PENDING = const(2)

# ---------------- RP2350 ERRATA E9 FIX ----------------
# GP27 Schmitt trigger can latch HIGH. The fix MUST be applied AFTER
# machine.Pin() initialises the pin — Pin() writes the pad register and
# would re-enable the Schmitt trigger if we disabled it first.

_PADS_BANK0_BASE = const(0x40038000)
_SCHMITT_BIT     = const(1 << 1)

def _disable_schmitt(pin_num):
    pad_addr = _PADS_BANK0_BASE + 0x4 + (pin_num * 0x4)
    machine.mem32[pad_addr] = machine.mem32[pad_addr] & ~_SCHMITT_BIT

# ---------------- HARDWARE ----------------

# RP2350 E9 latch-clear sequence for GP27:
#   1. Drive pin LOW as output — forces the latched state to reset
#   2. Reconfigure as input with pull-down
#   3. Disable Schmitt trigger AFTER Pin() so Pin() doesn't re-enable it
machine.Pin(PIN_ACC_IN, machine.Pin.OUT, value=0)
time.sleep_ms(5)
acc_in = machine.Pin(PIN_ACC_IN, machine.Pin.IN, machine.Pin.PULL_DOWN)
_disable_schmitt(PIN_ACC_IN)
rev_in          = machine.Pin(PIN_REV_IN,        machine.Pin.IN,  machine.Pin.PULL_DOWN)
rev_out         = machine.Pin(PIN_REV_OUT,       machine.Pin.OUT, value=0)
pwr_btn_out     = machine.Pin(PIN_PWR_BTN_OUT,   machine.Pin.OUT, value=0)
sbc_pwr_sense   = machine.Pin(PIN_SBC_PWR_SENSE, machine.Pin.IN,  machine.Pin.PULL_DOWN)
service_mode_in = machine.Pin(PIN_SERVICE_MODE,  machine.Pin.IN,  machine.Pin.PULL_DOWN)

# Onboard LED — GP25 on Pico 2. Debug signalling only.
led = machine.Pin(25, machine.Pin.OUT, value=0)

# ---------------- GLOBALS ----------------

state                = STATE_OFF
shutdown_deadline_ms = None
ignore_acc_until_ms  = 0
last_rev             = 0
boot_time_ms         = time.ticks_ms()

# Non-blocking debounce state
_acc_stable          = 0
_acc_candidate       = 0
_acc_candidate_since = 0

# ---------------- HELPERS ----------------

def log(msg):
    if DEBUG:
        print(msg)

# ---------------- LED DEBUG ----------------
# Patterns (only active when DEBUG = True):
#   Boot            — 3 quick blinks on startup
#   ACC detected    — LED solid ON while ACC is HIGH
#   Power btn press — LED flashes rapidly for the duration of the press

def led_set(on):
    if DEBUG:
        led.value(1 if on else 0)

def led_blink(times, on_ms=80, off_ms=80):
    if not DEBUG:
        return
    for _ in range(times):
        led.value(1)
        time.sleep_ms(on_ms)
        led.value(0)
        time.sleep_ms(off_ms)

def ticks_after(delta_ms):
    return time.ticks_add(time.ticks_ms(), delta_ms)

def ticks_reached(deadline_ms):
    return time.ticks_diff(time.ticks_ms(), deadline_ms) >= 0

def acc_is_high():
    return acc_in.value() == 1

def sbc_has_power():
    return sbc_pwr_sense.value() == 1

def service_mode_active():
    return service_mode_in.value() == 1

def boot_grace_active():
    return time.ticks_diff(time.ticks_ms(), boot_time_ms) < BOOT_GRACE_MS

def press_power_button(duration_ms):
    log("Power button press: {}ms".format(duration_ms))
    pwr_btn_out.value(1)
    # Flash LED rapidly  for the full duration so you can see the press happening
    if DEBUG:
        elapsed = 0
        while elapsed < duration_ms:
            led.value(1); time.sleep_ms(50)
            led.value(0); time.sleep_ms(50)
            elapsed += 100
    else:
        time.sleep_ms(duration_ms)
    pwr_btn_out.value(0)
    log("Power button released")

def _seed_debounce():
    """Hard-read ACC and reset debounce state. Call after waking from sleep."""
    global _acc_stable, _acc_candidate, _acc_candidate_since
    raw = acc_in.value()
    _acc_stable = raw
    _acc_candidate = raw
    _acc_candidate_since = time.ticks_ms()
    return raw

def read_acc_debounced():
    """
    Non-blocking debounce — no sleeping. Returns stable ACC value.
    Commits a new value only after it holds steady for ACC_DEBOUNCE_MS.
    """
    global _acc_stable, _acc_candidate, _acc_candidate_since
    raw = acc_in.value()
    if raw == _acc_stable:
        _acc_candidate = raw
        _acc_candidate_since = time.ticks_ms()
        return _acc_stable
    if raw != _acc_candidate:
        _acc_candidate = raw
        _acc_candidate_since = time.ticks_ms()
    elif time.ticks_diff(time.ticks_ms(), _acc_candidate_since) >= ACC_DEBOUNCE_MS:
        _acc_stable = raw
    return _acc_stable

def update_reverse_output():
    global last_rev
    current_rev = rev_in.value()
    if current_rev != last_rev:
        rev_out.value(current_rev)
        last_rev = current_rev

# ---------------- POWER SAVING WAITS ----------------

def _irq_wake(pin):
    """Empty IRQ handler — existence is enough to wake the chip from lightsleep."""
    pass

def low_power_idle():
    """
    STATE_OFF power saving: ~1–2 mA.
    Puts the Pico into lightsleep and wakes on ACC rising OR reverse change.
    Falls back to a 5-second poll as a safety net against missed edges.
    Reverse is updated after each wake so the output stays correct even
    while the car is off (belt-and-braces — reverse shouldn't be engaged
    with ACC low, but we handle it cleanly regardless).
    """
    log("Entering low-power idle (lightsleep)")
    _BOTH = machine.Pin.IRQ_RISING | machine.Pin.IRQ_FALLING
    acc_in.irq(trigger=machine.Pin.IRQ_RISING, handler=_irq_wake)
    rev_in.irq(trigger=_BOTH,                  handler=_irq_wake)

    while True:
        machine.lightsleep(5000)        # Wakes on any IRQ or after 5s
        update_reverse_output()         # Mirror reverse immediately on wake

        if acc_in.value() == 1:
            time.sleep_ms(ACC_DEBOUNCE_MS)
            if acc_in.value() == 1:
                break

    acc_in.irq(handler=None)
    rev_in.irq(handler=None)
    _seed_debounce()
    log("Woke from low-power idle — ACC confirmed HIGH")

def sleep_pending_wait():
    """
    STATE_SLEEP_PENDING power saving: ~3–5 mA.
    Replaces the busy 20ms loop during the 15-minute countdown with
    lightsleep(1000). Wakes immediately on ACC rising OR reverse change
    so the reverse output stays live while the SBC is shutting down.
    """
    log("Entering low-power sleep-pending wait")
    _BOTH = machine.Pin.IRQ_RISING | machine.Pin.IRQ_FALLING
    acc_in.irq(trigger=machine.Pin.IRQ_RISING, handler=_irq_wake)
    rev_in.irq(trigger=_BOTH,                  handler=_irq_wake)

    while state == STATE_SLEEP_PENDING:
        machine.lightsleep(1000)

        update_reverse_output()         # Mirror reverse immediately on wake

        if acc_in.value() == 1:         # Car turned back on
            break

        if shutdown_deadline_ms is not None and ticks_reached(shutdown_deadline_ms):
            break                       # 15-minute deadline hit

    acc_in.irq(handler=None)
    rev_in.irq(handler=None)
    _seed_debounce()
    log("Woke from sleep-pending wait")

# ---------------- ACTIONS ----------------

def wake_or_power_on_sbc():
    global state, shutdown_deadline_ms, ignore_acc_until_ms

    if service_mode_active():
        log("SERVICE MODE: wake/power-on skipped")
        return

    shutdown_deadline_ms = None

    if sbc_has_power():
        log("SBC power present — short wake press")
        press_power_button(SLEEP_PRESS_MS)
    else:
        log("SBC off — power-on press")
        press_power_button(PWR_ON_PRESS_MS)

    state = STATE_ON
    ignore_acc_until_ms = ticks_after(WAKE_SETTLE_MS)
    log("State -> ON")

def request_sbc_sleep():
    global state, shutdown_deadline_ms

    if service_mode_active():
        log("SERVICE MODE: sleep request skipped")
        return

    log("Requesting SBC sleep")
    press_power_button(SLEEP_PRESS_MS)
    state = STATE_SLEEP_PENDING
    shutdown_deadline_ms = ticks_after(FULL_OFF_DELAY_MS)
    log("State -> SLEEP_PENDING (shutdown in {}ms)".format(FULL_OFF_DELAY_MS))

def force_sbc_power_off():
    global state, shutdown_deadline_ms

    if service_mode_active():
        log("SERVICE MODE: power-off skipped")
        return

    log("Forcing SBC power off")
    press_power_button(PWR_OFF_PRESS_MS)
    state = STATE_OFF
    shutdown_deadline_ms = None
    log("State -> OFF")

# ---------------- STATE MACHINE ----------------

def handle_boot():
    global state, shutdown_deadline_ms, ignore_acc_until_ms, boot_time_ms, last_rev

    boot_time_ms = time.ticks_ms()
    rev_out.value(0)
    pwr_btn_out.value(0)
    shutdown_deadline_ms = None
    ignore_acc_until_ms  = 0
    last_rev = rev_in.value()

    led_blink(3)            # 3 blinks = booted successfully
    log("Boot start (48MHz)")
    if service_mode_active():
        log("SERVICE MODE ACTIVE")

    raw = _seed_debounce()

    if BOOT_IF_ACC_HIGH and raw == 1:
        wake_or_power_on_sbc()
    elif sbc_has_power():
        log("Boot with ACC low, SBC rail high — sleep pending")
        state = STATE_SLEEP_PENDING
        shutdown_deadline_ms = ticks_after(FULL_OFF_DELAY_MS)
    else:
        state = STATE_OFF
        log("Boot with ACC low — going to low-power idle")

def handle_acc_rising():
    global shutdown_deadline_ms
    log("ACC rising edge")
    led_set(True)           # LED ON — ACC signal confirmed received
    shutdown_deadline_ms = None
    if state != STATE_ON:
        wake_or_power_on_sbc()
    else:
        log("Already ON — no action")

def handle_acc_falling():
    led_set(False)          # LED OFF — ACC dropped
    now = time.ticks_ms()

    if time.ticks_diff(ignore_acc_until_ms, now) > 0:
        log("ACC fall ignored — wake settle window")
        return

    if boot_grace_active():
        log("ACC fall ignored — boot grace window")
        return

    log("ACC falling edge")

    if state == STATE_ON:
        crank_deadline = ticks_after(CRANK_IGNORE_MS)
        log("Crank-ignore window: {}ms".format(CRANK_IGNORE_MS))

        while not ticks_reached(crank_deadline):
            if acc_is_high():
                log("ACC recovered in crank-ignore window")
                return
            update_reverse_output()
            time.sleep_ms(20)

        if not acc_is_high():
            request_sbc_sleep()
    else:
        log("ACC low, state != ON — no action")

def process_acc_change(new_acc):
    if new_acc == 1:
        handle_acc_rising()
    else:
        handle_acc_falling()

def process_shutdown_timer():
    if state != STATE_SLEEP_PENDING:
        return
    if acc_is_high():
        log("ACC returned before shutdown deadline")
        wake_or_power_on_sbc()
        return
    if shutdown_deadline_ms is not None and ticks_reached(shutdown_deadline_ms):
        log("Shutdown deadline reached with ACC low")
        force_sbc_power_off()

# ---------------- MAIN ----------------

def main():
    # ------------------------------------------------------------------
    # FIRMWARE UPLOAD SAFE WINDOW
    # Blinks the LED for BOOT_SAFE_MS before doing anything.
    # Connect Thonny and press Ctrl+C during this window to interrupt.
    # If ACC is low and the device would normally go straight to
    # lightsleep, this window keeps it awake long enough to recover.
    # Set BOOT_SAFE_MS = 0 to disable once you no longer need it.
    # ------------------------------------------------------------------
    BOOT_SAFE_MS = 8000
    deadline = time.ticks_add(time.ticks_ms(), BOOT_SAFE_MS)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        led.value(1); time.sleep_ms(100)
        led.value(0); time.sleep_ms(100)
    led.value(0)

    handle_boot()
    last_acc = _acc_stable

    while True:

        # STATE_OFF: deep idle — ~1–2 mA
        # Blocks here in lightsleep until ACC goes high, then falls through.
        if state == STATE_OFF:
            low_power_idle()
            last_acc = _acc_stable
            if _acc_stable == 1:
                handle_acc_rising()
            continue

        # STATE_SLEEP_PENDING: light idle during 15-min countdown — ~3–5 mA
        # Blocks here in lightsleep(1000) until deadline or ACC returns.
        if state == STATE_SLEEP_PENDING:
            sleep_pending_wait()
            last_acc = _acc_stable
            process_shutdown_timer()
            continue

        # STATE_ON: active monitoring at 48 MHz — ~12–15 mA
        update_reverse_output()

        current_acc = read_acc_debounced()
        if current_acc != last_acc:
            last_acc = current_acc
            process_acc_change(current_acc)

        time.sleep_ms(LOOP_MS)

try:
    main()
except Exception as e:
    print("FATAL:", e)
    while True:
        time.sleep_ms(1000)