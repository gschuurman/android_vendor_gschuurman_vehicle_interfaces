# On-board 4-channel audio output (proposal, 2026-09-29)

Goal: replace the USB 7.1 card with a proper 4-channel line-level output on the peripheral
board, at least 24-bit and a high sample rate. It feeds the JBL amplifier through the car's
ISO 10487 harness.

## Recommendation

**I2S straight from the VIM3 header into two TI PCM5102A DACs, one for front and one for
rear.**

```
VIM3 40-pin header (TDM-B)                        peripheral board
  pin 29  GPIOA_1  BCLK   ─────────┬──────────────► PCM5102A #1  BCK   ─► FL / FR line out
  pin 32  GPIOA_2  LRCK   ─────────┼──┬───────────► PCM5102A #1  LRCK
  pin 31  GPIOA_3  DOUT0  ─────────┼──┼───────────► PCM5102A #1  DIN
                                   └──┼───────────► PCM5102A #2  BCK   ─► RL / RR line out
                                      └───────────► PCM5102A #2  LRCK
  pin 33  GPIOA_4  DOUT1  ────────────────────────► PCM5102A #2  DIN
  pin 35  GPIOH_5  DOUT3  (spare lane: a sub or a 3rd stereo pair later)
  pin 30  GPIOA_0  MCLK   not used; the PCM5102A makes its own clock from BCLK
Pico GPIO ─► XSMT (soft mute) on both DACs, sequenced with the amp remote output
```

Why this route:
- **The pins are there.** The kernel's G12 pinctrl (`pinctrl-meson-g12a.c`) lets header pins 31, 33
  and 35 carry TDM-B data lanes 0, 1 and 3, next to BCLK (29), LRCK (32) and MCLK (30). Two
  lanes of ordinary stereo I2S give 4 channels without TDM, at any rate the DACs support.
- **The kernel side is already mostly there.** The whole Amlogic AXG TDM stack (tdmout, frddr,
  axg-sound-card) is in your vendor_dlkm today for HDMI audio. The `pcm5102a` codec driver is
  in your kernel tree and only needs building as a vendor module.
- **The audio HAL barely changes.** `hardware_amlogic_yukawa_audio` finds the ALSA card by
  name (`PrimaryMixer::findAlsaCardByName`) and already does fade/balance in software for 4, 6
  and 8 channels (`applyCarBalanceFaderInterleaved`). Point it at the new card and it works
  with your CarAudioTuner.
