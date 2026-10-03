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
| `*_cpl.csv` + `*_jlc_bom.csv` | pick-and-place and BOM in JLC's format: for JLC's SMT DFM check (or a PCBA order). Pin headers, pin sockets and the 40-pin IDC header are left out (they are in the LCSC cart; solder them yourself) |

`lcsc_paste.txt` is the LCSC list for one complete set (all four boards), for the BOM Tool's Copy & Paste box; `lcsc_cart_one_set.csv`
is the readable version of the same list.

## 1. Impedances (done)

Checked with JLCPCB's impedance calculator (4 layers, 1.6 mm, 1 oz / 0.5 oz, JLC04161H-7628, L1 over L2) and applied:

| Pairs | Target | Calculator | On the board |
|---|---|---|---|
| USB_UP (VIM3 to hub 1) | 90 Ω differential | 0.334 mm / 0.300 mm gap | 0.32 mm / 0.30 mm (0.32 fits between U13 and J23; about 1 Ω higher) |
| HDMI D0-D2, CLK | 100 Ω differential | 0.2187 mm / 0.1999 mm gap | 0.2187 mm / 0.20 mm (re-routed as coupled pairs) |

Order the main board **with impedance control on and stack-up JLC04161H-7628**, otherwise these numbers do not hold.

The GNSS module's RF line (1.0 mm trace, 0.30 mm gaps to top ground, solid bottom ground, about 5.7 mm long) was not
re-checked; it is short enough that a few ohms either way do not matter.

## JLC DFM check: what may still show up

JLC's DFM tool reads only the Gerbers, without net information, so it flags copper of the **same net** that comes close
without touching, which cannot cause a defect. After the clean-up (dangling vias and stubs removed, vias moved off
pins, pad gaps opened to 0.15 mm, overlapping vias merged, silkscreen clipped at pads), expect:

| DFM item | Expected | Why it is fine |
|---|---|---|
| Trace spacing (red/orange) | a few, 0.001-0.08 mm | same-net jogs left by the router (two parallel pieces of one track offset by a fraction of a mm); KiCad DRC confirms no clearance problem between different nets |
| Pad spacing (orange) | 0.13-0.15 mm | different-net vias/pads at the 0.13 mm design clearance, inside JLC's 0.09 mm limit |
| THT to SMD (red) | ~300 | an assembly rule (2 mm); it measures the ring of small vias around the M2.5/M3 mounting holes. Irrelevant for hand soldering |
| Via to pad | a few | thermal vias inside exposed pads (RP2350B, TPS55288, MOSFETs) are intentional; 9 vias stay at dense U12/U13 pins |
| Annular ring (red) | ~190 vias | 0.3 mm hole in a 0.45 mm pad (0.075 mm ring): exactly JLC's standard 0.3mm/(0.4/0.45mm) option, and JLC's own note says via results can be ignored. Where there was room the pads were grown to 0.5-0.6 mm (355 vias); the rest sit in dense areas, mostly around the RP2350B |
| Plated through-hole to trace (orange) | many, ~0.2 mm | a via hole next to a trace at the normal 0.13 mm copper clearance; inherent to the 0.3/0.45 mm via option. Same-net traces passing close to their own vias were joined to them |
| Unconnected trace end (orange) | ~6 | overlapping same-net copper that KiCad counts as dangling; electrically connected |
| Solder mask / silkscreen items | warnings | silkscreen is clipped at pad openings; leftover text over tented vias is cosmetic |

## 2. Order the PCBs (JLCPCB)

Upload each `*_gerbers.zip` as its own item. Leave **PCB Assembly off**.

