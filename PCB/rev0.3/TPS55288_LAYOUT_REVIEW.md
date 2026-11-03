# TPS55288 layout review (rev 0.3, commit 890e9fd)

Checked against TI's application note **SLVAER0C, "TPS55288 Layout Guideline"**
(https://www.ti.com/lit/an/slvaer0c/slvaer0c.pdf). TI's datasheet PDF (SLVSF01) could not be downloaded
from this session, so the rules come from the app note. Measurements were taken from the board file.

## Passes

| TI rule | Our layout |
|---|---|
| Loop 1 (input caps, buck FETs) small | C50/C49 sit 2-3 mm from Q11's drain tab; their GND pads share one F.Cu pour with Q12's source pins. Tight. |
| Loop 2 (output caps at VOUT/PGND pins) small | C58 is about 1.6 mm below VOUT pins 11/12; all four 22 µF caps share one GND pour with the PGND pins. Good. |
| Whole GND plane under the switching loops | In1 is a solid GND plane under the whole stage. |
| ILIM part close to the IC | R69 is 3.3 mm from pin 17, on F.Cu with no vias (after today's swap). |

## Problems, most important first

1. **VCC capacitor too far away.** TI: "very close to the VCC and PGND pins". C53 (4.7 µF) is about 6 mm of
   track from pin 19. VCC feeds the gate drivers, so this should be under 1-2 mm.
2. **FSW and compensation parts are scattered.** TI: FSW, ILIM, COMP and feedback parts close to the IC.
   - FSW (R68): 12 mm away, 31 mm of track, 4 vias.
   - COMP (R71, C55): 16 mm of track, 2 vias.
   - COMP_RC (C54): 24 mm of track, 2 vias.

   These are the most noise-sensitive pins.
3. **Bootstrap caps go through two vias each.** C51 (BOOT1) and C52 (BOOT2) are near their pins, but each
   route dives to B.Cu and back (about 4.6 mm, 2 vias each). TI wants the boot loop very short.
4. **DR1H gate drive is long and has no paired return.** It runs 11.8 mm on B.Cu from pin 2 to Q11's gate.
   TI wants it short, on layers 1 and 3, routed side by side with its SW1 return like a differential pair.
   DR1L (4.5 mm) is acceptable.
5. **Current sense is not Kelvin-connected.** TI routes ISP/ISN as a tight differential pair from the shunt
   (R74). ISP (pin 12) is on the BB_VOUT net, so it joins the VOUT pour at the IC instead of at R74's pad,
   and ISN lands on a +5V_SYS via near R74 rather than on its pad. Copper drop then shifts the current
   limit and cable-droop compensation by a few percent. A clean fix needs a schematic change: give ISP and
   ISN their own nets with net-tie footprints at R74's pads.
6. **No separate AGND.** TI pours AGND separately (FSW/ILIM/COMP/CDC/MODE grounds) and joins it to PGND at
   one point near the VCC cap. On our board every GND is one net going straight to the planes. With a
   solid In1 plane this usually works, but it is not what TI recommends. Doing it properly also needs a
   net tie in the schematic.
7. **SW1 copper is larger than needed.** TI: keep SW node area small. The SW1 pour is about 64 mm²
   (L3's left pad down to Q11/Q12). SW2 is about 24 mm². Part of this is forced by L3's 12 mm footprint;
   SW1 could be cut to a strip about 4 mm wide.

## Fix plan

- Items 1-4 and 7 are layout-only: move C53, R68, R71, C54, C55 (and R67/R70) into a tight cluster on the
  right and bottom of U12, re-route BOOT1/BOOT2 on F.Cu, shorten DR1H with Q11 closer or a paired route,
  and shrink the SW1 pour.
- Items 5-6 need a schematic change (net ties) before layout.

## Rework done (2026-10-01, Glenn chose "layout + net ties")

| Item | Before | After |
|---|---|---|
| 1. VCC cap C53 | ~6 mm of track | Pad touches pin 19 (0.9 mm link), its GND has its own via to the plane |
| 2. FSW, COMP, ILIM, CDC, MODE parts | 12-31 mm, up to 4 vias | Row of parts beside U12, all on F.Cu, no vias. FSW 1.3 mm, COMP 4.6 mm, COMP_RC 1.4 mm, ILIM 6.5 mm |
| 3. Bootstrap caps | 2 vias each | C52 sits over pin 20 (0.3 mm), C51 4.2 mm, both on F.Cu with no vias |
| 5. Current sense | ISP on the VOUT pour, ISN on a +5V_SYS via | ISP/ISN have their own nets, run as a pair on In2, and land on R74's inner pad edges through net ties NT1/NT2; the VOUT pour no longer wraps R74's inner edge |
| 6. AGND | None | AGND pour under the control parts (net BB_AGND) with U12 pins 7 and 10, joined to GND only through net tie NT3 at C53's ground pad |
| 4. DR1H gate drive | 11.8 mm on B.Cu | **Unchanged.** Q11's gate pin faces away from U12; fixing it means re-placing the input FET and loop 1, which passes TI's rules today |
| 7. SW1 copper | 64 mm² | **Unchanged.** Mostly forced by L3's pad; trimming it would save maybe 15 mm² |

Schematic: three NetTie_2 symbols (NT1-NT3) added in `gen3.py`; U12 pin 12 is now BB_ISP, pin 13 BB_ISN,
pins 7 and 10 BB_AGND, and the ground ends of R67-R70, C54 and C55 are on BB_AGND. ERC result unchanged.
The BOM is unchanged (net ties are not parts).

Other parts moved to make room: C58, C59, C56, C57 down 0.4 mm, C52 above pin 20, R68 below-left of U12,
C103 beside TH1. Nets re-routed around the change: RPP_G, LUX_SCL, LUX_SDA, DAC_XSMT, I2S_DOUT0,
VIM3_PWR_EN, MCU_TEMP_ADC, ACC_F and a few short pieces elsewhere.

DRC after the rework: 0 unconnected, no copper or courtyard errors; only silkscreen warnings and the
library-path notice for U12, F4 and J14.

## Follow-up: gate resistors and SW1 snubber (2026-10-01)

Items 4 and 7 were not fixed by moving copper, so the board now has the usual fallbacks for both:

| Part | Where | Fitted value | Purpose |
|---|---|---|---|
| R97 (0402) | Between L3 and Q11, in DR1H at Q11's gate | 0 Ω (C17168) | Gate resistor. 2.2-4.7 Ω slows the high-side switching edge and damps the long DR1H loop |
| R98 (0402) | Below Q12, in DR1L at Q12's gate | 0 Ω (C17168) | Same for the low-side FET |
| C104 (0603) + R99 (0805) | Above Q11/Q12, SW1 to GND | 1 nF X7R (C1588) + 2.2 Ω 125 mW (C17521) | RC snubber that damps ringing on SW1. About 0.08 W in R99 at 14 V in and 422 kHz |

The gate resistors ship as 0 Ω on purpose. The TPS55288 sets its dead time by watching the gate drive, and
a series resistor makes the FET turn off later than the chip thinks it does. Fit 2.2 Ω only if SW1 rings or
EMI is a problem on the bench, and check with a scope that the two FETs are never on together.
The snubber is fitted. If it runs warm or efficiency matters more than ringing, leave C104 off.

DRC after the change: 0 unconnected, no copper or courtyard errors.
