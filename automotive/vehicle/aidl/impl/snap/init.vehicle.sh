#!/vendor/bin/sh

log_info()  { log -p i -t "SchuurmanInit" "$1"; }
log_warn()  { log -p w -t "SchuurmanInit" "$1"; }
log_error() { log -p e -t "SchuurmanInit" "$1"; }

log_info "Searching for PWM chip at address 19000 (PWM_EF)..."

FOUND_CHIP=""
PWM_BASE=""
PWM_PATH=""

# 1. ZOEK DE JUISTE CHIP (PWM)
for i in 0 1 2 3 4 5 6 7 8 9; do
    DEVICE_NODE="/sys/class/pwm/pwmchip$i/device/of_node"
    if [ -e "$DEVICE_NODE" ]; then
        LINK_TARGET=$(readlink -f "$DEVICE_NODE" 2>/dev/null)
        if [ -z "$LINK_TARGET" ]; then LINK_TARGET="$DEVICE_NODE"; fi

        if echo "$LINK_TARGET" | grep -q "19000"; then
            FOUND_CHIP="pwmchip$i"
            log_info "FOUND MATCH: $FOUND_CHIP (link: $LINK_TARGET)"
            break
        fi
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

# 2. CONFIGUREREN PWM
CHANNEL=$(getprop ro.vendor.vehicle.pwm.channel 1)
if [ -z "$CHANNEL" ]; then CHANNEL=1; fi

PWM_BASE="/sys/class/pwm/$FOUND_CHIP"
PWM_PATH="$PWM_BASE/pwm$CHANNEL"

log_info "Using PWM_BASE=$PWM_BASE PWM_PATH=$PWM_PATH CHANNEL=$CHANNEL"

if [ ! -d "$PWM_PATH" ]; then
    log_info "Exporting channel $CHANNEL on $FOUND_CHIP..."
    echo "$CHANNEL" > "$PWM_BASE/export" 2>/dev/null || {
        log_error "Failed to write to $PWM_BASE/export"
        exit 1
    }
fi

CNT=0
MAXCNT=50
while [ ! -e "$PWM_PATH/duty_cycle" -a $CNT -lt $MAXCNT ]; do
    sleep 0.1 2>/dev/null || sleep 1
    CNT=$((CNT + 1))
done

if [ ! -e "$PWM_PATH/duty_cycle" ]; then
    log_error "Timed out waiting for $PWM_PATH/duty_cycle"
    exit 1
fi

# 3. PERMISSIES & SELINUX (PWM)
for FILE in duty_cycle enable period; do
    TARGET="$PWM_PATH/$FILE"
    if [ -e "$TARGET" ]; then
        if command -v restorecon >/dev/null 2>&1; then restorecon "$TARGET" 2>/dev/null; fi
        if getent group vehicle_network >/dev/null 2>&1; then
            chown vehicle_network:system "$TARGET" 2>/dev/null
        else
            chown system:system "$TARGET" 2>/dev/null
        fi
        chmod 0660 "$TARGET" 2>/dev/null
    fi
done

# 4. GPIO PERMISSIONS (CRITICAL FIX FOR GEAR DETECTION)
GPIO_CHIP_PROP=$(getprop ro.vendor.vehicle.gpio.chip)
if [ -z "$GPIO_CHIP_PROP" ]; then
    GPIO_CHIP="gpiochip0"
else
    GPIO_CHIP="$GPIO_CHIP_PROP"
fi

GPIO_DEV="/dev/$GPIO_CHIP"
log_info "Setting permissions for GPIO Chip: $GPIO_DEV"

if [ -c "$GPIO_DEV" ]; then
    # chown the device to vehicle_network user
    if getent group vehicle_network >/dev/null 2>&1; then
        chown vehicle_network:system "$GPIO_DEV" 2>/dev/null || log_warn "Failed to chown $GPIO_DEV"
    else
        chown system:system "$GPIO_DEV" 2>/dev/null
    fi
    # allow read/write
    chmod 0660 "$GPIO_DEV" 2>/dev/null || log_warn "Failed to chmod $GPIO_DEV"
else
    log_error "GPIO Device $GPIO_DEV not found! Gear detection may fail."
fi

# 5. INITIAL STATE PWM
if [ -w "$PWM_PATH/enable" ]; then echo "0" > "$PWM_PATH/enable" 2>/dev/null; fi
if [ -w "$PWM_PATH/period" ]; then echo "30518" > "$PWM_PATH/period" 2>/dev/null; fi
if [ -w "$PWM_PATH/duty_cycle" ]; then echo $((30518 / 2)) > "$PWM_PATH/duty_cycle" 2>/dev/null; fi
if [ -w "$PWM_PATH/enable" ]; then echo "1" > "$PWM_PATH/enable" 2>/dev/null; fi

log_info "Setup complete."
exit 0