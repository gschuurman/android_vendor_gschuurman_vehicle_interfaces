#!/vendor/bin/sh
# mcu_flash FILE.uf2 : install peripheral board MCU firmware over its BOOTSEL drive (adb root).
#
# Run it twice when the MCU is running normally:
#  1. `mcutool bootsel --force` reboots the MCU into the ROM bootloader. With R72 a pull-down
#     (rev 0.6 as built) that cuts the VIM3 supply: the VIM3 must be on USB-C power, and even
#     then the switch-over reboots it. FILE is synced first so it survives that.
#  2. After the VIM3 is back, the MCU is still in BOOTSEL (drive "RP2350"): FILE is copied onto
#     the drive, the MCU reboots into it and switches the VIM3 supply back on (another reboot
#     with a pull-down R72).
# On an MCU with the A/B partition table the bootrom writes the image into the slot that is not
# booting; the image's (inverted) bootrom version decides which slot boots afterwards.
F=$1
M=/data/local/tmp/rp2
[ -n "$F" ] && [ -f "$F" ] || { echo "usage: mcu_flash FILE.uf2"; exit 2; }

drive() {
    for b in /sys/block/sd*; do
        [ -e "$b/device/model" ] && grep -q RP2350 "$b/device/model" &&
            { echo /dev/block/$(basename "$b")1; return 0; }
    done
    return 1
}

D=$(drive)
if [ -z "$D" ]; then
    sync
    echo "MCU -> BOOTSEL. With a pull-down R72 the VIM3 loses its supply now and reboots on"
    echo "USB-C power; then run: mcu_flash $F"
    sync
    mcutool bootsel --force
    for i in $(seq 1 40); do D=$(drive) && break; sleep 0.5; done
    [ -z "$D" ] && { echo "no RP2350 drive"; exit 1; }
fi
for i in $(seq 1 10); do [ -e "$D" ] && break; sleep 0.3; done
mkdir -p $M
mount -t vfat "$D" $M || { echo "mount $D failed"; exit 1; }
cp "$F" $M/ && sync
echo "copied $F rc=$? (the MCU reboots into it; with a pull-down R72 the VIM3 reboots too)"
umount $M 2>/dev/null
for i in $(seq 1 20); do drive >/dev/null || { echo "drive gone"; exit 0; }; sleep 0.5; done
echo "drive still present"
exit 1