- **PCM5102A** ([LCSC C107671](https://jlcpcb.com/partdetail/TexasInstruments-PCM5102APWR/C107671)):
  32-bit and up to 384 kHz, 112 dB SNR, 2.1 Vrms ground-centred line output with no coupling
  caps, and no I2C setup (format, mute and filter are pins). Proper line level for a car amp.
- **Quality comes from the analog layout**, which is where a USB card falls down: a
  dedicated low-noise LDO for the DAC analog supply, a quiet analog ground island joined at one
  point, a short I2S path, and hardware mute to avoid pops.

**What it needs from you:** header pins 32, 33 and 35 are today's reverse input, backlight
enable and backlight PWM. They are free once those move to the Pico, which the new MCU design
already does.

## Board details

- **Supply:** the DACs only need to run while the VIM3 is on. Take 5V from the VIM3 side (or
  the board's own 5V rail if it ends up powering the VIM3), then a low-noise 3.3V LDO for
  AVDD/CPVDD, with DVDD on a separate LDO or ferrite.
- **Output:** the PCM5102A datasheet's 470 Ω / 2.2 nF output filter, ESD diodes, then the line
  outs to the ISO C1 block, with optional RCA footprints.
- **Mute and pops:** the Pico drives XSMT on both DACs. At power-up it unmutes the DACs,
  then turns the amp remote on. At power-down it turns the amp remote off, then mutes the
  DACs. The firmware plan already delays the amp remote by 2 s.
- **Ground loops (alternator whine):** line-out ground ties to the audio ground at a single
  point. Add a 0 Ω / 10 Ω footprint between audio ground and power ground so a ground lift can
  be tried. If your JBL amp has balanced/differential inputs, a balanced line driver is the
  next step.
- **I2S over the ribbon:** keep it short (about 10–15 cm). Put 22–33 Ω series resistors at
  the board entry and a ground wire next to BCLK. MCLK isn't routed at all.
- Resolution: 24-bit samples in 32-bit I2S slots at 48, 96 or 192 kHz. Android mixes at the
  primary output rate (usually 48 kHz). Higher rates only matter for hi-res content played
  bit-perfect.

## Software changes (for later)

- **Kernel DT:** enable `tdmif_b`, `tdmout_b` and a frddr. Add a dai-link to the
  axg-sound-card with two `pcm5102a` codec nodes and a tx-mask per lane (lane 0 = front,
  lane 1 = rear). Pinmux: `tdm_b_sclk`, `tdm_b_fs`, `tdm_b_dout0`, `tdm_b_dout1`. U-Boot
  doesn't apply your DTBO, so this goes in the base DT.
- **Modules:** add `snd-soc-pcm5102a.ko` to vendor_dlkm.
- **Audio HAL:** set the card name so the primary mixer finds the new card, with a 4-channel
  output. The existing "smart mirroring" logic only applies to 6-channel output.

## Alternatives considered

| Option | Why not first |
|---|---|
| TI PCM3168A (8 DAC + 6 ADC, TDM on one lane) | Room to grow, and the ADCs could take a microphone for Dicio or an aux input. But its outputs are differential and need an op-amp stage, and it needs a 5V analog supply and I2C setup. It's the upgrade path if you want more channels or inputs. Driver is in your kernel tree. |
| Speaker-level outputs (ISO B) with TI TAS6424 (4× class-D, TDM input) | Only makes sense if the JBL amp goes. It brings heat, a 14.4V high-current path and EMC work. Driver is in your kernel tree. |
| USB audio on the board | No kernel or DT work, but it needs a high-speed USB audio bridge chip (XMOS, C-Media) and its firmware, plus another USB port. The Pico can't do it: full-speed USB tops out around 4 channels at 24-bit/48 kHz. |
| Keep the 7.1 USB card | That's what you want to replace. |

## ISO 10487 connector

ISO 10487 fixes the connector shapes, but the pin assignments are defined by the manufacturer,
most of all in section C ([HandWiki](https://handwiki.org/wiki/ISO_10487)). The common European
layout for A and B is below. **Please check it against your MG F harness or adapter before
this goes on the board.**

| Pin | Common use | On this board |
|---|---|---|
| A4 | +12V permanent | BATT+ (always-on supply for the Pico) |
| A5 | +12V remote (power antenna or amp) | Amp remote output (Q2) |
| A6 | Illumination / dimmer | ILLUM opto input |
| A7 | +12V ACC | ACC opto input, amp remote supply |
| A8 | Ground | Ground |
| A1 / A2 | Speed signal / phone mute | Spare inputs (the MG F likely has no speed signal) |
| B1–B8 | Speakers: RR+/−, RF+/−, LF+/−, LR+/− | Not used with the JBL amp; reserved for a TAS6424 later |
| C1 1–6 | Commonly LR, RR, LF, RF line out, line-out ground, remote | Line outs from the two DACs (**verify your harness's C1 layout**) |

Connectors on the board: PCB-mount ISO 10487 blocks are hard to find with a reliable library
footprint. The safer build is Molex Micro-Fit headers on the board, which are library parts,
plus a short ISO 10487 pigtail on the radio side.

## Questions

1. Which JBL amplifier is it? Does it take RCA/low-level input, high-level (speaker) input, or
   balanced input?
2. What is the pin layout of the ISO C1 line-out block in your harness, if you have one?
