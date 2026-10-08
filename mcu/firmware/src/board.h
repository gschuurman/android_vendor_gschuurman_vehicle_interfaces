// RP2350B pin map for the car radio peripheral board, rev 0.6.
//
// Taken from the rev 0.6 main-board netlist (PCB/rev0.6/main/carradio_peripheral_rev06.net,
// U20). The comment after each pin names the net and the parts that set its idle level.
#pragma once

#define BOARD_REV 6

// ---- Car inputs: EL817 opto, emitter to the pin, 4.7k pull-down. High = 12V present. ----
#define PIN_ACC_IN        43  // /MCU_ACC_IN    U2, R4 (ISO A7, via F2)
#define PIN_ILLUM_IN      37  // /MCU_ILLUM_IN  U3, R6 (ISO A6)
#define PIN_REV_IN        35  // /MCU_REV_IN    U4, R30 (ISO A1)
#define PIN_PARK_IN       14  // /MCU_PARK_IN   U5, R32 (ISO A2, switch to ground; open = released)

// ---- Other inputs ----
#define PIN_SBC_SENSE      6  // /MCU_SBC_SENSE  VIM3 3.3V via R7 1k, R8 4.7k pull-down. High = VIM3 on
#define PIN_SERVICE       19  // /MCU_SERVICE    JP1 to 3.3V, R9 4.7k pull-down. High = service mode
#define PIN_USBP_PG       36  // /MCU_USBP_PG    USB module LMR33630 PG, R89 10k pull-up. High = good
#define PIN_USBP_FAULT1   39  // /MCU_USBP_FAULT1 TPS2561 FAULT, R87 10k pull-up. Low = over-current
#define PIN_USBP_FAULT2   38  // /MCU_USBP_FAULT2 R88 10k pull-up. Low = over-current
#define PIN_GNSS_PPS       3  // /MCU_GNSS_PPS   via R40 1k, R94 4.7k pull-down

// ---- Display buttons J12: switch to GND, 10k pull-up, 1k + 100nF RC. Low = pressed ----
#define PIN_BTN_SCREEN    18  // /MCU_BTN_SCREEN J12.1
#define PIN_BTN_VOLUP     17  // /MCU_BTN_VOLUP  J12.2
#define PIN_BTN_VOLDN     22  // /MCU_BTN_VOLDN  J12.3
#define PIN_BTN_MUTE      16  // /MCU_BTN_MUTE   J12.4

// ---- Outputs ----
#define PIN_VIM3_PWR_EN   23  // /MCU_VIM3_PWR_EN R73 1k -> TPS55288 EN + USB module enable; R72 100k pull-down
#define PIN_PWR_KEY       15  // /MCU_PWR_KEY    R12 390R -> AQY210S U22 LED. High = VIM3 power key pressed
#define PIN_AMP_EN        20  // /MCU_AMP_EN     R16 -> Q3 2N7002 -> amp remote (ISO A3). R15 pull-down
#define PIN_BL_EN          0  // /MCU_BL_EN      R23 -> panel FPC pin 37. R96 100k pull-down
#define PIN_BL_PWM         1  // /MCU_BL_PWM     R24 -> panel FPC pin 36. Inverted: low = brightest
#define PIN_DAC_MUTE      10  // /MCU_DAC_MUTE   R46 1k -> DAC XSMT, R47 10k pull-down. High = play
#define PIN_HUB_RST        2  // /MCU_HUB_RST    R90 1k -> CH334R RESET#, R104 10k pull-up. Drive low only
#define PIN_GNSS_EN        9  // /MCU_GNSS_EN    LP5907 U6 enable, R35 100k pull-down
#define PIN_GNSS_RST       7  // /MCU_GNSS_RST   R39 1k -> NEO RESET_N. Drive low only
#define PIN_GNSS_SAFEBOOT  8  // /MCU_GNSS_SAFEBOOT R79 1k -> NEO SAFEBOOT_N. Drive low only
#define PIN_LED           21  // /MCU_LED        R86 1k -> D16 green. High = on

// ---- UART1 to the GNSS (NEO-M9N UART1) ----
#define PIN_GNSS_TX        4  // /MCU_GNSS_TX    R37 -> GNSS RXD only when JP2 is set to 2-3
#define PIN_GNSS_RX        5  // /MCU_GNSS_RX    R38 from GNSS TXD, R95 4.7k pull-down
#define GNSS_UART          uart1

// ---- I2C1: BH1750 (J7), TPS55288 (U12), audio module, expansion J21. 4.7k pull-ups ----
#define PIN_I2C_SDA       30  // /LUX_SDA
#define PIN_I2C_SCL       31  // /LUX_SCL
#define BOARD_I2C          i2c1
#define TPS55288_ADDR     0x74  // MODE pin R67 = 0 ohm
#define BH1750_ADDR_L     0x23
#define BH1750_ADDR_H     0x5C

// ---- ADC (RP2350B: GPIO40..47 are ADC0..7) ----
#define PIN_VBAT_ADC      40  // ADC0 /MCU_VBAT_ADC  R10 1M / R11 220k from VBAT_P
#define PIN_5VSYS_ADC     41  // ADC1 /MCU_5VSYS_ADC R91 10k / R92 10k from +5V_SYS
#define PIN_TEMP_ADC      42  // ADC2 /MCU_TEMP_ADC  R93 10k to 3.3V, TH1 NTC 10k B3950 to GND
#define ADC_CH_VBAT        0
#define ADC_CH_5VSYS       1
#define ADC_CH_TEMP        2

// ---- K-line module socket J10 (not used by this firmware yet) ----
#define PIN_KLINE_TX      32  // /EXP_GP32 UART0 TX
#define PIN_KLINE_RX      33  // /EXP_GP33 UART0 RX
#define PIN_KLINE_EN      28  // /EXP_GP28

// Pins with nothing on them or only on expansion headers (J21: GPIO24..27).
// RP2350-E9: these are parked as inputs with the input buffer off and no pulls.
#define UNUSED_PINS {11, 12, 13, 24, 25, 26, 27, 28, 29, 32, 33, 34, 44, 45, 46, 47}
