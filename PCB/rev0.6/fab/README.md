# JLCPCB assembly-order files (rev 0.6 set)

For hand assembly use `../order/` instead; this folder adds the JLC PCBA BOM/CPL files.

One folder per board, made by `../layout/jlcfab.py` from the KiCad files:

| Folder | Board | Source |
|---|---|---|
| `main/` | main board rev 0.6, 100 x 100 mm, 4 layers | `../main/carradio_peripheral_rev06.kicad_pcb` |
| `gnss/` | GNSS module, 26.5 x 31.5 mm, 2 layers | `../../rev0.4/gnss/` |
| `audio/` | audio module, 36.5 x 41 mm, 2 layers | `../../rev0.4/audio/` |
| `usb/` | USB module rev 0.6, 36 x 55 mm, 2 layers | `../usb/` |

Each folder holds:
- `*_gerbers.zip`: upload as the PCB. It contains the Gerbers (Protel extensions, no X2/netlist attributes) and Excellon
  drill files (mm, PTH and NPTH separate).
- `*_bom.csv`: assembly BOM (Comment, Designator, Footprint, JLCPCB Part #), fitted parts only.
- `*_cpl.csv`: pick-and-place (Designator, Mid X, Mid Y, Layer, Rotation).

## PCB options

Main board:
- Layers 4, 1.6 mm, **impedance control: yes, stack-up JLC04161H-7628** (the USB_UP pair at 0.32/0.30 mm and the HDMI
  pairs at 0.2187/0.20 mm assume it). Outer copper 1 oz, inner 0.5 oz.
- Vias are 0.3 mm holes in 0.45 mm pads: JLC's standard 0.3mm/(0.4/0.45mm) option.
  Minimum track 0.15 mm, minimum clearance 0.1 mm.
- Surface finish: HASL with lead (chosen; ENIG would be flatter for the 0.4 mm QFN, VQFN and 0.5 mm FPC).
- Via covering: tented.

Modules: 2 layers, 1.6 mm, 1 oz, standard options. On the GNSS module, check the 1.0 mm RF trace width against JLC's
impedance calculator for 50 Ω on the 2-layer 1.6 mm stack before ordering (see the rev 0.4 README).

## Assembly (PCBA)

- Assemble the top side. All SMD parts are on top; the module headers (J24, J26, J28) are through-hole on the
  underside and are hand-soldered.
- After uploading BOM + CPL, **check every part's rotation and position in JLC's preview**. KiCad and JLC disagree on
  the zero orientation of some footprints (SOT-23, QFN, connectors are the usual ones), so fix any that look turned.
- Parts without a JLCPCB number are left for hand soldering or your own sourcing:
  - main: J10 (2x4 female socket, 8.5 mm) and J27 (2x8 female socket, 8.5 mm). J23/J25 use BOOMELE C30867, which was
    out of stock on 2026-10-01; any 2x10 2.54 mm 8.5 mm socket fits.
  - gnss: J28 (2x8 male header, bottom side).
  - GNSS R102/R103 had no LCSC number in the rev 0.4 BOM; the order BOM uses C2907021 (FOJAN 27 Ω 1% 0603, the part used for R83/R84; UNI-ROYAL C25190 was backordered on 2026-10-04
    on the main board).
- U20 is the RP2354B (C39843328, 2 MB flash in the package): LCSC does not sell the RP2350B (C42415655) outside China.
  U21 (external flash) is marked not fitted and left out of the JLC BOM/CPL; fit it only with an RP2350B.
- JP2 is a solder jumper (PCB copper), not a part; it ships bridged 1-2.

## Before you order

- All boards DRC 0 unconnected; the USB module's buck/switch GND pads are solid since rev 0.6.
- Impedance-controlled pairs follow JLC's calculator for JLC04161H-7628: USB_UP 0.32/0.30 mm (90 Ω), HDMI 0.2187/0.20 mm (100 Ω).
