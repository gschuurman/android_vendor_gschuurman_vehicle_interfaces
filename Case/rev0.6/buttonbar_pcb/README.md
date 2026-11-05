# Button bar PCB (case rev 0.6)

Small 2-layer board (176.7 x 11.5 mm) that sits behind the 9 caps of the case's button bar.
Everything goes over the existing **J12** connector on the rev 0.6 main board (5 wires, no main-board change).

Files: `buttonbar.kicad_pro/.kicad_sch/.kicad_pcb` (open in KiCad 7 or newer), project footprint
library `buttonbar.pretty` (all footprints included, no global libraries needed), `buttonbar_schematic.pdf`,
`gerbers/` + `buttonbar_gerbers.zip` (JLCPCB-ready, 2 layers, 1.6 mm), `render/`, `scripts/` (generators).

Status: schematic netlist matches the PCB 1:1 (10 nets), KiCad DRC 0 errors, 0 warnings, 0 unconnected.

## How it works (diode coding)

Every J12 line has a 1k series resistor, a 10k pull-up and 100 nF on the main board.
Single buttons short one line to GND. Combo buttons pull two lines low through two BAT85 Schottky diodes.

| Button | J12 lines low |
|---|---|
| Screen off | 1 (S, GPIO18) |
| Vol + | 2 (U, GPIO17) |
| Vol - | 3 (D, GPIO22) |
| Mute | 4 (M, GPIO16) |
| Play/Pause | 2 + 3 |
| Prev | 3 + 4 |
| Next | 2 + 4 |
| Home | 1 + 3 |
| Voice | 1 + 2 |
| (spare code) | 1 + 4 |

Firmware: wait ~30 ms after the first line goes low, then read all four lines and decode the pattern.
The current firmware treats the lines as four separate buttons, so it needs this decode step.

## Build notes

- **BAT85 (or BAT43) only.** A 1N4148 leaves the line at about 0.8 V, right at the RP2350 VIL limit.
  The cathode band goes on the pad marked K (the square pad).
- **Switch pitch is assumed** at 5.08 mm, 2 pins, body 6 x 3.5 mm, 5 mm high (KW-1556 / Adafruit 1489 type; no
  drawing could be downloaded). Measure yours before ordering. If they differ, change the footprint in
  `buttonbar.pretty` and `btn_total_h` / `btn_body` in the case.
- **J1 = J12 pin for pin** (1 S, 2 U, 3 D, 4 M, 5 GND). There is only 3 mm behind the board in the bar,
  so a pin header does not fit: solder the 5 wires straight into the J1 pads from the back and run them
  out through the wire slot in the bar's back wall (case updated: slot now x -17..-5, support rib moved to x -24
  so it clears J1).
- Switches, diodes and labels are on the front (F) side; solder from the back.
- It needs both copper layers. A single-sided version could not be routed without wire links, so on perfboard
  treat the red (F.Cu) tracks as wire links.
