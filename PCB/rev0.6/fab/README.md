# JLCPCB order files (rev 0.6 set)

One folder per board, made by `../layout/jlcfab.py` from the KiCad files:

| Folder | Board | Source |
|---|---|---|
| `main/` | main board rev 0.6, 100 x 100 mm, 4 layers | `../main/carradio_peripheral_rev06.kicad_pcb` |
| `gnss/` | GNSS module, 26.5 x 31.5 mm, 2 layers | `../../rev0.4/gnss/` |
| `audio/` | audio module, 36.5 x 41 mm, 2 layers | `../../rev0.4/audio/` |
| `usb/` | USB module, 36 x 55 mm, 2 layers | `../../rev0.4/usb/` |

Each folder holds:
- `*_gerbers.zip`: upload as the PCB. It contains the Gerbers (Protel extensions, no X2/netlist attributes) and Excellon
  drill files (mm, PTH and NPTH separate).
- `*_bom.csv`: assembly BOM (Comment, Designator, Footprint, JLCPCB Part #), fitted parts only.
- `*_cpl.csv`: pick-and-place (Designator, Mid X, Mid Y, Layer, Rotation).

## PCB options

Main board:
- Layers 4, 1.6 mm, **impedance control: yes, stack-up JLC04161H-7628** (the USB_UP pair at 0.30/0.15 mm and the HDMI
  pairs assume it). Outer copper 1 oz, inner 0.5 oz.
- Vias are 0.45 mm pad / 0.2 mm hole. Pick the via option that allows a 0.2 mm hole (multilayer boards support it).
  Minimum track 0.15 mm, minimum clearance 0.1 mm.
- Surface finish: ENIG recommended (0.4 mm QFN RP2350B, 0.5 mm FPC J14, TPS55288 VQFN). Leaded HASL works but is less flat.
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
  - GNSS R102/R103 had no LCSC number in the rev 0.4 BOM; the order BOM uses C25190 (27 Ω 0603, the part used for R83/R84
    on the main board).
- The RP2350B (C42415655) had unclear LCSC stock; the BOM note on U20 names the RP2354B (C39843328, internal flash, then
  leave U21 unfitted) as the alternative.
- JP2 is a solder jumper (PCB copper), not a part; it ships bridged 1-2.

## Before you order

- Main board DRC: 0 unconnected, no errors. Module boards: 0 unconnected, but KiCad 10 flags "starved thermal" on a few
  GND pads (audio J24 pin 3; USB U15 pin 9, U16 pins 1/11, C69 pin 2). U16 is the module's 5 V / 3 A buck; solid zone
  connections on its GND pins are advisable (see `../README.md`).
- USB_UP pair: confirm 0.30 mm / 0.15 mm gives about 90 Ω in JLC's calculator for JLC04161H-7628.
