#!/vendor/bin/sh

# Lees configuratie uit system.prop (met defaults voor VIM3)
CHIP=$(getprop ro.vendor.vehicle.pwm.chip pwmchip1)
CHANNEL=$(getprop ro.vendor.vehicle.pwm.channel 1)
GPIO_CHIP=$(getprop ro.vendor.vehicle.gpio.chip gpiochip0)

# 1. PWM Export (Dynamisch)
# Check of export al gebeurd is om errors te voorkomen
if [ ! -d "/sys/class/pwm/$CHIP/pwm$CHANNEL" ]; then
    echo "Exporting PWM: Chip=$CHIP, Channel=$CHANNEL"
    echo $CHANNEL > "/sys/class/pwm/$CHIP/export"
fi

# 2. PWM Permissies (Dynamisch)
# Wacht heel even tot sysfs de mappen heeft aangemaakt (race condition preventie)
sleep 0.1

PWM_PATH="/sys/class/pwm/$CHIP/pwm$CHANNEL"

if [ -d "$PWM_PATH" ]; then
    chown vehicle_network:system "$PWM_PATH/duty_cycle"
    chmod 0660 "$PWM_PATH/duty_cycle"
    
    chown vehicle_network:system "$PWM_PATH/enable"
    chmod 0660 "$PWM_PATH/enable"
    
    chown vehicle_network:system "$PWM_PATH/period"
    chmod 0660 "$PWM_PATH/period"
else
    echo "Error: PWM path $PWM_PATH not found!"
fi

# 3. GPIO Permissies (Dynamisch)
if [ -c "/dev/$GPIO_CHIP" ]; then
    chown vehicle_network:system "/dev/$GPIO_CHIP"
    chmod 0660 "/dev/$GPIO_CHIP"
fi