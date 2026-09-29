// Car radio peripheral controller for the Raspberry Pi Pico 2 (RP2350).
//
// Owns the vehicle-side I/O of the head unit and exposes it to Android over
// USB CDC (/dev/ttyACM*), using the line protocol in ../PROTOCOL.md. The VIM3
// power key stays a hardware signal because it must be able to wake the VIM3
// from suspend or power it on, when USB is not available.

#include <stdio.h>
#include <string.h>

#include "hardware/adc.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "hardware/pll.h"
#include "hardware/pwm.h"
#include "hardware/sync.h"
#include "hardware/watchdog.h"
#include "pico/bootrom.h"
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"

#include "board.h"
#include "device.h"
#include "power_sm.h"
#include "proto.h"

#define LOOP_MS             2
#define WATCHDOG_MS         2000
#define AMP_ON_DELAY_MS     2000  // let the head unit's audio settle before the amp turns on
#define LUX_PERIOD_MS       200
#define LUX_RETRY_MS        5000
#define VBAT_PERIOD_MS      500
#define IDLE_WAKE_MS        250

static device_t dev;
static pwr_sm_t pwr;

static uint32_t now_ms(void) { return to_ms_since_boot(get_absolute_time()); }

// ---------------------------------------------------------------- inputs

typedef struct {
    uint pin;
    uint32_t debounce_ms;
    bool stable;
    bool candidate;
    uint32_t since;
} debounced_t;

static debounced_t in_acc     = {PIN_ACC_IN, 80};
static debounced_t in_rev     = {PIN_REV_IN, 30};
static debounced_t in_illum   = {PIN_ILLUM_IN, 100};
static debounced_t in_park    = {PIN_PARK_IN, 100};
static debounced_t in_service = {PIN_SERVICE, 50};
static debounced_t in_sbc     = {PIN_SBC_SENSE, 50};
static debounced_t *const inputs[] = {&in_acc, &in_rev, &in_illum, &in_park, &in_service, &in_sbc};

static void input_seed(debounced_t *d, uint32_t now) {
    d->stable = d->candidate = gpio_get(d->pin);
    d->since = now;
}

static bool input_update(debounced_t *d, uint32_t now) {
    bool raw = gpio_get(d->pin);
    if (raw != d->candidate) {
        d->candidate = raw;
        d->since = now;
    } else if (raw != d->stable && (uint32_t)(now - d->since) >= d->debounce_ms) {
        d->stable = raw;
    }
    return d->stable;
}

// ---------------------------------------------------------------- power key

static bool press_active;
static uint32_t press_end_ms;

static void press_start(uint32_t ms, uint32_t now) {
    gpio_put(PIN_PWR_KEY, 1);
    press_active = true;
    press_end_ms = now + ms;
}

static void press_poll(uint32_t now) {
    if (press_active && (int32_t)(now - press_end_ms) >= 0) {
        gpio_put(PIN_PWR_KEY, 0);
        press_active = false;
    }
}

// ---------------------------------------------------------------- backlight

static uint bl_slice;
static uint32_t bl_top;
static uint32_t bl_freq_applied;

static void backlight_apply(bool on, uint16_t duty, uint32_t freq) {
    if (freq != bl_freq_applied) {
        uint32_t sys = clock_get_hz(clk_sys);
        uint32_t div = (sys / freq + 65535) / 65536;
        if (div < 1) div = 1;
        if (div > 255) div = 255;
        bl_top = sys / div / freq - 1;
        pwm_set_clkdiv_int_frac(bl_slice, (uint8_t)div, 0);
        pwm_set_wrap(bl_slice, (uint16_t)bl_top);
        bl_freq_applied = freq;
    }
    pwm_set_gpio_level(PIN_BL_PWM, on ? (uint16_t)((bl_top + 1) * duty / 1000) : 0);
    gpio_put(PIN_BL_EN, on);
}

