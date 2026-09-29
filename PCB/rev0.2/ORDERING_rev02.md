# Ordering notes: mainboard rev 0.2 (2026-09-29)

Every fitted part in `carradio_peripheral_rev02_bom.csv` now has an LCSC number. Each number was checked
on its lcsc.com product page (MPN, package and specs) on 2026-09-29. The schematic carries the same
numbers in each part's `LCSC` field, so EasyEDA picks up the part and its footprint on import. The one
exception is U12 (TPS55288, C2864583), whose footprint was left empty on purpose: take it from the EasyEDA
library.

The full lookup tables, with alternatives and stock levels, are in `lcsc_lookup/`.

## Cost estimate for one board

These are LCSC unit prices at qty 10 or the smallest break.

| Item | Estimate |
|---|---|
| Parts | about $66 |
| JLCPCB assembly | about $135 extra per order (see below) |

**Parts.** The biggest items are:

| Part | Price |
|---|---|
| NEO-M9N | $16 |
| L4 inductor (Coilcraft) | $11.78 |
| SMA jack (genuine Amphenol) | $10 |
| TPS55288 | a few dollars |

**JLCPCB assembly.** 45 of the 77 unique parts are "extended" parts. JLCPCB charges a loading fee for
each unique extended part (about $3 each), so that adds about $135 per order however many boards you
order. The 15 through-hole connectors are cheaper to solder yourself.

## Changes made while picking parts

- **Out of stock at LCSC, swapped for the same spec:**

  | Was | Now |
  |---|---|
  | 1206 10uF 50V | C77092 |
  | EL817 optos | C470884 |
  | 0603 1uF 50V | C77386 |
  | 0603 10nF | C1589 |
  | 0603 47k | C105579 |

- **LP5907 LDOs (U6, U8, U9).** The TI part is out of stock at LCSC, so the BOM now has the TECH PUBLIC
  clone, C5370990. For the DAC supplies (U8, U9) I would rather use the genuine TI part. If JLCPCB or
  another supplier has TI LP5907MFX-3.3 in stock, use that.
- **Q10 reverse-polarity FET.** It's the NCE40P70K (C130101, -40V, 10 mOhm). The SQD40031EL I named
  earlier is only -30V.
- **D14 load-dump TVS.** It's a 5.0SMDJ22A in SMC (C2990362). The SM8S has no KiCad footprint.
- **L3 (C780205, Bourns SRP1265A-4R7M).** 28A saturation, but only about 100 in stock. It uses the
  SRP1245A land pattern, which has the same outline.
- **L4 (C19191627, Coilcraft XAL6060).** It's $11.78. Cheaper 7x7mm parts either had 2-3x the
  resistance (more heat at 3A) or were out of stock. Any shielded 8.2-10uH part with at least 5A
  saturation current will work.
- **F4 fuse holder.** The Keystone 3568 is out of stock. The BOM uses a Littelfuse 01530008Z (C206907),
  which has a different pin layout, so use its LCSC footprint. The 7.5A fuse is C178942.
- **J14 FPC.** The genuine Hirose FH12 is single-sided. The BOM uses a XUNPU dual-contact part
  (C2856837), so the ribbon works either way up. Use its LCSC footprint, not the FH12 one.
- **J13 HDMI.** Amphenol 10029449-111RLF (C427307) is a plating variant of the -001RLF. Compare the land
  pattern against the drawing once.

## Check before ordering

- **NEO-M9N (C5119087).** LCSC had only 1 in stock. Check JLCPCB stock, or buy the module elsewhere and
  fit it yourself.
- **2.2nF 0805 C0G output filter caps (C30, C31, C40, C41, part C28260).** Out of stock at LCSC. Any 0805
  2.2nF 50V C0G/NP0 part works; X7R does not.
- **J2 (C9138).** Check on the drawing that this 2x20 header is the shrouded (keyed) type.
- **Q2 (FDN5618P) and Q3 (2N7002).** The pinout should be 1=G 2=S 3=D; check it against the datasheets.
