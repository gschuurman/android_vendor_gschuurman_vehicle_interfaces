#!/vendor/bin/sh

log_info() { log -p i -t "SchuurmanInit" "$1"; }
log_error() { log -p e -t "SchuurmanInit" "$1"; }

log_info "Searching for PWM chip at address 19000 (PWM_EF)..."

FOUND_CHIP=""
PWM_BASE=""

# 1. ZOEK DE JUISTE CHIP
# We loopen door pwmchip0 t/m pwmchip9
for i in 0 1 2 3 4 5 6 7 8 9; do
    DEVICE_LINK="/sys/class/pwm/pwmchip$i/device/of_node"
    
    if [ -L "$DEVICE_LINK" ]; then
        # Lees waar de link naartoe wijst
        LINK_TARGET=$(readlink "$DEVICE_LINK")
        
        # Check of '19000' in het pad voorkomt
        if echo "$LINK_TARGET" | grep -q "19000"; then
            FOUND_CHIP="pwmchip$i"
            log_info "FOUND MATCH: $FOUND_CHIP points to 19000!"
            break
        fi
    fi
done

if [ -z "$FOUND_CHIP" ]; then
    log_error "FATAL: Could not find PWM chip with address 19000!"
    exit 1
fi

# 2. CONFIGUREREN
CHANNEL=$(getprop ro.vendor.vehicle.pwm.channel 1)
PWM_BASE="/sys/class/pwm/$FOUND_CHIP"
PWM_PATH="$PWM_BASE/pwm$CHANNEL"

# Export
if [ ! -d "$PWM_PATH" ]; then
    log_info "Exporting channel $CHANNEL on $FOUND_CHIP..."
    echo $CHANNEL > "$PWM_BASE/export"
fi

# Wacht loop
CNT=0
while [ ! -f "$PWM_PATH/duty_cycle" ]; do
    if [ $CNT -ge 20 ]; then
        log_error "Timed out waiting for $PWM_PATH..."
        exit 1
    fi
    sleep 0.1
    CNT=$((CNT + 1))
done

# 3. PERMISSIES & SELINUX
# Restorecon is belangrijk voor dynamische files!
restorecon -R "$PWM_PATH"

for FILE in duty_cycle enable period; do
    TARGET="$PWM_PATH/$FILE"
    if [ -f "$TARGET" ]; then
        chown vehicle_network:system "$TARGET"
        chmod 0660 "$TARGET"
    fi
done

log_info "Setup complete on $FOUND_CHIP."