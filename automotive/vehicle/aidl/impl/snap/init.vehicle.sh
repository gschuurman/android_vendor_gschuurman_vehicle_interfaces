#!/vendor/bin/sh

log_info()  { log -p i -t "SchuurmanInit" "$1"; }
log_warn()  { log -p w -t "SchuurmanInit" "$1"; }
log_error() { log -p e -t "SchuurmanInit" "$1"; }

log_info "Searching for PWM chip at address 19000 (PWM_EF)..."

FOUND_CHIP=""
PWM_BASE=""
PWM_PATH=""

# 1. ZOEK DE JUISTE CHIP
for i in 0 1 2 3 4 5 6 7 8 9; do
    DEVICE_NODE="/sys/class/pwm/pwmchip$i/device/of_node"

    # use readlink -f if present, otherwise try to inspect file content
    if [ -e "$DEVICE_NODE" ]; then
        # prefer readlink -f output if it's a symlink
        LINK_TARGET=$(readlink -f "$DEVICE_NODE" 2>/dev/null)
        if [ -z "$LINK_TARGET" ]; then
            # fallback: list children or use path itself
            LINK_TARGET="$DEVICE_NODE"
        fi

        if echo "$LINK_TARGET" | grep -q "19000"; then
            FOUND_CHIP="pwmchip$i"
            log_info "FOUND MATCH: $FOUND_CHIP (link: $LINK_TARGET)"
            break
        fi

        # extra: if of_node is a dir, inspect files for hint
        if [ -d "$DEVICE_NODE" ]; then
            if grep -q "19000" "$DEVICE_NODE"/* 2>/dev/null; then
                FOUND_CHIP="pwmchip$i"
                log_info "FOUND MATCH (inspect): $FOUND_CHIP"
                break
            fi
        fi
    fi
done

if [ -z "$FOUND_CHIP" ]; then
    log_error "FATAL: Could not find PWM chip with address 19000!"
    exit 1
fi

# 2. CONFIGUREREN
CHANNEL=$(getprop ro.vendor.vehicle.pwm.channel 1)
if [ -z "$CHANNEL" ]; then
    CHANNEL=1
fi

PWM_BASE="/sys/class/pwm/$FOUND_CHIP"
PWM_PATH="$PWM_BASE/pwm$CHANNEL"

log_info "Using PWM_BASE=$PWM_BASE PWM_PATH=$PWM_PATH CHANNEL=$CHANNEL"

# Export channel if needed
if [ ! -d "$PWM_PATH" ]; then
    log_info "Exporting channel $CHANNEL on $FOUND_CHIP..."
    echo "$CHANNEL" > "$PWM_BASE/export" 2>/dev/null || {
        log_error "Failed to write to $PWM_BASE/export"
        exit 1
    }
fi

# Wait until pwm channel nodes appear (give up after ~5s)
CNT=0
MAXCNT=50  # 50 * 0.1s = 5s
SLEEP_MS=0.1

while [ ! -e "$PWM_PATH/duty_cycle" -a $CNT -lt $MAXCNT ]; do
    # Use sleep with fractional seconds if available; otherwise fallback to 1s
    if sleep 0.1 2>/dev/null; then
        : # slept 0.1s
    else
        sleep 1
    fi
    CNT=$((CNT + 1))
done

if [ ! -e "$PWM_PATH/duty_cycle" ]; then
    log_error "Timed out waiting for $PWM_PATH/duty_cycle (waited $CNT loops)"
    ls -ld "$PWM_BASE" "$PWM_PATH" 2>/dev/null | while read -r line; do log_warn "$line"; done
    exit 1
fi

# 3. PERMISSIES & SELINUX
# restorecon can be heavy; apply to the files we need
for FILE in duty_cycle enable period; do
    TARGET="$PWM_PATH/$FILE"
    if [ -e "$TARGET" ]; then
        # try restorecon on the file (if available)
        if command -v restorecon >/dev/null 2>&1; then
            restorecon "$TARGET" 2>/dev/null || log_warn "restorecon failed on $TARGET"
        fi

        # chown/chmod - pick sensible defaults; adjust user:group for your device
        if getent group vehicle_network >/dev/null 2>&1; then
            chown vehicle_network:system "$TARGET" 2>/dev/null || log_warn "chown failed on $TARGET"
        else
            chown system:system "$TARGET" 2>/dev/null || log_warn "chown fallback failed on $TARGET"
        fi
        chmod 0660 "$TARGET" 2>/dev/null || log_warn "chmod failed on $TARGET"
    fi
done

# Optional: set a safe initial state (disable, set period and duty) before any userspace touches it.
# Be careful: some drivers don't accept writes to period while enabled; disable first.
if [ -w "$PWM_PATH/enable" ]; then
    echo "0" > "$PWM_PATH/enable" 2>/dev/null || log_warn "could not disable PWM (may already be disabled)"
fi

# Try to set a conservative period and duty if writable
if [ -w "$PWM_PATH/period" ]; then
    echo "30518" > "$PWM_PATH/period" 2>/dev/null || log_warn "period write failed"
fi

if [ -w "$PWM_PATH/duty_cycle" ]; then
    echo $((30518 / 2)) > "$PWM_PATH/duty_cycle" 2>/dev/null || log_warn "duty write failed"
fi

if [ -w "$PWM_PATH/enable" ]; then
    echo "1" > "$PWM_PATH/enable" 2>/dev/null || log_warn "could not enable PWM (may already be enabled)"
fi

log_info "Setup complete on $FOUND_CHIP. status:"
ls -l "$PWM_PATH" 2>/dev/null | while read -r line; do log_info "$line"; done

exit 0
