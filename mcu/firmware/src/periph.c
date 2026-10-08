#include "periph.h"

#include "board.h"
#include "hardware/gpio.h"
#include "hardware/i2c.h"

#define I2C_TIMEOUT_US 5000

void periph_i2c_init(void) {
    i2c_init(BOARD_I2C, 100 * 1000);
    gpio_set_function(PIN_I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(PIN_I2C_SCL, GPIO_FUNC_I2C);
    // External 4.7k pull-ups (R33, R34); no internal pulls.
    gpio_disable_pulls(PIN_I2C_SDA);
    gpio_disable_pulls(PIN_I2C_SCL);
}

bool tps_read(uint8_t reg, uint8_t *val) {
    if (i2c_write_timeout_us(BOARD_I2C, TPS55288_ADDR, &reg, 1, true, I2C_TIMEOUT_US) != 1) return false;
    return i2c_read_timeout_us(BOARD_I2C, TPS55288_ADDR, val, 1, false, I2C_TIMEOUT_US) == 1;
}

bool tps_write(uint8_t reg, uint8_t val) {
    uint8_t buf[2] = {reg, val};
    return i2c_write_timeout_us(BOARD_I2C, TPS55288_ADDR, buf, 2, false, I2C_TIMEOUT_US) == 2;
}

bool tps_set_output(bool on) {
    uint8_t mode;
    if (!tps_read(TPS_REG_MODE, &mode)) return false;
    uint8_t want = on ? (mode | TPS_MODE_OE) : (mode & (uint8_t)~TPS_MODE_OE);
    if (want != mode && !tps_write(TPS_REG_MODE, want)) return false;
    uint8_t check;
    return tps_read(TPS_REG_MODE, &check) && check == want;
}

bool tps_output_enabled(void) {
    uint8_t mode;
    return tps_read(TPS_REG_MODE, &mode) && (mode & TPS_MODE_OE);
}

static bool bh1750_cmd(uint8_t addr, uint8_t cmd) {
    return i2c_write_timeout_us(BOARD_I2C, addr, &cmd, 1, false, I2C_TIMEOUT_US) == 1;
}

uint8_t bh1750_probe(void) {
    const uint8_t addrs[] = {BH1750_ADDR_L, BH1750_ADDR_H};
    for (unsigned i = 0; i < sizeof(addrs); i++) {
        // Power on, then continuous high-resolution mode.
        if (bh1750_cmd(addrs[i], 0x01) && bh1750_cmd(addrs[i], 0x10)) return addrs[i];
    }
    return 0;
}

int32_t bh1750_read(uint8_t addr) {
    uint8_t b[2];
    if (i2c_read_timeout_us(BOARD_I2C, addr, b, 2, false, I2C_TIMEOUT_US) != 2) return -1;
    uint32_t raw = ((uint32_t)b[0] << 8) | b[1];
    return (int32_t)((raw * 10u + 6u) / 12u);  // lux = raw / 1.2
}
