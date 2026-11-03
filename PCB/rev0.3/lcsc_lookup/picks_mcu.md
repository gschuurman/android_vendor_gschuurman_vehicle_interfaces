# MCU section: LCSC picks (verified 2026-09-29 by fetching each lcsc.com product page)

Basic/extended was checked against cdfer/scraped/ComponentList.csv (the JLCPCB basic/preferred list). Prices are USD per unit, at qty 10 or at the smallest break shown on the page.

| designator | LCSC | MPN | manufacturer | package (as on page) | specs verified | stock | price each | basic/extended | note |
|---|---|---|---|---|---|---|---|---|---|
| U20 | C42415655 | RP2350B | Raspberry Pi | QFN-80-EP(10x10) | Cortex-M33 150MHz, 48 I/O | **Unclear:** the page shows "Not available now", but its metadata says about 3,049 to 4,642 in stock (two fetches gave different numbers) | "From $1.0682" (metadata only, no break table shown) | extended | Stock needs a manual check in the JLCPCB parts search. JLCPCB also has its own listing C9900138392 ("New Arrivals", JLCPCB-sourced, PCBA only, stock not shown). |
| U20 (alt) | C39843328 | RP2354B | Raspberry Pi | QFN-80-EP(10x10) | Cortex-M33 150MHz, 48 I/O, 520KB SRAM, 2MB stacked flash | 3,028 | $1.4769 | extended | In stock. Same package and pinout family as RP2350B, with 2MB flash inside, so U21 could be dropped if 2MB is enough. |
| U21 | C97521 | W25Q128JVSIQ | Winbond | SOIC-8-208mil | 128Mbit, 2.7 to 3.6V, 133MHz, SPI/Dual/Quad | 4,853 | $2.24 | **basic** | |
| U19 | C51118 | AP2112K-3.3TRG1 | Diodes | SOT-25-5 (SOT-23-5) | 3.3V, 600mA, enable input, thermal shutdown | 40,510 | $0.1726 | extended | |
| L5 | C42411119 | AOTA-B201610S3R3-101-T | Abracon | 0806 (= 2016 metric) | 3.3uH, Irated 2.1A, Isat 2.4A, DCR 115mOhm | 3,435 | $0.2864 | extended | This is the exact reference part, and it is stocked, so no alternative is needed. It is polarised: follow the orientation mark as in the Raspberry Pi design guide. |
| Y3 | C20625731 | ABM8-272-T3 | Abracon | SMD3225-4P | 12MHz, CL 10pF, ESR 50 ohm, +/-30ppm, -40 to 85C | 16,530 | $0.5139 | extended | The exact reference part is stocked. |
| C99, C100 | C1644 | CL10C150JB8NNNC | Samsung Electro-Mechanics | 0603 | 15pF, 50V, C0G, +/-5% | 629,150 | $0.0115 (smallest break shown, 50+) | **basic** | |
| R83, R84 | C25190 | 0603WAF270JT5E | UNI-ROYAL | 0603 | 27 ohm, +/-1%, 100mW | 9,500 | $0.0021 (100+ tier) | **basic** | The page lists the tolerance as +/-1%, although the MPN contains a "J". |
| SW1, SW2 | C2886898 | TL3342F160QG | E-Switch | SMD-4P,5.2x5.2mm (LCSC's label) | 1.6N (160gf), height 1.54mm | 2,181 | $0.8408 | extended | This is the genuine TL3342, so it matches the KiCad SW_SPST_TL3342 footprint. LCSC's "5.2x5.2mm" package label disagrees with the 4.2x3.2mm body in the footprint name, so check the datasheet drawing. Alternative: C2886894 TL3342F260QG (2.6N), only 152 in stock at $0.9459. |
| TH1 | C13564 | NCP18XH103F03RB | Murata | 0603 | 10k at 25C, +/-1%, B 3380K (25/50) | 276,130 | $0.0467 | extended | The exact example part. Note: C77131 is the 0402 version (NCP15XH103F03RC), not this part. |
| J22 | C124378 | B-2100S04P-A110 | Ckmtw (Cankemeng) | Through Hole, P=2.54mm | 1x4, 2.54mm, straight, male, THT | 64,570 | $0.0537 | extended | |
| J21 | C57369 | 2.54-1*10P | BOOMELE | Through Hole, P=2.54mm | 1x10, 2.54mm, straight, male, THT | 22,510 | $0.0698 | extended | |

Notes:
- **RP2350B stock (C42415655):** the only line I could not confirm. The live page says "Not available now", which contradicts the stock count in its metadata, and the JLCPCB page for this part shows no stock figure. The RP2354B (C39843328) is clearly in stock.
- Only one basic part in the list has a JLCPCB-specific alternative: the 12MHz crystal C9002 (Yangxing X322512MSB4SI) is basic. It was **not** fetched or verified here, and it is a 20pF-load part, so it does not suit 15pF caps. Keep the Abracon part.
