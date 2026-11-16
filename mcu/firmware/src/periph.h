// I2C parts on the board bus (I2C1): TPS55288 VIM3 supply and BH1750 light sensor.
#pragma once
#include <stdbool.h>
#include <stdint.h>

void periph_i2c_init(void);

// TPS55288 (U12) at 0x74. Defaults from the MODE pin and the power-on registers give
// 5.0 V with the 5 A current limit; the firmware only switches the output (MODE.OE).
#define TPS_REG_MODE 0x06
#define TPS_REG_STATUS 0x07
#define TPS_MODE_OE 0x80
// MODE register (datasheet SLVSF01B table 7-10): bit 3 VCC (0 internal LDO), bit 2 I2CADD
// (0 = 0x74), bit 1 PFM (0 PFM, 1 FPWM at light load), bit 0 MODE (1 = VCC/I2CADD/PFM from
// these bits instead of the MODE pin). The board's MODE pin (R67 0R) selects internal VCC,
// 0x74 and FPWM.
#define TPS_MODE_LIGHTLOAD_MASK 0x0F
#define TPS_MODE_REG_PFM 0x01   // register control, internal VCC, 0x74, PFM
#define TPS_MODE_REG_FPWM 0x03  // register control, internal VCC, 0x74, FPWM
#define TPS_STATUS_SCP 0x80
#define TPS_STATUS_OCP 0x40
#define TPS_STATUS_OVP 0x20

bool tps_read(uint8_t reg, uint8_t *val);
bool tps_write(uint8_t reg, uint8_t val);
// Set or clear the output-enable bit. Returns true when the read-back matches.
bool tps_set_output(bool on);
// Returns true if the output-enable bit is set (false also when it does not answer).
bool tps_output_enabled(void);
// Light-load mode: PFM (true) or forced PWM (false), keeping address, VCC and OE.
bool tps_set_pfm(bool pfm);

// BH1750 (J7). Returns the I2C address found, or 0.
uint8_t bh1750_probe(void);
// Continuous high-resolution mode, a new value every 120 ms. Returns lux or -1.
int32_t bh1750_read(uint8_t addr);
