#!/usr/bin/env python3
"""Write a UF2 that erases flash sectors 0 and 1 of an RP2350 (where `picotool partition create`
puts the partition table), so the chip goes back to a flat image at the start of flash.

Family "absolute" (0xe48bff57): the A/B table allowed absolute writes to unpartitioned space,
which sectors 0-1 are (the partitions start at sector 2). Drop it on the BOOTSEL drive; the MCU
then has no bootable image and comes back in BOOTSEL, ready for the flat firmware UF2.

usage: erase-partition-table.py OUT.uf2
"""
import struct
import sys

UF2_MAGIC0, UF2_MAGIC1, UF2_MAGIC_END = 0x0A324655, 0x9E5D5157, 0x0AB16F30
FLAG_FAMILY = 0x00002000
FAMILY_ABSOLUTE = 0xE48BFF57
SECTORS = (0x10000000, 0x10001000)

blocks = []
for n, addr in enumerate(SECTORS):
    hdr = struct.pack("<8I", UF2_MAGIC0, UF2_MAGIC1, FLAG_FAMILY, addr, 256, n, len(SECTORS),
                      FAMILY_ABSOLUTE)
    data = b"\xff" * 256 + b"\x00" * (476 - 256)
    blocks.append(hdr + data + struct.pack("<I", UF2_MAGIC_END))
with open(sys.argv[1], "wb") as f:
    f.write(b"".join(blocks))
