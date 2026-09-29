# Peripheral board (mainboard)

This is the board that connects the VIM3 and the Raspberry Pi Pico 2 (vehicle MCU, firmware in `../mcu`)
to the car through the ISO 10487 harness. It also carries the audio DACs, GNSS, the display adapter, the
USB hub and the 5V supply.

- `rev0.3/` is the current design: rev 0.2 with the RP2350B chip on the board instead of the Pico 2 module.
  Read `DESIGN_rev03.md` for the changes, the 48-GPIO map and the RP2350-E9 check.
- `rev0.2/` is the Pico 2 version, and its documents still describe everything rev 0.3 didn't change.
  Start with `PCB_SUMMARY_rev02.md`, then read:
  - `DESIGN_rev02.md` for the pin map and design notes
  - `DESIGN_REVIEW_rev02.md` for the design check and layout rules
  - `ORDERING_rev02.md` for LCSC parts, cost and what to check before ordering
- `rev0.1/` is the first draft, kept for reference.
- `AUDIO.md` is the audio output plan.

The schematics are generated KiCad 7 files, for import into EasyEDA Pro. To regenerate one, run
`python3 gen3.py` inside `rev0.3/` (or `gen2.py` inside `rev0.2/`).

The PCB layout has not been done yet.
