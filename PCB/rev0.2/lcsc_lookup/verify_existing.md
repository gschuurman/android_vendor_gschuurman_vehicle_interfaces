# LCSC verification of existing BOM part numbers (checked 2026-09-29)

Source: LCSC product pages fetched with WebFetch (https://www.lcsc.com/product-detail/<C>.html). Prices are USD per unit at qty 10, or at the smallest break shown (noted). Stock is LCSC warehouse stock; JLCPCB assembly stock is separate. Basic/extended: from cdfer ComponentList.csv (basic + preferred list).

| LCSC | verdict | MPN on page | package on page | price each | basic/extended | replacement LCSC if needed | note |
|---|---|---|---|---|---|---|---|
| C8678 | OK | SS34 (MDD) | SMA (DO-214AC) | $0.0351 @20+ | basic | | 40V 3A; 3.89M in stock |
| C13585 | OUT OF STOCK | CL31A106KBHNNNE (Samsung) | 1206 | $0.2687 @10+ | basic | C77092 (GRM31CR61H106KA12L, Murata 1206 10uF 50V X5R ±10%, 115,815 in stock, extended; only a 4000+ price was reported, $0.154) | Specs match (10uF 50V X5R ±10%). Also possible: C89632 CL31B106KBHNNNE (X7R, 69,225 in stock, $0.3545 @5+, extended). As a basic part, JLCPCB may still have its own stock, so check there first |
| C14663 | OK | CC0603KRX7R9BB104 (YAGEO) | 0603 | $0.0124 @50+ | basic | | 100nF 50V X7R ±10%; 9.27M in stock |
| C524782 | OK | TPS560430XDBVR (TI) | SOT-23-6 | $0.46 @10+ | extended | | 4-36V, 600mA, 1.1MHz; 38,070 in stock |
| C96895 | OK (stock unconfirmed) | SWPA4030S180MT (Sunlord) | SMD (4x4mm) | $0.0481 @10+ | extended | | Short URL returns 404. The long URL (Power-Inductors_Sunlord-SWPA4030S180MT_C96895.html) renders MPN, 18uH ±20%, 1.1A/1.4A and prices, but no stock figure. The JLCPCB partdetail page lists it as an active extended part. Check stock in the JLCPCB BOM tool |
| C25803 | OK | 0603WAF1003T5E (UNI-ROYAL) | 0603 | $0.0031 @100+ | basic | | 100k 1%; 15.98M in stock |
| C23352 | OK | 0603WAF2402T5E (UNI-ROYAL) | 0603 | $0.0023 @100+ | basic | | 24k 1%; 739,100 in stock |
| C45783 | OK | CL21A226MAQNNNE (Samsung) | 0805 | $0.2222 @20+ | basic | | 22uF 25V X5R, ±20% (description gave no tolerance); 1.51M in stock |
| C2480 | OK | SS14 (MDD) | SMA (DO-214AC) | $0.0181 @50+ | basic | | 40V 1A; 848,450 in stock |
| C17673 | OK | 0805W8F4701T5E (UNI-ROYAL) | 0805 | $0.0051 @100+ | basic | | 4.7k 1%; 3.24M in stock |
| C81598 | OK | 1N4148W (ST/Semtech) | SOD-123 | $0.0125 @10 | basic | | 75V 150mA; 4.13M in stock |
| C106900 | OUT OF STOCK | EL817S1(C)(TU)-F (Everlight) | SMD-4P | $0.0235 (from) | basic | C470884 (EL817S1(C)(TU)-FV, Everlight, SMD-4P, 5kV, 3,020 in stock, $0.0766 @10+, extended) | Same S1 SMD-4 lead form and C rank, -FV suffix variant. C14210 EL817S(C)(TU)-F is also out of stock. Basic part, so JLCPCB stock may differ |
| C23162 | OK | 0603WAF4701T5E (UNI-ROYAL) | 0603 | $0.0028 @100+ | basic | | 4.7k 1%; 14.2M in stock |
| C21189 | OK | 0603WAF0000T5E (UNI-ROYAL) | 0603 | $0.0013 @10k+ (only break reported) | basic | | 0 ohm jumper; 17.4M in stock |
| C25804 | OK (low LCSC stock) | 0603WAF1002T5E (UNI-ROYAL) | 0603 | $0.0019 @100+ | basic | | 10k 1%. LCSC showed only 100 in stock. Common basic part, so JLCPCB stock is likely fine, but check |
| C124196 | OK | BZT52C12-7-F (Diodes) | SOD-123 | $0.0651 @10+ | extended | | 12V zener 370mW; 2,500 in stock |
| C22775 | OK | 0603WAF1000T5E (UNI-ROYAL) | 0603 | $0.0032 @100+ | basic | | 100 ohm 1%; 6.08M in stock |
| C21190 | OK | 0603WAF1001T5E (UNI-ROYAL) | 0603 | $0.0026 @100+ | basic | | 1k 1%; 4.46M in stock |
| C22935 | OK | 0603WAF1004T5E (UNI-ROYAL) | 0603 | $0.0019 @100+ | basic | | 1M 1%; 4.58M in stock |
| C22961 | OK | 0603WAF2203T5E (UNI-ROYAL) | 0603 | $0.0016 @100+ | basic | | 220k 1%; 1.38M in stock |
| C80670 | OUT OF STOCK | LP5907MFX-3.3/NOPB (TI) | SOT-23-5 | $0.2108 @5+ | extended | C5370990 (TPLP5907MFX-3.3, TECH PUBLIC, SOT-23-5, 3.3V 300mA, 194,560 in stock, $0.10 @5+, extended) | This is a second-source clone, not TI, so noise and PSRR specs may differ from the genuine LP5907. Also possible: C20538881 (LP5907MFX-3.3/NOPB(MS), MSKSEMI, 3,440 in stock, $0.0937 @5+). Confirm the clone's pinout matches (IN/GND/EN/NC/OUT) before substituting |
| C15849 | OUT OF STOCK | CL10A105KB8NNNC (Samsung) | 0603 | $0.0168 @50+ | basic | C77386 (GRM188R61H105KAALD, Murata 0603 1uF 50V X5R ±10%, 39,290 in stock, $0.0764 @10+, extended) | Exact spec match. Basic part, so check JLCPCB stock first |
| C15850 | OK | CL21A106KAYNNNE (Samsung) | 0805 | $0.0656 @20+ | basic | | 10uF 25V X5R ±10%; 692,200 in stock |
| C5119087 | OK (only 1 in stock) | NEO-M9N-00B (u-blox) | SMD-24P LCC 12.2x16.0 | $16.04 @10+ | extended | | LCSC showed 1 unit. The board needs 1, so any build of more than one board is stock-limited |
| C57112 | OUT OF STOCK | 0603B103K500NT (FH) | 0603 | $0.0109 @50+ | basic | C1589 (CL10B103KB8NNNC, Samsung 0603 10nF 50V X7R ±10%, 1.81M in stock, $0.0103 @50+, extended per the CSV) | Exact spec match |
| C22859 | OK | 0603WAF100JT5E (UNI-ROYAL) | 0603 | $0.0032 @10+ | basic | | 10 ohm 1% (in UNI-ROYAL codes the "J" is a decimal multiplier, not a tolerance); ±400ppm tempco; 5.75M in stock |
| C20917 | OK | AO3400A (AOS) | SOT-23 | $0.0853 @5+ | basic | | 30V 5.7A N-MOSFET; 584,445 in stock |
| C23140 | OK | 0603WAF330JT5E (UNI-ROYAL) | 0603 | $0.0025 @100+ | basic | | 33 ohm 1%; 4.14M in stock |
| C107671 | OK | PCM5102APWR (TI) | TSSOP-20 | $1.2881 @10+ | extended | | 6,471 in stock |
| C23630 | OK | CL10A225KO8NNNC (Samsung) | 0603 | $0.0182 @50+ | basic | | 2.2uF 16V X5R ±10%; 1.05M in stock |
| C23179 | OK | 0603WAF4700T5E (UNI-ROYAL) | 0603 | $0.0022 @100+ | basic | | 470 ohm 1%; 4.61M in stock |
| C28260 | OUT OF STOCK | CL21C222JBFNNNE (Samsung) | 0805 | $0.0293 @10+ | basic | none verified | Specs match (2.2nF 50V C0G ±5%). I found no in-stock 0805 C0G 2.2nF replacement page to verify. C107146/C1728 are X7R, which is not equivalent. Basic part, so JLCPCB stock may still cover it; otherwise search the JLCPCB parametric tool |
| C2864583 | OK | TPS55288RPMR (TI) | VQFN-26-HR (3.5x4) | $2.07 @10+ | extended | | 2.7-36V in, I2C buck-boost; 5,183 in stock |
| C25819 | OUT OF STOCK | 0603WAF4702T5E (UNI-ROYAL) | 0603 | $0.0036 @100+ | basic | C105579 (RC0603FR-0747KL, YAGEO 0603 47k 1%, 409,900 in stock, $0.0031 @100+, extended per the CSV) | Exact spec match. Basic part, so check JLCPCB stock first |
| C25981 | OK | 0603WAF8201T5E (UNI-ROYAL) | 0603 | $0.0033 @100+ | basic | | 8.2k 1%; 710,500 in stock |
| C53987 | OK | 0603B472K500NT (FH) | 0603 | $0.0089 @50+ | basic | | 4.7nF 50V X7R ±10%; 425,650 in stock |
| C1653 | OK | CL10C220JB8NNNC (Samsung) | 0603 | $0.0058 @100+ | basic | | 22pF 50V C0G ±5%; 1.71M in stock |
| C840100 | OK | CSD18543Q3A (TI) | VSONP-8 (3.3x3.3) | $0.6572 @10+ | extended | | 60V N-MOSFET, 8.1 mOhm @10V; 13,400 in stock |
| C19666 | OK | CL10A475KO8NNNC (Samsung) | 0603 | $0.0298 @10 | basic | | 4.7uF 16V X5R ±10%; 606,340 in stock |
| C4154405 | OK | CH334R (WCH) | QSOP-16 (150mil) | $0.4589 @10 | extended | | 4-port USB 2.0 hub; 19,419 in stock |
| C841384 | OK | LMR33630ADDAR (TI) | ESOP-8 (SO PowerPAD-8) | $0.6352 @10+ | extended | | 3.8-36V, 3A, 400kHz; 44,888 in stock |
| C140303 | OK | TPS2561DRCR (TI) | VSON-10-EP (3x3) | $1.1505 @10+ | extended | | dual 2.8A switch; 2,196 in stock |
| C23153 | OK | 0603WAF3902T5E (UNI-ROYAL) | 0603 | $0.0016 @100+ | basic | | 39k 1%; 158,000 in stock |
| C15008 | OK | CL31A107MQHNNNE (Samsung) | 1206 | $0.1269 @10 | basic | | 100uF 6.3V X5R ±20%; 1.50M in stock |

All replacement candidates above are "extended" in ComponentList.csv.
Page data came from WebFetch's summarizer. Stock figures are a snapshot.
