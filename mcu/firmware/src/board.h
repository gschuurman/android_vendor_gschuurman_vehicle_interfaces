// Pin map for the car radio peripheral board rev 0.2 (Raspberry Pi Pico 2).
//
// All vehicle inputs arrive through EL817 optocouplers whose emitters drive the
// GPIO with a 4.7k pull-down on the board, so every input is active-high and
// the RP2350-E9 pull-down erratum does not apply.
#pragma once

// Vehicle inputs (opto, active-high)
#define PIN_ACC_IN        2
#define PIN_REV_IN        3
#define PIN_ILLUM_IN      6   // headlight / dash illumination wire
#define PIN_PARK_IN       7   // parking brake wire (optional on the loom)

// Light sensor (BH1750 on J7)
#define PIN_I2C_SDA       4
#define PIN_I2C_SCL       5
#define LUX_I2C           i2c0
#define BH1750_ADDR       0x23

// Outputs
#define PIN_PWR_KEY       8   // high = press the VIM3 POWER key (Q1 open drain)
#define PIN_AMP_EN        9   // high = +12V on the amplifier remote wire (Q3/Q2)
#define PIN_BL_EN         10  // display backlight enable
#define PIN_BL_PWM        11  // display backlight PWM (slice 5, channel B)
#define PIN_REV_OUT       12  // hardware copy of reverse to VIM3 header pin 32

// Other inputs
#define PIN_SBC_SENSE     13  // VIM3 3.3V rail present (1k + 4.7k divider)
#define PIN_SERVICE       14  // service jumper JP1 to 3.3V
#define PIN_VBUS_SENSE    24  // Pico 2 on-board VBUS detect (USB host powered)
#define PIN_LED           25  // Pico 2 on-board LED

// Battery voltage: GP26 / ADC0 through 1M / 220k after the reverse-polarity diode
#define PIN_VBAT_ADC      26
#define ADC_CH_VBAT       0
#define VBAT_DIVIDER_NUM  (1000 + 220)
#define VBAT_DIVIDER_DEN  220
#define VBAT_DIODE_MV     300 // SS34 drop at a few mA, added back to the reading