// ---------------------------------------------------------------- BH1750

static bool lux_present;
static uint32_t lux_next_ms;

static bool bh1750_cmd(uint8_t cmd) {
    return i2c_write_timeout_us(LUX_I2C, BH1750_ADDR, &cmd, 1, false, 2000) == 1;
}

static void lux_poll(uint32_t now) {
    if ((int32_t)(now - lux_next_ms) < 0) return;
    if (!lux_present) {
        // Power on, continuous high-resolution mode (1 lx, 120 ms per sample).
        lux_present = bh1750_cmd(0x01) && bh1750_cmd(0x10);
        lux_next_ms = now + (lux_present ? LUX_PERIOD_MS : LUX_RETRY_MS);
        if (!lux_present) dev.lux = -1;
        return;
    }
    uint8_t buf[2];
    if (i2c_read_timeout_us(LUX_I2C, BH1750_ADDR, buf, 2, false, 2000) != 2) {
        lux_present = false;
        dev.lux = -1;
        lux_next_ms = now + LUX_RETRY_MS;
        return;
    }
    int32_t lux = ((int32_t)buf[0] << 8 | buf[1]) * 10 / 12;
    int32_t hyst = dev.lux / 10 > 2 ? dev.lux / 10 : 2;
    if (dev.lux < 0 || lux > dev.lux + hyst || lux < dev.lux - hyst) dev.lux = lux;
    lux_next_ms = now + LUX_PERIOD_MS;
}

// ---------------------------------------------------------------- battery

static uint32_t vbat_next_ms;

static void vbat_poll(uint32_t now) {
    if ((int32_t)(now - vbat_next_ms) < 0) return;
    vbat_next_ms = now + VBAT_PERIOD_MS;
    uint32_t sum = 0;
    for (int i = 0; i < 8; i++) sum += adc_read();
    int32_t pin_mv = (int32_t)(sum * 3300u / (4095u * 8u));
    int32_t mv = pin_mv * VBAT_DIVIDER_NUM / VBAT_DIVIDER_DEN + VBAT_DIODE_MV;
    if (mv - dev.vbat_mv >= 100 || dev.vbat_mv - mv >= 100) dev.vbat_mv = mv;
}

// ---------------------------------------------------------------- amplifier

static uint32_t amp_ready_since;
static bool amp_ready_prev;

static void amp_update(uint32_t now) {
    bool ready = dev.state == PWR_STATE_ON && dev.acc && dev.sbc_power;
    if (ready && !amp_ready_prev) amp_ready_since = now;
    amp_ready_prev = ready;

    bool on;
    switch (dev.amp_mode) {
    case AMP_MODE_ON: on = true; break; // Q2 is fed from ACC, so it is still off with ACC off
    case AMP_MODE_OFF: on = false; break;
    default: on = ready && (uint32_t)(now - amp_ready_since) >= AMP_ON_DELAY_MS; break;
    }
    dev.amp_out = on;
    gpio_put(PIN_AMP_EN, on);
}

// ---------------------------------------------------------------- USB

static char rx_line[128];
static size_t rx_len;
static bool rx_overflow;

static void usb_out(const char *line) {
    if (!stdio_usb_connected()) return;
    printf("%s\n", line);
}

static void usb_poll(uint32_t now) {
    int c;
    while ((c = getchar_timeout_us(0)) != PICO_ERROR_TIMEOUT) {
        if (c == '\n' || c == '\r') {
            if (rx_overflow) usb_out("ERR - line_too_long");
            else if (rx_len) { rx_line[rx_len] = '\0'; proto_handle_line(&dev, rx_line, now, usb_out); }
            rx_len = 0;
            rx_overflow = false;
        } else if (rx_len < sizeof(rx_line) - 1) {
            rx_line[rx_len++] = (char)c;
        } else {
            rx_overflow = true;
        }
    }
}

// ---------------------------------------------------------------- deep idle

