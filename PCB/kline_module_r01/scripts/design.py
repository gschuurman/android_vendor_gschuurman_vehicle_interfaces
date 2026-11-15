# K-line module rev 0.1 for the car radio main board rev 0.6 (J10 socket, H8 standoff).
# Coordinates are MAIN-BOARD KiCad coordinates (mm), so the header lands exactly on J10.
NAME = "kline_module"
# Main board: J10 pin 1 at (78.19, 27.63), H8 at (69.6, 18.5). USB module starts at y 32.5, audio module ends at x 63.5.
BX0, BY0, BX1, BY1 = 65.0, 11.5, 93.5, 32.0
def j10(n):
    k = (n - 1) // 2
    return (78.19 + 2.54 * k, 27.63 if n % 2 else 30.17)
J1_NETS = {1: "+3V3", 2: "GND", 3: "K_TXD", 4: "K_RXD", 5: "K_EN", 6: "GND", 7: "VBAT", 8: "+5V_AON"}
HS0805 = "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder"
CS0805 = "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder"
# ref, symbol, value, footprint, x, y, rot, side, {pad: net}, LCSC, MPN/description, note
PARTS = [
 ("U1", "kline:L9637D", "L9637D", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", 76.3, 14.4, 0, "F",
   {"1": "K_RXD", "3": "+3V3", "4": "K_TXD", "5": "GND", "6": "KLINE", "7": "VS"},
   "C153038", "ST L9637D (E-L9637D013TR) ISO 9141 K-line transceiver, SO-8", "Glenn has these (LCSC number for reference). VCC 3.3 V is in spec (3-7 V), so RX/TX need no level shifting"),
 ("C1", "Device:C", "100nF", CS0805, 73.2, 19.6, 90, "F", {"1": "+3V3", "2": "GND"},
   "C49678", "YAGEO CC0805KRX7R9BB104 0805 100nF 50V X7R", "U1 VCC decoupling"),
 ("C2", "Device:C", "100nF", CS0805, 82.6, 16.6, 0, "F", {"1": "VS", "2": "GND"},
   "C49678", "YAGEO CC0805KRX7R9BB104 0805 100nF 50V X7R", "U1 VS decoupling"),
 ("D2", "Device:D_TVS", "SMAJ26CA", "Diode_SMD:D_SMA", 78.6, 21.5, 90, "F", {"1": "KLINE", "2": "GND"},
   "C571371", "High Diode SMAJ26CA 400W bidirectional TVS, 26V standoff, SMA", "K-line ESD / transient clamp"),
 ("C4", "Device:C", "1nF", CS0805, 75.6, 22.0, 90, "F", {"1": "KLINE", "2": "GND"},
   "C1588", "Samsung CL10B102KB8NNNC 1nF 50V X7R (0603 from rev 0.6 stock fits the 0805 pads; 470pF also fine)", "K-line EMI cap (ISO 9141 allows up to 1.3 nF)"),
 ("R1", "Device:R", "510R 1W", "Resistor_SMD:R_2512_6332Metric_Pad1.40x3.35mm_HandSolder", 67.1, 26.5, 90, "F", {"1": "VS", "2": "KPU"},
   "C269361", "TyoHM RMC25125105%N 2512 510R 1W", "ISO 9141 K-line pull-up to battery (0.4 W if K is stuck low at 14.4 V)"),
 ("JP1", "Jumper:SolderJumper_2_Bridged", "K pull-up", "Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm", 73.3, 23.4, 90, "F", {"1": "KPU", "2": "KLINE"},
   "", "solder jumper, bridged by default", "cut the thin trace between the pads to remove the 510R pull-up"),
 ("Q1", "Device:Q_PMOS_GSD", "FDN5618P", "Package_TO_SOT_SMD:SOT-23", 82.7, 13.25, 0, "F", {"1": "GATE", "2": "VBAT", "3": "VS"},
   "C400792", "onsemi FDN5618P -60V P-MOSFET SOT-23", "high-side switch: K-line side fully off when parked (same part as main-board Q2)"),
 ("D1", "Device:D_Zener", "BZT52C12", "Diode_SMD:D_SOD-123", 87.2, 13.25, 0, "F", {"1": "VBAT", "2": "GATE"},
   "C124196", "Diodes BZT52C12-7-F 12V zener SOD-123", "Q1 Vgs clamp"),
 ("R2", "Device:R", "100k", HS0805, 86.5, 16.6, 0, "F", {"1": "VBAT", "2": "GATE"},
   "C149504", "UNI-ROYAL 0805W8F1003T5E 0805 100k 1%", "Q1 gate pull-up (off by default)"),
 ("R3", "Device:R", "10k", HS0805, 90.4, 16.6, 0, "F", {"1": "GATE", "2": "QD"},
   "C17414", "UNI-ROYAL 0805W8F1002T5E 0805 10k 1%", "Q1 gate drive"),
 ("Q2", "Device:Q_NMOS_GSD", "2N7002", "Package_TO_SOT_SMD:SOT-23", 67.35, 13.6, 0, "F", {"1": "K_EN", "2": "GND", "3": "QD"},
   "C8545", "JSCJ 2N7002 SOT-23", "GPIO28 high = K-line side powered"),
 ("R4", "Device:R", "10k", HS0805, 70.3, 13.75, 90, "F", {"1": "K_EN", "2": "GND"},
   "C17414", "UNI-ROYAL 0805W8F1002T5E 0805 10k 1%", "keeps Q2 off while GPIO28 floats"),
 ("D3", "Device:LED", "green", "LED_SMD:LED_0805_2012Metric_Pad1.15x1.40mm_HandSolder", 73.4, 28.4, 90, "F", {"1": "GND", "2": "LEDA"},
   "C2297", "Hubei KENTO KT-0805G green LED 0805", "lit when the K-line side is powered"),
 ("R5", "Device:R", "4.7k", HS0805, 75.4, 28.6, 90, "F", {"1": "LEDA", "2": "VS"},
   "C17673", "UNI-ROYAL 0805W8F4701T5E 0805 4.7k 1%", "LED current about 2.5 mA"),
 ("J2", "Connector_Generic:Conn_01x02", "K-line to car", "Connector_JST:JST_XH_S2B-XH-A_1x02_P2.50mm_Horizontal", 83.5, 23.2, 90, "F", {"1": "KLINE", "2": "GND"},
   "C157931", "JST S2B-XH-A(LF)(SN) side entry, 2.5 mm", "pin 1 K-line (OBD-II pin 7), pin 2 GND (OBD-II pin 4/5); opening faces the back plate"),
 ("J1", "Connector_Generic:Conn_02x04_Odd_Even", "to main J10", "Connector_PinHeader_2.54mm:PinHeader_2x04_P2.54mm_Vertical", 0, 0, 0, "B",
   {str(k): v for k, v in J1_NETS.items()},
   "C124378", "2x Ckmtw B-2100S04P-A110 1x4 2.54mm male header (one per row)", "soldered from the top, plastic on the underside, plugs into main-board J10"),
 ("H1", "Mechanical:MountingHole", "M2", "MountingHole:MountingHole_2.2mm_M2", 69.6, 18.5, 0, "F", {},
   "", "M2 x 18 screw through the 11 mm spacer into H8", ""),
]
SILK = [("K-LINE r0.1", 70.4, 31.3, 0.7), ("MG F K-line module r0.1", 71.0, 24.3, 0.8, __import__("pcbnew").B_SilkS, True)]
import pcbnew as _p
SILK2 = [
 ("K-LINE", 90.5, 28.0, 0.8), ("r0.1", 90.5, 29.3, 0.8), ("MG F", 90.5, 30.6, 0.8),
 ("K", 86.0, 23.2, 0.8), ("G", 86.0, 20.7, 0.8),
 ("K-line module r0.1", 80.0, 13.0, 0.8, _p.B_SilkS, 0, True),
 ("main board rev 0.6 J10", 80.0, 14.4, 0.8, _p.B_SilkS, 0, True),
]
