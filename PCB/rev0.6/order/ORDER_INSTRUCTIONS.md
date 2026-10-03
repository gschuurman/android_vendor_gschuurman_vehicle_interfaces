# Car radio rev 0.6: order and hand assembly

You assemble the boards yourself, so the order is: **bare PCBs + stencils from JLCPCB, parts from LCSC.**

| Folder | Board | Size | Layers |
|---|---|---|---|
| `main/` | main board rev 0.6 | 100 x 100 mm | 4 |
| `gnss/` | GNSS module rev 0.4 | 26.5 x 31.5 mm | 2 |
| `audio/` | audio module rev 0.4 | 36.5 x 41 mm | 2 |
| `usb/` | USB module rev 0.6 (rev 0.4 with solid GND on the buck U15, switch U16 and C69) | 36 x 55 mm | 2 |

Each board folder has:

| File | Use |
|---|---|
| `*_gerbers.zip` | upload to JLCPCB (PCB and stencil) |
| `*_parts.csv` | full parts list: designator, value, part/MPN, LCSC number, footprint, notes |
| `*_assembly_top.pdf` / `*_assembly_bottom.pdf` | placement drawings (fab outlines with designators, silkscreen, board edge) |
| `*_schematic.pdf` | schematic |

`lcsc_cart_one_set.csv` lists every part for one complete set (all four boards) by LCSC number.

## 1. Impedances (done)

Checked with JLCPCB's impedance calculator (4 layers, 1.6 mm, 1 oz / 0.5 oz, JLC04161H-7628, L1 over L2) and applied:

| Pairs | Target | Calculator | On the board |
|---|---|---|---|
| USB_UP (VIM3 to hub 1) | 90 Ω differential | 0.334 mm / 0.300 mm gap | 0.32 mm / 0.30 mm (0.32 fits between U13 and J23; about 1 Ω higher) |
| HDMI D0-D2, CLK | 100 Ω differential | 0.2187 mm / 0.1999 mm gap | 0.2187 mm / 0.20 mm (re-routed as coupled pairs) |

Order the main board **with impedance control on and stack-up JLC04161H-7628**, otherwise these numbers do not hold.

The GNSS module's RF line (1.0 mm trace, 0.30 mm gaps to top ground, solid bottom ground, about 5.7 mm long) was not
re-checked; it is short enough that a few ohms either way do not matter.

## 2. Order the PCBs (JLCPCB)

Upload each `*_gerbers.zip` as its own item. Leave **PCB Assembly off**.

Main board:
- FR-4, **4 layers, 1.6 mm**, **impedance control: yes, stack-up JLC04161H-7628**, outer 1 oz, inner 0.5 oz
- Min via hole/diameter: an option that allows **0.2 mm holes / 0.45 mm pads**
- Surface finish **ENIG** (flat pads for the 0.4 mm QFN, VQFN and 0.5 mm FPC connector)
- Via covering: tented

Modules: 2 layers, 1.6 mm, 1 oz, standard options. ENIG on the GNSS (LGA receiver) and USB (VSON, PowerPAD) modules
makes paste soldering easier; HASL works on the audio module.

**Stencils:** on each PCB's order page, add an **SMD stencil, top side** (frameless is fine for hand work). Paste is
practically required for: RP2350B (QFN-80 0.4 mm), TPS55288 (VQFN-HR), Q11/Q12 (VSON),
NEO-M9N (LGA), TPS2561 (VSON-10), LMR33630 (PowerPAD). Use a hotplate or hot air for those; the 0603/0805 parts and
SOT-23s can go on in the same reflow or by iron.

## 3. Order the parts (LCSC)

1. lcsc.com > BOM Tool > upload `lcsc_cart_one_set.csv`; map **LCSC Part Number** and **Quantity**.
   Quantities are for one set plus 3 spares of each 0402/0603/0805 resistor and capacitor; LCSC rounds up to its
   minimum order quantities.
2. For more sets, multiply the **Needed** column and re-upload.
3. Replace anything out of stock with the same value, package and rating. Known cases:
   - RP2350B (C42415655): if unavailable, RP2354B (C39843328, internal flash; then leave U21 off).
   - J23/J25 BOOMELE C30867 (2x10 female, 8.5 mm): out of stock on 2026-10-01; any 2x10 2.54 mm 8.5 mm socket fits.
4. Not on LCSC (lines with quantity 0): **J10** 2x4 female socket 8.5 mm, **J27** 2x8 female socket 8.5 mm,
   **J28** 2x8 male header. Any 2.54 mm socket/header with an 8.5 mm body works.
5. Extra hardware: M2.5 x 11 mm standoffs (3, for the GNSS, audio and USB modules), M3 screws/standoffs for the four
   main board corners, and an M2 x 11 mm standoff for a future K-line module (H8).

## 4. Assembly order (suggested)

1. Main board, paste + reflow: U20, U21, TPS55288 stage (U12, Q11, Q12, L3), then the rest of the SMD parts.
   Check U20 and U12 for bridges under a loupe before going on.
2. Hand-solder the through-hole parts: module sockets J10/J23/J25/J27, J2 (VIM3 box header), loom connectors, F4 fuse
   holder, the large electrolytics.
3. Modules: SMD first (paste + reflow), then their headers J24/J26/J28 on the **bottom side**, pins pointing down.
4. JP2 (GNSS RX source) is copper, bridged 1-2 from the factory.
5. Before the first power-up: measure for shorts on VSYS_IN, +5V_SYS, +5V_AON, +3V3_MCU and +1V1_MCU to GND.
6. Flash the RP2350B over USB (hold SW1, tap SW2) or SWD on J22; see `../../rev0.4/README.md`, "Flashing the RP2350B".

## Status

- Main board: DRC 0 unconnected, no errors.
- USB module rev 0.6: DRC 0 unconnected, no errors (GND pads of U15, U16 and C69 now connect solid to the pours).
- GNSS module: clean. Audio module: one starved-thermal warning on header J24 pin 3 (a through-hole GND pin with fewer
  thermal spokes, fine for hand soldering).