// Car off, VIM3 off, USB unpowered: run from the 12 MHz crystal with both PLLs
// stopped and sleep in WFI until ACC comes on, reverse changes or USB power
// appears. Reverse is still mirrored to REV_OUT while idling.
static volatile bool idle_wake;
static void idle_gpio_irq(uint gpio, uint32_t events) { (void)gpio; (void)events; idle_wake = true; }
static int64_t idle_alarm(alarm_id_t id, void *user) { (void)id; (void)user; idle_wake = true; return 0; }

static bool idle_should_exit(bool rev_at_entry) {
    return gpio_get(PIN_ACC_IN) || gpio_get(PIN_VBUS_SENSE) || gpio_get(PIN_REV_IN) != rev_at_entry;
}

static void deep_idle(void) {
    bool rev = gpio_get(PIN_REV_IN);
    gpio_set_irq_enabled_with_callback(PIN_ACC_IN, GPIO_IRQ_EDGE_RISE, true, idle_gpio_irq);
    gpio_set_irq_enabled(PIN_VBUS_SENSE, GPIO_IRQ_EDGE_RISE, true);
    gpio_set_irq_enabled(PIN_REV_IN, GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, true);

    clock_configure(clk_sys, CLOCKS_CLK_SYS_CTRL_SRC_VALUE_CLK_REF, 0, XOSC_HZ, XOSC_HZ);
    clock_configure(clk_peri, 0, CLOCKS_CLK_PERI_CTRL_AUXSRC_VALUE_CLK_SYS, XOSC_HZ, XOSC_HZ);
    clock_stop(clk_usb);
    clock_stop(clk_adc);
    pll_deinit(pll_usb);

    while (!idle_should_exit(rev)) {
        idle_wake = false;
        alarm_id_t a = add_alarm_in_ms(IDLE_WAKE_MS, idle_alarm, NULL, true);
        while (!idle_wake) __wfi();
        cancel_alarm(a);
        watchdog_update();
    }

    pll_init(pll_usb, PLL_USB_REFDIV, PLL_USB_VCO_FREQ_HZ, PLL_USB_POSTDIV1, PLL_USB_POSTDIV2);
    clock_configure(clk_usb, 0, CLOCKS_CLK_USB_CTRL_AUXSRC_VALUE_CLKSRC_PLL_USB, USB_CLK_HZ, USB_CLK_HZ);
    clock_configure(clk_adc, 0, CLOCKS_CLK_ADC_CTRL_AUXSRC_VALUE_CLKSRC_PLL_USB, USB_CLK_HZ, USB_CLK_HZ);
    set_sys_clock_48mhz();

    gpio_set_irq_enabled(PIN_ACC_IN, GPIO_IRQ_EDGE_RISE, false);
    gpio_set_irq_enabled(PIN_VBUS_SENSE, GPIO_IRQ_EDGE_RISE, false);
    gpio_set_irq_enabled(PIN_REV_IN, GPIO_IRQ_EDGE_RISE | GPIO_IRQ_EDGE_FALL, false);
    gpio_put(PIN_REV_OUT, gpio_get(PIN_REV_IN));
}

// ---------------------------------------------------------------- setup

static void pin_in(uint pin) {
    gpio_init(pin);
    gpio_set_dir(pin, GPIO_IN);
    gpio_disable_pulls(pin); // the board has 4.7k pull-downs (RP2350-E9)
}

static void pin_out(uint pin) {
    gpio_init(pin);
    gpio_set_dir(pin, GPIO_OUT);
    gpio_put(pin, 0);
}