Main board:
- FR-4, **4 layers, 1.6 mm**, **impedance control: yes, stack-up JLC04161H-7628**, outer 1 oz, inner 0.5 oz
- Min via hole size/diameter: the standard **0.3mm/(0.4/0.45mm)** (vias are 0.3 mm holes in 0.45 mm pads; no surcharge)
- Specify Stackup: **Yes**, JLC04161H-7628 · Via covering: Plugged (default) · Mark: Remove Mark
- Surface finish **HASL (with lead)** (Glenn's choice, 2026-10-03; see the HASL notes below)

Modules: 2 layers, 1.6 mm, 1 oz, standard options, surface finish **HASL (with lead)**.

HASL notes: leaded HASL wets well and melts low, which suits hand and hot-air work, but its pads are domed rather than
flat. Where that matters:
- RP2350B (QFN-80, 0.4 mm): stencil paste, then check every side for bridges under a loupe; flux and wick clear them.
- TPS55288 (VQFN), Q11/Q12 (VSON), LMR33630 (PowerPAD), TPS2561 (VSON): paste through the stencil; if a part sits
  tilted on the domed pads, press it down lightly while the solder is molten.
- NEO-M9N (LGA, GNSS module): the trickiest on HASL. Thin, even paste layer, hotplate, no extra solder; check that it
  sits flat.
- J14 (0.5 mm FPC): drag-solder with plenty of flux.

**Stencils:** on each PCB's order page, add an **SMD stencil, top side** (frameless is fine for hand work). Paste is
practically required for: RP2350B (QFN-80 0.4 mm), TPS55288 (VQFN-HR), Q11/Q12 (VSON),
NEO-M9N (LGA), TPS2561 (VSON-10), LMR33630 (PowerPAD). Use a hotplate or hot air for those; the 0603/0805 parts and
SOT-23s can go on in the same reflow or by iron.

## 3. Order the parts (LCSC)

1. lcsc.com > **BOM Tool** > **Copy & Paste** tab: paste the whole of **`lcsc_paste.txt`** (one `LCSC number, quantity`
   per line) and press Continue. Checked on 2026-10-03: 95 of 95 lines matched, about $91 for one set (before shipping). The biggest items are the
   NEO-M9N GNSS module (~$16.50), the F4 fuse holder (~$4) and the TPS55288 (~$2.20); about $34 is minimum order
   quantities of cheap passives (you get 50 of a resistor you need 2 of: spares for a second set).
   File upload works less well: LCSC tries to match by value/description text. If you want a file anyway, use
   `lcsc_cart_one_set_upload.xlsx` and map only **Quantity** and **LCSC Part Number**.
   `lcsc_cart_one_set.csv` is the same list with values, descriptions and where each part goes.
   Quantities are for one set plus 3 spares of each 0402/0603/0805 resistor and capacitor; LCSC rounds up to its
   minimum order quantities. It also includes the 7.5 A blade fuse for holder F4 (C178942) and the jumper cap for JP1
   (C5305), which the BOM only names in notes.
2. For more sets, multiply the **Needed** column of `lcsc_cart_one_set.csv` and paste again.
3. Substitutions already in the list (out of stock or not sold outside China on 2026-10-03):
   - **U20 is the RP2354B** (C39843328): the RP2350B with 2 MB flash inside the package. LCSC does not sell the RP2350B
     (C42415655) outside China. With the RP2354B, **U21 (W25Q128 flash) stays empty**; build the firmware for 2 MB flash (PICO_BOARD with PICO_FLASH_SIZE_BYTES 2 MB), plenty for an I/O controller.
     If you get an RP2350B elsewhere, fit U21 (W25Q128JVSIQ, C113767) as well.
   - L1 C96895 -> C167882, 10 kΩ C25804 -> C98220, 2.2 nF C28260 -> C77060, J23/J25 C30867 -> C5821035,
     optocoupler EL817S1 C470884 -> LTV-817S-TA1-C C109227 (same pinout and package).
   - USB module L4: Bourns SRP6060FA-8R2M (C2045598, $1.38) instead of the Coilcraft XAL6060-822MEC ($12.34). Same
     8.2 uH, 8.5 A saturation, 22.5 mOhm, and the same land pattern (pads 4.05 vs 4.04 mm apart). All same value, package and rating.
4. Extra hardware: M2.5 x 11 mm standoffs (3, for the GNSS, audio and USB modules), M3 screws/standoffs for the four
   main board corners, and an M2 x 11 mm standoff for a future K-line module (H8).

## 4. Assembly order (suggested)

1. Main board, paste + reflow: U20 (U21 stays empty with the RP2354B), TPS55288 stage (U12, Q11, Q12, L3), then the rest of the SMD parts.
   Check U20 and U12 for bridges under a loupe before going on.
2. Hand-solder the through-hole parts: module sockets J10/J23/J25/J27, J2 (VIM3 box header), loom connectors, F4 fuse
   holder, the large electrolytics.
3. Modules: SMD first (paste + reflow), then their headers J24/J26/J28 on the **bottom side**, pins pointing down.
4. JP2 (GNSS RX source) is copper, bridged 1-2 from the factory.
5. Before the first power-up: measure for shorts on VSYS_IN, +5V_SYS, +5V_AON, +3V3_MCU and +1V1_MCU to GND.
6. Flash the RP2354B over USB (same firmware and procedure as the RP2350B) (hold SW1, tap SW2) or SWD on J22; see `../../rev0.4/README.md`, "Flashing the RP2350B".

## Status

- Main board: DRC 0 unconnected, no errors.
- USB module rev 0.6: DRC 0 unconnected, no errors (GND pads of U15, U16 and C69 now connect solid to the pours).
- GNSS module: clean. Audio module: one starved-thermal warning on header J24 pin 3 (a through-hole GND pin with fewer
  thermal spokes, fine for hand soldering).
