# Audio module rev 0.7: 2x PCM5102A + car mic input

2026-11-02. Plugs into the rev 0.6 main board exactly like the rev 0.4 audio module (same 41 x 36.5 mm outline, same J24 position, same standoff hole). Not pushed to any repo yet.

## What changed from rev 0.4
- **DAC side unchanged.** U8-U11 and their parts keep rev 0.4's copper on the top side, so the bit that already works stays the same.
- **New mic input on the underside**: a 3-pin JST XH socket J201 (on the top side) goes to a 3.5 mm stereo panel jack. Then electret bias (2.2k from a filtered 4.9 V), ESD diode, a 2-stage TLV9062 preamp (42 dB, or 33.5 dB with JP201 bridged), and a PCM1808 24-bit ADC.
- **Uses the two spare J24 lines** (checked against the rev 0.6 main-board netlist): pin 8 = VIM3 pin 30 (TDM-B MCLK, 256 fs into the ADC), pin 11 = VIM3 pin 35 (ADC data back to the VIM3, TDM-B lane 3). These are the pins the road-ready software patches already use, so the software doesn't change.
- PCM1808 runs as a slave (MD0/MD1 low), I2S 24-bit (FMT low), with BCK/LRCK shared with the DACs. The mic signal goes to both ADC inputs, so the HAL can use either one.

## Jack wiring (J201, XH 2.50 mm)
| J201 pin | Jack contact | Signal |
|---|---|---|
| 1 | Tip | mic + bias |
| 2 | Ring | unused (JP202 open) |
| 3 | Sleeve | GND |

JST XH is the common "2.54 mm JST". Its real pitch is 2.50 mm, and standard XH plugs fit it. JP202 stays open, so a mono plug (ring shorted to sleeve) is safe. Only bridge it for a mic that wants bias on both tip and ring.

## Board check
- DRC (KiCad 10): 0 unconnected, 0 clearance or copper errors. Schematic parity: nets and footprints match. The only differences are LCSC/MPN fields, which are not copied onto the footprints.
- What's left is cosmetic: silkscreen overlaps (mostly the dense labels on the underside), tiny dangling track stubs that don't affect copper, and R207/R208 plus C208/C209 sitting with courtyards touching (0.35 mm pad gap, so solder those carefully).
- 2 layers, 0.15 mm minimum track and gap, 0.3 mm vias.

## Ordering the PCB (JLCPCB)
Upload `carradio_audio_rev07_gerbers.zip` and keep the defaults: 2 layers, 1.6 mm, HASL lead-free, any colour, 5 pcs. The size comes in at 41 x 36.5 mm. Skip assembly, since you're soldering it yourself. The BOM/CPL files are there in case you change your mind.

## Parts to buy (LCSC, one board)
| Part | LCSC | Package | Qty per board | Refs | New in rev 0.7 |
|---|---|---|---|---|---|
| LP5907MFX-3.3 | C5370990 | SOT-23-5 | 2 | U8, U9 |  |
| 1uF | C77386 | C 0603 1608Metric | 9 | C18, C19, C20, C21, C24, C34, C205, C212, C213 | partly |
| PCM5102APWR | C107671 | TSSOP-20 4.4x6.5mm P0.65mm | 2 | U10, U11 |  |
| 2.2uF | C23630 | C 0603 1608Metric | 6 | C22, C23, C32, C33, C209, C211 | partly |
| 100nF | C14663 | C 0603 1608Metric | 11 | C25, C26, C27, C35, C36, C37, C203, C207, C215, C216, C217 | partly |
| 10uF | C15850 | C 0805 2012Metric | 9 | C28, C29, C38, C39, C202, C204, C206, C214, C218 | partly |
| 470Ω | C23179 | R 0603 1608Metric | 4 | R48, R49, R50, R51 |  |
| 2.2nF C0G | C28260 | C 0805 2012Metric | 4 | C30, C31, C40, C41 |  |
| Main board plug | C5116480 | PinHeader 2x10 P2.54mm Vertical | 1 | J24 |  |
| MIC (to 3.5 mm jack) | C144394 | JST XH B3B-XH-A 1x03 P2.50mm Vertical | 1 | J201 | yes |
| PESD5V0S1BA | C2827694 | D SOD-323 HandSoldering | 1 | D201 | yes |
| 1nF | C1588 | C 0603 1608Metric | 3 | C201, C208, C210 | yes |
| 10Ω | C22859 | R 0603 1608Metric | 1 | R201 | yes |
| 1k | C21190 | R 0603 1608Metric | 3 | R202, R208, R210 | yes |
| 2.2k | C4190 | R 0603 1608Metric | 1 | R203 | yes |
| 100k | C25803 | R 0603 1608Metric | 1 | R204 | yes |
| 10k | C25804 | R 0603 1608Metric | 4 | R205, R206, R207, R209 | yes |
| TLV9062IDR | C398355 | SOIC-8 3.9x4.9mm P1.27mm | 1 | U201 | yes |
| 4.7k | C23162 | R 0603 1608Metric | 1 | R211 | yes |
| PCM1808PWR | C55513 | TSSOP-14 4.4x5mm P0.65mm | 1 | U202 | yes |
| 33Ω | C23140 | R 0603 1608Metric | 1 | R212 | yes |

LCSC sells passives in strips of 50-100, so one order covers several boards. Every number above was checked on LCSC/JLCPCB today. J201's number was C144394 (the 3-pin part), not C144395 (that's the 4-pin).

**Also buy (no LCSC number given, any equivalent works):**
- A 3.5 mm stereo panel-mount jack (for example a PJ-392 style).
- A JST XH 3-pin housing (XHP-3) with SXH-001T-P0.6 crimps, or a pre-crimped XH 3-pin pigtail, which is easier.
- You already have the mic.

## Soldering order
1. Underside first, before J24 is in: U202 (PCM1808, TSSOP, 0.65 mm pitch, so flux and drag-solder), U201, then the 0603/0805 parts, D201.
2. Top side: U10/U11 (check PCM5102A pin 18/19 for a bridge, as on rev 0.6), U8/U9, the rest of the passives.
3. J24 (bottom) and J201 (top) last.

## Bench checks
- With the module powered, VIM3_5V is about 5 V, +5V_MIC about 4.9 V, and +3V3_DAC_A/D are 3.3 V.
- U202 pin 1 (VREF) reads about 2.45 V, and VMID (C206) about 2.45 V.
- With the mic plugged in, the tip sits at about 2-3 V. Without the mic it reads close to +5V_MIC.
- In Android or Linux: `arecord` on the mic capture device while you speak. If it clips, bridge JP201.

## Files
- `carradio_audio_rev07.kicad_sch / .kicad_pcb / .kicad_pro`: KiCad 10 project (open the .kicad_pro).
- `carradio_audio_rev07_schematic.pdf`, `render_top.png`, `render_bottom.png`
- `carradio_audio_rev07_bom.csv` (full BOM with notes), `carradio_audio_rev07_gerbers.zip`, `jlc_bom.csv` / `jlc_cpl.csv`