static void hw_init(void) {
    const uint ins[] = {PIN_ACC_IN, PIN_REV_IN, PIN_ILLUM_IN, PIN_PARK_IN, PIN_SERVICE, PIN_SBC_SENSE, PIN_VBUS_SENSE};
    for (size_t i = 0; i < sizeof(ins) / sizeof(ins[0]); i++) pin_in(ins[i]);
    const uint outs[] = {PIN_PWR_KEY, PIN_AMP_EN, PIN_BL_EN, PIN_REV_OUT, PIN_LED};
    for (size_t i = 0; i < sizeof(outs) / sizeof(outs[0]); i++) pin_out(outs[i]);

    gpio_set_function(PIN_BL_PWM, GPIO_FUNC_PWM);
    bl_slice = pwm_gpio_to_slice_num(PIN_BL_PWM);
    pwm_set_enabled(bl_slice, true);

    i2c_init(LUX_I2C, 100 * 1000);
    gpio_set_function(PIN_I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(PIN_I2C_SCL, GPIO_FUNC_I2C);

    adc_init();
    adc_gpio_init(PIN_VBAT_ADC);
    adc_select_input(ADC_CH_VBAT);
}

int main(void) {
    set_sys_clock_48mhz(); // enough for USB, saves power
    stdio_usb_init();
    hw_init();
    watchdog_enable(WATCHDOG_MS, true);

    uint32_t now = now_ms();
    device_defaults(&dev);
    for (size_t i = 0; i < sizeof(inputs) / sizeof(inputs[0]); i++) input_seed(inputs[i], now);
    vbat_poll(now);

    pwr_config_t cfg;
    pwr_default_config(&cfg);
    cfg.full_off_delay_ms = dev.off_delay_s * 1000u;
    pwr_inputs_t pin = {in_acc.stable, in_sbc.stable, in_service.stable};
    uint32_t press = 0;
    pwr_init(&pwr, &cfg, now, &pin, &press);
    if (press) press_start(press, now);

    device_t last = dev;
    bool was_connected = false;

    for (;;) {
        watchdog_update();
        now = now_ms();

        dev.acc = input_update(&in_acc, now);
        dev.reverse = input_update(&in_rev, now);
        dev.illum = input_update(&in_illum, now);
        dev.park = input_update(&in_park, now);
        dev.service = input_update(&in_service, now);
        dev.sbc_power = input_update(&in_sbc, now);
        gpio_put(PIN_REV_OUT, dev.reverse);

        pwr.cfg.full_off_delay_ms = dev.off_delay_s * 1000u;
        press_poll(now);
        if (!press_active) {
            pwr_inputs_t pi = {dev.acc, dev.sbc_power, dev.service};
            pwr_step(&pwr, now, &pi, &press);
            if (press) press_start(press, now);
            else if (dev.key_press_request_ms) press_start(dev.key_press_request_ms, now);
            dev.key_press_request_ms = 0;
        }
        dev.state = pwr.state;

        amp_update(now);
        backlight_apply(dev.bl_en && dev.state == PWR_STATE_ON && dev.sbc_power, dev.bl_duty, dev.bl_freq);
        if (dev.state != PWR_STATE_OFF) lux_poll(now);
        vbat_poll(now);
        gpio_put(PIN_LED, dev.state == PWR_STATE_ON && (now % 2000) < 100);

        bool connected = stdio_usb_connected();
        if (connected && !was_connected) {
            proto_hello(usb_out);
            last = dev;
        }
        was_connected = connected;
        usb_poll(now);
        if (connected) proto_emit_changes(&dev, &last, usb_out);
        else last = dev;

        if (dev.bootsel_request) {
            sleep_ms(50); // let the OK line reach the host
            reset_usb_boot(0, 0);
        }

        if (dev.state == PWR_STATE_OFF && !press_active && !gpio_get(PIN_VBUS_SENSE) && !dev.acc) {
            deep_idle();
            now = now_ms();
            for (size_t i = 0; i < sizeof(inputs) / sizeof(inputs[0]); i++) input_seed(inputs[i], now);
            // Force a real debounce of ACC after waking, like the MicroPython version.
            in_acc.stable = false;
        }

        sleep_ms(LOOP_MS);
    }
}
