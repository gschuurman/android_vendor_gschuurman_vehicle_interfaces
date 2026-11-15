# K-line module rev 0.1 (MG F, MEMS 1.9) - 2026-11-15

A small 2-layer board that stacks on main board rev 0.6 socket **J10**, like the other modules, and connects the
RP2350B UART to the car's K-line through Glenn's ST **L9637D**.

- Size **28.5 x 20.5 mm**, 1.6 mm, 2 layers, GND pour on both sides. Well inside the JLCPCB 100 x 100 mm promo.
- Status: fully routed, **0 unconnected, 0 copper/clearance errors**. `drc.rpt` only lists the KiCad standard library
  names (not installed in the build container) and one silkscreen nick at a corner.
- All parts are 0805 or larger (SOT-23, SOD-123, SMA, SO-8, 2512), all on the top side. Only the 2x4 header sits underneath.
- Files: `kline_module.kicad_pro/.kicad_pcb/.kicad_sch` (made in KiCad 7, open in KiCad 10), `kline_module_gerbers.zip`
  (upload to JLCPCB), `kline_module_bom.csv`, `kline_module_lcsc_order.csv` (LCSC numbers and quantity per board),
  `kline_module_schematic.pdf`, renders in `render/`, generator scripts in `scripts/` (placement and netlist in `design.py`).

## Fit on the main board (rev 0.6)

The board is drawn in main-board coordinates, so it can be checked directly against `carradio_peripheral_rev06.kicad_pcb`.

| What | Main board | Module |
|---|---|---|
| J10 (2x4 socket, 8.5 mm) | pin 1 at (78.19, 27.63) | J1 2x4 male header on the underside, pin 1 at (78.19, 27.63); all 8 pins checked in the script |
| H8 (M2) | (69.6, 18.5) | H1 2.2 mm hole at (69.6, 18.5), copper keep-out 5.2 mm |
| outline | free zone above J10 | x 65.0-93.5, y 11.5-32.0 (audio module ends at x 63.5, USB module starts at y 32.5) |

Under the module there are only low SMD parts, the J10 socket, F6 and the HDMI pairs. The module edge reaches
0.5 mm over the back of the HDMI socket J13 (courtyard to y 12.0), which is about 6 mm tall, so there is ~5 mm of air
at the 11 mm stack height. It stays clear of the FPC J14 (starts at x 94.2); unplug the module to open the J14 latch.
Screw: M2 x 18 through the module, the printed 11 mm M2 sleeve (`module_spacers`) and the main board into the H8 insert.

J1 is two 1x4 male headers (Ckmtw B-2100S04P-A110, same family as earlier boards), one per row. Plug them into J10
first, put the module on top and solder them from above, so they line up.

## Circuit

| J1 pin | Main board net | Use |
|---|---|---|
| 1 | +3V3_MCU | U1 VCC |
| 2, 6 | GND | |
| 3 | EXP_GP32 (UART0 TX) | U1 TX |
| 4 | EXP_GP33 (UART0 RX) | U1 RX |
| 5 | EXP_GP28 | K-line power enable (high = on) |
| 7 | VBAT_KLINE (via F6, after D1 reverse diode and SMBJ22A) | Q1 source |
| 8 | +5V_AON | not used |

- **U1 L9637D**: VCC from 3.3 V is inside the datasheet range (3-7 V). RX then swings 0-3.3 V straight into GPIO33,
  and TX accepts 3.3 V logic (VIH max 2.5 V). TX, RX and LO have internal pull-ups to VCC, so nothing else is needed.
  VS max 36 V; the main-board TVS clamps at 35.5 V.
- **Q1 FDN5618P** (same as main-board Q2) with D1 12 V zener, R2 100k and Q2 2N7002 + R3: switches battery to VS and to the
  pull-up. GPIO28 low (also the default through R4 10k) = off. That gives zero parked drain and, more importantly,
  no 12 V pushed through 510 ohm into the ECU's K-line while the ECU is unpowered.
- **R1 510 ohm 2512** (1 W, 0.4 W worst case with K stuck low): the ISO 9141 tester pull-up. **JP1** is a bridged solder jumper;
  cut it if you want to run without the module's pull-up.
- **D2 SMAJ26CA** bidirectional TVS and **C4 1 nF** on K (ISO 9141 allows up to 1.3 nF; 470 pF also fine).
- **D3** green LED: lit while the K-line side is powered.
- L-line is not used by the MEMS 1.9: LI and LO stay open (the datasheet defines LO for an open LI).

## Car side

**J2 = JST S2B-XH-A side entry** (2.5 mm XH, crimp housing XHP-2), pin 1 **K-line**, pin 2 **GND**. The opening faces
the back plate (main-board x = 100). Glenn's harness already uses XH for the VIM3 power, so the same crimps work.
- Forum sources (not a wiring diagram) say the MEMS 1.9 K-line is OBD-II socket pin 7 (ECU red connector pin 31 on at
  least one car), GND pins 4/5. Check this on your car before wiring.
- Space: the plug and wire leave the module edge at x 93.3; the back plate inner face is at about x 101. That is
  tight for a bend; a small hole/grommet in the back plate lets the wire run straight out.

## Firmware notes (not written yet)

- GPIO28 high, wait ~10 ms, then talk.
- MEMS 1.9 (per rovermems.com): ISO 9141 5-baud init with ECU address 0x16, bit-banged on GPIO32 as SIO, then UART0
  **9600 8N1** half duplex (you read back your own echo on GPIO33).
- GPIO28 low when ACC goes off.

## Order

JLCPCB: upload `kline_module_gerbers.zip`, defaults (2 layers, 1.6 mm, HASL, 5 pcs), no assembly.

Parts (checked against the rev 0.6 order of 2026-10-04, `pcb/ordering/lcsc_final_cart.csv` + `mouser_final_import.csv`,
assuming one set built with at most 2 spares used):

| Ref | Part | Source |
|---|---|---|
| U1 | L9637D | Glenn's own |
| J2 | JST XH 2-pin right angle | Glenn's own; cable needs an XHP-2 housing + 2 SXH crimps |
| Q1 | FDN5618P | rev 0.6 leftover (5 ordered, 1 used) |
| D1 | BZT52C12 | leftover (10 ordered, 2 used) |
| Q2 | 2N7002 | leftover (50 ordered) |
| D3 | KT-0805G LED | leftover (50 ordered) |
| R5 | 4.7k 0805 | leftover (100 ordered) |
| C1, C2 | 100 nF | leftover 0603 C14663 (150 ordered, ~48 used); fits the 0805 pads |
| R3, R4 | 10k | leftover 0603 C98220 (40 ordered, ~18 used) |
| R2 | 100k | leftover 0603 C25803 (100 ordered) |
| C4 | 1 nF | leftover 0603 C1588 (6 ordered, 1 used) |
| J1 | 2x 1x4 header | leftover C124378 (10 ordered, 1 used) |
| **R1** | **510R 2512 1W** | **buy: LCSC C269361** |
| **D2** | **SMAJ26CA** | **buy: LCSC C571371** |

`kline_module_lcsc_order.csv` holds only the two parts to buy; `kline_module_bom.csv` is the full BOM.
