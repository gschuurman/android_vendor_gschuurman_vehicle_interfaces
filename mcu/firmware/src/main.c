// Car radio peripheral board firmware (RP2350B, board rev 0.6).
//
// Owns the car-side I/O and the VIM3's power, and talks to the VHAL over USB HID
// (see ../../protocol/mcu_protocol.h and ../README.md).
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "board.h"
#include "hardware/adc.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/irq.h"
#include "hardware/pwm.h"
#include "hardware/uart.h"
#include "hardware/watchdog.h"
#include "mcu_protocol.h"
#include "nmea.h"
#include "periph.h"
#include "pico/bootrom.h"
#include "pico/stdlib.h"
#include "kline_sm.h"
#include "power_sm.h"
#include "usb_link.h"

#define FW_MAJOR 0
#define FW_MINOR 2
#define FW_PATCH 3

#define BL_PWM_HZ 32768u        // same period (30518 ns) the VHAL used on the VIM3 PWM
#define LOW_BATT_MV 12200       // shut down from suspend below this (~50% charge at rest: the car must still start)...
#define LOW_BATT_HOLD_MS 60000  // ...for this long
#define SUSPEND_SAVE_AFTER_MS 10000 // MCU_SAVE_* this long into a suspend (Android done suspending)
#define HOT_DECI_C 850          // MCU_ST_HOT above 85 degC
#define AMP_AFTER_DAC_MS 500
#define DAC_AFTER_AMP_MS 150

_Static_assert(NUM_BANK0_GPIOS == 48, "build for the RP2350B (48 GPIOs)");

static const uint32_t gnss_bauds[] = {38400, 9600, 115200, 230400};

// ---------------------------------------------------------------- debounce

typedef struct {
    uint8_t pin;
    bool active_low;
    uint16_t debounce_ms;
    bool stable;
    bool candidate;
    uint32_t since;
} din_t;

static bool din_raw(const din_t *d) {
    bool v = gpio_get(d->pin);
    return d->active_low ? !v : v;
}

static void din_seed(din_t *d, uint32_t now) {
    d->stable = d->candidate = din_raw(d);
    d->since = now;
}

// Returns true when the stable value changed.
static bool din_update(din_t *d, uint32_t now) {
    bool raw = din_raw(d);
    if (raw == d->stable) {
        d->candidate = raw;
        d->since = now;
        return false;
    }
    if (raw != d->candidate) {
        d->candidate = raw;
        d->since = now;
        return false;
    }
    if (now - d->since >= d->debounce_ms) {
        d->stable = raw;
        return true;
    }
    return false;
}

enum { IN_ACC, IN_REV, IN_ILLUM, IN_PARK, IN_SBC, IN_SERVICE, IN_BTN_SCREEN, IN_BTN_VOLUP,
       IN_BTN_VOLDN, IN_BTN_MUTE, IN_COUNT };

static din_t inputs[IN_COUNT] = {
    [IN_ACC] = {PIN_ACC_IN, false, 80},
    [IN_REV] = {PIN_REV_IN, false, 40},
    [IN_ILLUM] = {PIN_ILLUM_IN, false, 300},
    [IN_PARK] = {PIN_PARK_IN, false, 300},
    [IN_SBC] = {PIN_SBC_SENSE, false, 100},
    [IN_SERVICE] = {PIN_SERVICE, false, 200},
    [IN_BTN_SCREEN] = {PIN_BTN_SCREEN, true, 30},
    [IN_BTN_VOLUP] = {PIN_BTN_VOLUP, true, 30},
    [IN_BTN_VOLDN] = {PIN_BTN_VOLDN, true, 30},
    [IN_BTN_MUTE] = {PIN_BTN_MUTE, true, 30},
};

static uint32_t input_bits(void) {
    static const uint32_t bit[IN_COUNT] = {
        [IN_ACC] = MCU_IN_ACC, [IN_REV] = MCU_IN_REVERSE, [IN_ILLUM] = MCU_IN_ILLUM,
        [IN_PARK] = MCU_IN_HANDBRAKE, [IN_SBC] = MCU_IN_SBC_ON, [IN_SERVICE] = MCU_IN_SERVICE,
        [IN_BTN_SCREEN] = MCU_IN_BTN_SCREEN, [IN_BTN_VOLUP] = MCU_IN_BTN_VOLUP,
        [IN_BTN_VOLDN] = MCU_IN_BTN_VOLDN, [IN_BTN_MUTE] = MCU_IN_BTN_MUTE,
    };
    uint32_t b = 0;
    for (int i = 0; i < IN_COUNT; i++)
        if (inputs[i].stable) b |= bit[i];
    return b;
}

// ---------------------------------------------------------------- state

static pwr_sm_t psm;
static uint32_t now_ms;
static uint8_t reset_reason;
static bool en_pullup;        // R72 fitted as a pull-up: VIM3 supply survives MCU resets

// Host-controlled settings
static int32_t brightness = 50;     // 0..100
static bool screen_on = true;
static int32_t amp_mode = 2;        // 0 off, 1 on, 2 auto
// Audio mute from the VHAL. Starts muted and falls back to muted whenever the link drops or
// a new drive starts: only the VHAL releases it, once Android's audio output runs (the DACs
// are clocked). The DACs float without their clocks and the amp would amplify that.
static bool host_mute = true;
static uint32_t suspend_save;       // MCU_SAVE_*, set by the VHAL (default off)
static uint32_t off_delay_s = 12 * 3600;  // suspend -> full off; the low battery guard ends it earlier

// Outputs as driven
static bool supply_on;
static bool tps_ok;               // TPS55288 output enable confirmed
static uint32_t tps_retry_at;
static bool amp_on;
static bool dac_unmuted;
static uint32_t dac_changed_at, amp_changed_at;
static bool link_was_up;
static bool display_on;
static bool gnss_powered;
static bool gnss_safeboot;
static uint32_t gnss_cmd_until;   // supply forced off / reset held until
static int gnss_cmd;
static uint32_t key_release_at;
static bool key_down;

// Measurements
static int32_t vbat_mv = -1, rail_mv = -1, temp_dc = INT32_MIN, lux = -1;
static int32_t sent_vbat = INT32_MIN, sent_rail = INT32_MIN, sent_temp = INT32_MIN, sent_lux = INT32_MIN;
static uint32_t low_batt_since;
static bool low_batt;
static uint8_t bh_addr;
static uint32_t bh_next;
static uint8_t tps_status;

// GNSS
static nmea_t nmea;
static volatile uint8_t gnss_rx[512];
static volatile uint16_t gnss_head, gnss_tail;
static int gnss_baud_idx;
static uint32_t gnss_last_good, gnss_baud_since;
static float sent_speed = -1.0f;
static int32_t sent_fix = -1;

static uint32_t sent_inputs = 0xFFFFFFFF, sent_status = 0xFFFFFFFF;

// ---------------------------------------------------------------- pins

static void park_unused(uint pin) {
    // RP2350-E9: no internal pull-down on undriven pins; input buffer off.
    gpio_init(pin);
    gpio_disable_pulls(pin);
    gpio_set_input_enabled(pin, false);
}

static void out_init(uint pin, bool value) {
    gpio_init(pin);
    gpio_disable_pulls(pin);
    gpio_put(pin, value);
    gpio_set_dir(pin, GPIO_OUT);
}

static void in_init(uint pin) {
    gpio_init(pin);
    gpio_disable_pulls(pin);  // every input has an external pull resistor
    gpio_set_input_enabled(pin, true);
}

// "Drive low only" pins (hub reset, GNSS reset/safeboot): low or released.
static void od_set(uint pin, bool low) {
    if (low) {
        gpio_put(pin, 0);
        gpio_set_dir(pin, GPIO_OUT);
    } else {
        gpio_set_dir(pin, GPIO_IN);
    }
}

static void od_init(uint pin) {
    gpio_init(pin);
    gpio_disable_pulls(pin);
    gpio_set_input_enabled(pin, false);  // never read (RP2350-E9)
    od_set(pin, false);
}

static void gnss_uart_irq(void) {
    while (uart_is_readable(GNSS_UART)) {
        uint8_t c = (uint8_t)uart_getc(GNSS_UART);
        uint16_t next = (uint16_t)((gnss_head + 1) % sizeof(gnss_rx));
        if (next != gnss_tail) {
            gnss_rx[gnss_head] = c;
            gnss_head = next;
        }
    }
}

// GNSS PPS: the NEO-M9N timepulse (1 Hz, rising edge at the top of the UTC second) on
// PIN_GNSS_PPS. The edge is timestamped here and reported by the main loop.
static volatile bool pps_flag;
static volatile uint32_t pps_count;
static volatile uint64_t pps_edge_us;

static void gpio_edge_irq(uint gpio, uint32_t events) {
    if (gpio == PIN_GNSS_PPS && (events & GPIO_IRQ_EDGE_RISE)) {
        pps_edge_us = time_us_64();
        pps_count++;
        pps_flag = true;
    }
}

uint64_t app_time_us(void) { return time_us_64(); }

// ---------------------------------------------------------------- K-line (MEMS 1.9)

static kl_sm_t ksm;
static int32_t kline_mode = 1;  // MCU_PROP_KLINE_MODE: 0 off, 1 auto
static volatile uint8_t kline_rx[128];
static volatile uint8_t kline_head, kline_tail;
static bool kline_uart_fn;      // TX pin currently on the UART

static void kline_uart_irq(void) {
    while (uart_is_readable(KLINE_UART)) {
        uint8_t c = (uint8_t)uart_getc(KLINE_UART);
        uint8_t next = (uint8_t)((kline_head + 1) % sizeof(kline_rx));
        if (next != kline_tail) {
            kline_rx[kline_head] = c;
            kline_head = next;
        }
    }
}

static void kline_init(void) {
    out_init(PIN_KLINE_EN, 0);
    out_init(PIN_KLINE_TX, 1);  // idle high (recessive) while driven as a GPIO
    gpio_set_drive_strength(PIN_KLINE_TX, GPIO_DRIVE_STRENGTH_4MA);
    uart_init(KLINE_UART, 9600);
    uart_set_format(KLINE_UART, 8, 1, UART_PARITY_NONE);
    uart_set_fifo_enabled(KLINE_UART, true);
    gpio_set_function(PIN_KLINE_RX, GPIO_FUNC_UART);
    gpio_pull_up(PIN_KLINE_RX);  // RX floats while the module is absent
    irq_set_exclusive_handler(UART0_IRQ, kline_uart_irq);
    irq_set_enabled(UART0_IRQ, true);
    uart_set_irq_enables(KLINE_UART, true, false);
    kl_init(&ksm, to_ms_since_boot(get_absolute_time()));
}

static void kline_task(void) {
    while (kline_tail != kline_head) {
        uint8_t c = kline_rx[kline_tail];
        kline_tail = (uint8_t)((kline_tail + 1) % sizeof(kline_rx));
        kl_rx(&ksm, c, now_ms);
    }
    kl_inputs_t in = {.acc = inputs[IN_ACC].stable, .enabled = kline_mode != 0};
    kl_actions_t a = kl_step(&ksm, now_ms, &in);

    gpio_put(PIN_KLINE_EN, a.power);
    if (a.uart != kline_uart_fn) {
        // UART for 9600 baud traffic, plain GPIO for the 5-baud address
        if (!a.uart) uart_tx_wait_blocking(KLINE_UART);  // last byte fully shifted out
        gpio_set_function(PIN_KLINE_TX, a.uart ? GPIO_FUNC_UART : GPIO_FUNC_SIO);
        kline_uart_fn = a.uart;
    }
    if (!a.uart) gpio_put(PIN_KLINE_TX, a.power ? a.line_high : true);
    if (a.flush_rx) {
        while (uart_is_readable(KLINE_UART)) (void)uart_getc(KLINE_UART);
        kline_tail = kline_head;
    }
    if (a.tx >= 0) uart_putc_raw(KLINE_UART, (char)a.tx);
    if (a.frame) usb_link_send_kline(MCU_KLINE_ECU_MEMS19, a.frame_data, a.frame_len, now_ms);
    if (a.state_changed) {
        usb_link_send_prop(MCU_PROP_KLINE_STATE, kl_public_state(&ksm), (int32_t)ksm.ecu_id);
        // Only with the link up: while the VIM3 sleeps the retries would fill the log queue.
        if (usb_link_up()) usb_link_log("kline state %d", kl_public_state(&ksm));
    }
}

static void pps_task(void) {
    if (!pps_flag) return;
    uint32_t irq = save_and_disable_interrupts();
    uint32_t count = pps_count;
    uint64_t edge = pps_edge_us;
    pps_flag = false;
    restore_interrupts(irq);
    usb_link_send_pps(count, edge);
}

static void board_init(void) {
    // VIM3 supply enable first. With R72 as a pull-up the pin reads high here and the
    // TPS55288 kept running through this reset, so keep driving it high.
    gpio_init(PIN_VIM3_PWR_EN);
    gpio_disable_pulls(PIN_VIM3_PWR_EN);
    gpio_set_input_enabled(PIN_VIM3_PWR_EN, true);
    busy_wait_us(50);
    en_pullup = gpio_get(PIN_VIM3_PWR_EN);
    gpio_put(PIN_VIM3_PWR_EN, en_pullup);
    gpio_set_dir(PIN_VIM3_PWR_EN, GPIO_OUT);
    gpio_set_input_enabled(PIN_VIM3_PWR_EN, false);

    out_init(PIN_PWR_KEY, 0);
    gpio_set_drive_strength(PIN_PWR_KEY, GPIO_DRIVE_STRENGTH_8MA);
    out_init(PIN_AMP_EN, 0);
    out_init(PIN_BL_EN, 0);
    out_init(PIN_BL_PWM, 0);
    out_init(PIN_DAC_MUTE, 0);
    out_init(PIN_GNSS_EN, 0);
    out_init(PIN_LED, 0);
    od_init(PIN_HUB_RST);
    od_init(PIN_GNSS_RST);
    od_init(PIN_GNSS_SAFEBOOT);

    for (int i = 0; i < IN_COUNT; i++) in_init(inputs[i].pin);
    in_init(PIN_USBP_PG);
    in_init(PIN_USBP_FAULT1);
    in_init(PIN_USBP_FAULT2);
    in_init(PIN_GNSS_PPS);
    gpio_set_irq_enabled_with_callback(PIN_GNSS_PPS, GPIO_IRQ_EDGE_RISE, true, &gpio_edge_irq);

    static const uint8_t unused[] = UNUSED_PINS;
    for (unsigned i = 0; i < sizeof(unused); i++) park_unused(unused[i]);
    // GNSS TX: the MCU never transmits (JP2 normally gives the GNSS RX to the VIM3).
    park_unused(PIN_GNSS_TX);

    adc_init();
    adc_gpio_init(PIN_VBAT_ADC);
    adc_gpio_init(PIN_5VSYS_ADC);
    adc_gpio_init(PIN_TEMP_ADC);

    periph_i2c_init();
    kline_init();

    // GNSS UART RX only.
    uart_init(GNSS_UART, gnss_bauds[0]);
    gpio_set_function(PIN_GNSS_RX, GPIO_FUNC_UART);
    gpio_disable_pulls(PIN_GNSS_RX);  // R95 4.7k pull-down holds it when the GNSS is off
    uart_set_fifo_enabled(GNSS_UART, true);
    irq_set_exclusive_handler(UART1_IRQ, gnss_uart_irq);
    irq_set_enabled(UART1_IRQ, true);
    uart_set_irq_enables(GNSS_UART, true, false);
}

// ---------------------------------------------------------------- outputs

static void set_supply(bool on) {
    if (on == supply_on) return;
    supply_on = on;
    if (on) {
        gpio_put(PIN_VIM3_PWR_EN, 1);
        od_set(PIN_HUB_RST, false);
        tps_ok = false;
        tps_retry_at = now_ms + 3;  // TPS55288 needs ~1 ms after EN before I2C
    } else {
        tps_set_output(false);
        gpio_put(PIN_VIM3_PWR_EN, 0);
        od_set(PIN_HUB_RST, true);  // hub off the unpowered VIM3, lower parked current
        tps_ok = false;
    }
}

// Extra savings in suspend, each enabled by the VHAL (MCU_PROP_SUSPEND_SAVE, default off)
// so it can be validated on the car and switched off without a reflash. They start
// SUSPEND_SAVE_AFTER_MS into a suspend and are undone in the same step that leaves
// SUSPENDED (and presses the power key to wake the VIM3):
// - MCU_SAVE_HUB_PARK: hub 1 (CH334R: this MCU's own USB, the touch controller, the GNSS
//   module and hub 2 with the phone ports) is held in reset, as while the VIM3 is
//   unpowered. Released before the VIM3 resumes, so the MCU link comes back, which is how
//   WAKING sees that the wake worked.
// - MCU_SAVE_TPS_PFM: the TPS55288 runs PFM at light load instead of the forced PWM of
//   its MODE pin (FPWM keeps the switching noise out of the audio while playing).
static bool hub_parked;
static bool tps_pfm;
static uint8_t tps_mode = 0xFF;  // last MODE register read

static bool suspend_saving(uint32_t bit) {
    return (suspend_save & bit) && psm.state == MCU_PWR_SUSPENDED &&
           now_ms - psm.state_since >= SUSPEND_SAVE_AFTER_MS;
}

static void apply_hub(void) {
    bool park = !supply_on || suspend_saving(MCU_SAVE_HUB_PARK);
    if (park == hub_parked) return;
    hub_parked = park;
    od_set(PIN_HUB_RST, park);
    if (supply_on) usb_link_log("hub 1 %s", park ? "parked (suspend)" : "released");
}

static void apply_tps_mode(void) {
    if (!supply_on || !tps_ok) {
        tps_pfm = false;  // the MODE pin applies again after EN
        return;
    }
    bool pfm = suspend_saving(MCU_SAVE_TPS_PFM);
    if (pfm == tps_pfm) return;
    if (tps_set_pfm(pfm)) {
        tps_pfm = pfm;
        usb_link_log("TPS55288 %s", pfm ? "PFM (suspend)" : "forced PWM");
    }
}

static void service_supply(void) {
    if (!supply_on || tps_ok || (int32_t)(now_ms - tps_retry_at) < 0) return;
    tps_ok = tps_set_output(true);
    if (!tps_ok) tps_retry_at = now_ms + 100;
    else usb_link_log("vim3 supply on");
}

static void backlight_init(void) {
    gpio_set_function(PIN_BL_PWM, GPIO_FUNC_PWM);
    uint slice = pwm_gpio_to_slice_num(PIN_BL_PWM);
    pwm_config cfg = pwm_get_default_config();
    uint32_t wrap = clock_get_hz(clk_sys) / BL_PWM_HZ - 1;
    pwm_config_set_wrap(&cfg, (uint16_t)wrap);
    pwm_init(slice, &cfg, true);
}

static void apply_display(bool allowed) {
    bool on = allowed && screen_on;
    if (on) {
        if (!display_on) {
            gpio_set_function(PIN_BL_PWM, GPIO_FUNC_PWM);
        }
        uint slice = pwm_gpio_to_slice_num(PIN_BL_PWM);
        uint32_t top = pwm_hw->slice[slice].top + 1;
        // Waveshare panel: inverted PWM, 0 V is brightest.
        uint32_t level = top * (uint32_t)(100 - brightness) / 100u;
        pwm_set_gpio_level(PIN_BL_PWM, (uint16_t)level);
        gpio_put(PIN_BL_EN, 1);
    } else {
        gpio_put(PIN_BL_EN, 0);
        if (display_on) {
            // Panel may be unpowered: do not drive its PWM input high.
            gpio_init(PIN_BL_PWM);
            gpio_disable_pulls(PIN_BL_PWM);
            gpio_put(PIN_BL_PWM, 0);
            gpio_set_dir(PIN_BL_PWM, GPIO_OUT);
        }
    }
    display_on = on;
}

static void set_host_mute(void) {
    if (host_mute) return;
    host_mute = true;
    usb_link_send_prop(MCU_PROP_AUDIO_MUTE, host_mute, 0);
}

static void apply_audio(void) {
    bool allowed = pwr_audio_allowed(&psm);
    bool dac_want = allowed && usb_link_up() && !host_mute;
    bool amp_want;
    switch (amp_mode) {
    case 0: amp_want = false; break;
    case 1: amp_want = supply_on; break;
    default: amp_want = allowed && dac_unmuted && now_ms - dac_changed_at >= AMP_AFTER_DAC_MS; break;
    }
    if (amp_mode == 2 && !dac_want) amp_want = false;

    if (amp_on && !amp_want) {
        amp_on = false;
        amp_changed_at = now_ms;
        gpio_put(PIN_AMP_EN, 0);
    } else if (!amp_on && amp_want) {
        amp_on = true;
        amp_changed_at = now_ms;
        gpio_put(PIN_AMP_EN, 1);
    }
    // Mute the DACs only once the amp has been off a moment (no pop).
    if (dac_unmuted && !dac_want && (!amp_on || amp_mode == 1) && now_ms - amp_changed_at >= DAC_AFTER_AMP_MS) {
        dac_unmuted = false;
        dac_changed_at = now_ms;
        gpio_put(PIN_DAC_MUTE, 0);
    } else if (!dac_unmuted && dac_want) {
        dac_unmuted = true;
        dac_changed_at = now_ms;
        gpio_put(PIN_DAC_MUTE, 1);
    }
}

static void apply_gnss(void) {
    bool want = supply_on && psm.state != MCU_PWR_SUSPENDED;
    bool forced_off = gnss_cmd != 0 && (int32_t)(now_ms - gnss_cmd_until) < 0 &&
                      gnss_cmd != MCU_GNSS_CMD_RESET;
    if (gnss_cmd == MCU_GNSS_CMD_RESET) od_set(PIN_GNSS_RST, (int32_t)(now_ms - gnss_cmd_until) < 0);
    if (gnss_cmd && (int32_t)(now_ms - gnss_cmd_until) >= 0) gnss_cmd = 0;
    od_set(PIN_GNSS_SAFEBOOT, gnss_safeboot);
    bool on = want && !forced_off;
    if (on != gnss_powered) {
        gnss_powered = on;
        gpio_put(PIN_GNSS_EN, on);
        gnss_baud_since = now_ms;
    }
}

static void gnss_command(int cmd) {
    switch (cmd) {
    case MCU_GNSS_CMD_RESET: gnss_cmd_until = now_ms + 100; break;
    case MCU_GNSS_CMD_POWER_CYCLE: gnss_cmd_until = now_ms + 1000; break;
    case MCU_GNSS_CMD_SAFEBOOT: gnss_safeboot = true; gnss_cmd_until = now_ms + 1000; break;
    case MCU_GNSS_CMD_NORMAL: gnss_safeboot = false; gnss_cmd_until = now_ms + 1000; break;
    default: return;
    }
    gnss_cmd = cmd;
}

static void led_task(void) {
    uint32_t t = now_ms;
    bool on;
    switch (psm.state) {
    case MCU_PWR_OFF: on = (t % 4000) < 20; break;
    case MCU_PWR_BOOTING: on = (t % 500) < 250; break;
    case MCU_PWR_RUNNING: on = usb_link_up() ? true : (t % 1000) < 500; break;
    case MCU_PWR_SUSPENDED: on = (t % 2000) < 20; break;
    case MCU_PWR_LATCHED_OFF: on = (t % 2000) < 20 || ((t % 2000) >= 200 && (t % 2000) < 220); break;
    default: on = (t % 200) < 100; break;
    }
    gpio_put(PIN_LED, on);
}

// ---------------------------------------------------------------- measurements

static float adc_volts(uint ch) {
    adc_select_input(ch);
    uint32_t sum = 0;
    for (int i = 0; i < 16; i++) sum += adc_read();
    return (float)sum / 16.0f * 3.3f / 4096.0f;
}

static void measure(void) {
    static uint32_t next;
    if ((int32_t)(now_ms - next) < 0) return;
    next = now_ms + 100;

    float vb = adc_volts(ADC_CH_VBAT) * (1000.0f + 220.0f) / 220.0f;  // R10 1M / R11 220k
    float v5 = adc_volts(ADC_CH_5VSYS) * 2.0f;                         // R91 / R92 10k
    float vt = adc_volts(ADC_CH_TEMP);
    vbat_mv = vbat_mv < 0 ? (int32_t)(vb * 1000) : (vbat_mv * 3 + (int32_t)(vb * 1000)) / 4;
    rail_mv = rail_mv < 0 ? (int32_t)(v5 * 1000) : (rail_mv * 3 + (int32_t)(v5 * 1000)) / 4;
    if (vt > 0.05f && vt < 3.25f) {
        float r = 10000.0f * vt / (3.3f - vt);  // NTC to GND, R93 10k to 3.3V
        float tk = 1.0f / (1.0f / 298.15f + logf(r / 10000.0f) / 3950.0f);
        temp_dc = (int32_t)lroundf((tk - 273.15f) * 10.0f);
    } else {
        temp_dc = INT32_MIN;
    }

    // Low battery: only acted on while the VIM3 sleeps (see power_sm).
    bool low = vbat_mv > 5000 && vbat_mv < LOW_BATT_MV && !inputs[IN_ACC].stable;
    if (!low) low_batt_since = now_ms;
    low_batt = low && now_ms - low_batt_since >= LOW_BATT_HOLD_MS;

    static uint32_t tps_next;
    if (supply_on && tps_ok && (int32_t)(now_ms - tps_next) >= 0) {
        tps_next = now_ms + 1000;
        uint8_t st;
        if (tps_read(TPS_REG_STATUS, &st)) tps_status = st;
        if (tps_read(TPS_REG_MODE, &st)) tps_mode = st;
    }
}

static void lux_task(void) {
    if ((int32_t)(now_ms - bh_next) < 0) return;
    if (!bh_addr) {
        bh_addr = bh1750_probe();
        bh_next = now_ms + (bh_addr ? 200 : 5000);
        if (!bh_addr) lux = -1;
        return;
    }
    int32_t v = bh1750_read(bh_addr);
    if (v < 0) {
        bh_addr = 0;
        lux = -1;
        bh_next = now_ms + 1000;
        return;
    }
    lux = lux < 0 ? v : (lux * 3 + v) / 4;
    bh_next = now_ms + 200;
}

static void gnss_task(void) {
    while (gnss_tail != gnss_head) {
        char c = (char)gnss_rx[gnss_tail];
        gnss_tail = (uint16_t)((gnss_tail + 1) % sizeof(gnss_rx));
        if (nmea_feed(&nmea, c)) gnss_last_good = now_ms;
    }
    // Autobaud: the NEO-M9N UART1 default is 38400, but the GNSS HAL may have changed it.
    if (gnss_powered && now_ms - gnss_last_good > 3000 && now_ms - gnss_baud_since > 3000) {
        gnss_baud_idx = (gnss_baud_idx + 1) % (int)(sizeof(gnss_bauds) / sizeof(gnss_bauds[0]));
        uart_set_baudrate(GNSS_UART, gnss_bauds[gnss_baud_idx]);
        gnss_baud_since = now_ms;
    }
}

static bool gnss_nmea_ok(void) { return gnss_powered && now_ms - gnss_last_good < 3000; }

static uint32_t status_bits(void) {
    uint32_t s = 0;
    if (gpio_get(PIN_USBP_PG)) s |= MCU_ST_USBP_PG;
    if (!gpio_get(PIN_USBP_FAULT1)) s |= MCU_ST_USBP_FAULT1;
    if (!gpio_get(PIN_USBP_FAULT2)) s |= MCU_ST_USBP_FAULT2;
    if (tps_ok) s |= MCU_ST_BB_PRESENT;
    if (tps_status & TPS_STATUS_SCP) s |= MCU_ST_BB_SCP;
    if (tps_status & TPS_STATUS_OCP) s |= MCU_ST_BB_OCP;
    if (tps_status & TPS_STATUS_OVP) s |= MCU_ST_BB_OVP;
    if (bh_addr) s |= MCU_ST_LUX_PRESENT;
    if (gnss_powered) s |= MCU_ST_GNSS_POWER;
    if (gnss_nmea_ok()) s |= MCU_ST_GNSS_NMEA;
    if (en_pullup) s |= MCU_ST_EN_PULLUP;
    if (low_batt) s |= MCU_ST_LOW_BATTERY;
    if (temp_dc != INT32_MIN && temp_dc > HOT_DECI_C) s |= MCU_ST_HOT;
    if (dac_unmuted) s |= MCU_ST_DAC_UNMUTED;
    return s;
}

// ---------------------------------------------------------------- reporting

static int32_t abs32(int32_t v) { return v < 0 ? -v : v; }

static void report_changes(bool force) {
    uint32_t in = input_bits();
    if (force || in != sent_inputs) {
        uint32_t changed = in ^ sent_inputs;
        if (force || (changed & MCU_IN_ACC))
            usb_link_send_prop(MCU_PROP_IGNITION_STATE, (in & MCU_IN_ACC) ? 4 /* ON */ : 2 /* OFF */, 0);
        if (force || (changed & MCU_IN_REVERSE))
            usb_link_send_prop(MCU_PROP_GEAR_SELECTION, (in & MCU_IN_REVERSE) ? 0x2 : 0x4, 0);
        if (force || (changed & MCU_IN_ILLUM))
            usb_link_send_prop(MCU_PROP_NIGHT_MODE, (in & MCU_IN_ILLUM) ? 1 : 0, 0);
        usb_link_send_prop(MCU_PROP_INPUTS, (int32_t)in, 0);
        sent_inputs = in;
    }
    uint32_t st = status_bits();
    if (force || st != sent_status) {
        usb_link_send_prop(MCU_PROP_STATUS, (int32_t)st, 0);
        sent_status = st;
    }
    if (force || abs32(vbat_mv - sent_vbat) >= 100) {
        usb_link_send_prop(MCU_PROP_BATTERY_MV, vbat_mv, 0);
        sent_vbat = vbat_mv;
    }
    if (force || abs32(rail_mv - sent_rail) >= 50) {
        usb_link_send_prop(MCU_PROP_RAIL_5V_MV, rail_mv, 0);
        sent_rail = rail_mv;
    }
    if (force || (temp_dc != sent_temp && (temp_dc == INT32_MIN || sent_temp == INT32_MIN ||
                                           abs32(temp_dc - sent_temp) >= 5))) {
        usb_link_send_prop(MCU_PROP_BOARD_TEMP, temp_dc, 0);
        sent_temp = temp_dc;
    }
    int32_t lux_step = sent_lux > 40 ? sent_lux / 20 : 2;
    if (force || (lux != sent_lux && (lux < 0 || sent_lux < 0 || abs32(lux - sent_lux) >= lux_step))) {
        usb_link_send_prop(MCU_PROP_LUX, lux, 0);
        sent_lux = lux;
    }
    float speed = (gnss_nmea_ok() && nmea.rmc_valid) ? nmea.speed_mps : 0.0f;
    if (speed < 0.3f) speed = 0.0f;  // GNSS jitter while parked
    if (force || fabsf(speed - sent_speed) >= 0.1f) {
        usb_link_send_float(MCU_PROP_PERF_VEHICLE_SPEED, speed);
        sent_speed = speed;
    }
    int32_t fix = gnss_nmea_ok() ? (nmea.fix_quality > 0) : 0;
    int32_t sats = gnss_nmea_ok() ? nmea.satellites : 0;
    if (force || ((fix << 8) | sats) != sent_fix) {
        usb_link_send_prop(MCU_PROP_GNSS_FIX, fix, sats);
        sent_fix = (fix << 8) | sats;
    }
    static int sent_tps_mode = -1;
    if (force || sent_tps_mode != tps_mode) {
        usb_link_send_prop(MCU_PROP_TPS_MODE, tps_mode, 0);
        sent_tps_mode = tps_mode;
    }
    static int sent_amp = -1;
    if (force || sent_amp != (int)amp_on) {
        usb_link_send_prop(MCU_PROP_AMP_ON, amp_on, 0);
        sent_amp = amp_on;
    }
    if (force) {
        usb_link_send_prop(MCU_PROP_AP_POWER_STATE_REQ, psm.req, psm.req_param);
        usb_link_send_prop(MCU_PROP_POWER_STATE, psm.state, 0);
        usb_link_send_prop(MCU_PROP_SCREEN_POWER, screen_on, 0);
        usb_link_send_prop(MCU_PROP_DISPLAY_BRIGHTNESS, brightness, 0);
        usb_link_send_prop(MCU_PROP_AMP_MODE, amp_mode, 0);
        usb_link_send_prop(MCU_PROP_AUDIO_MUTE, host_mute, 0);
        usb_link_send_prop(MCU_PROP_OFF_DELAY_S, (int32_t)off_delay_s, 0);
        usb_link_send_prop(MCU_PROP_SUSPEND_SAVE, (int32_t)suspend_save, 0);
    }
}

void app_on_snapshot_request(void) {
    report_changes(true);
    usb_link_send_prop(MCU_PROP_KLINE_STATE, kl_public_state(&ksm), (int32_t)ksm.ecu_id);
    usb_link_send_prop(MCU_PROP_KLINE_MODE, kline_mode, 0);
}

void app_fill_info(void *p) {
    mcu_info_msg_t *info = p;
    info->fw_major = FW_MAJOR;
    info->fw_minor = FW_MINOR;
    info->fw_patch = FW_PATCH;
    info->reset_reason = reset_reason;
    info->board_rev = BOARD_REV;
    info->flags = en_pullup ? MCU_INFO_FLAG_EN_PULLUP : 0;
    info->uptime_s = now_ms / 1000;
    snprintf(info->build, sizeof(info->build), "%s %s", __DATE__, __TIME__);
}

// Power-relevant input edges, for the sleep/wake post-mortem after the link returns.
static void log_power_inputs(const pwr_inputs_t *in) {
    static bool init;
    static pwr_inputs_t last;
    if (init && in->acc == last.acc && in->sbc_on == last.sbc_on && in->service == last.service &&
        in->usb_suspended == last.usb_suspended && in->low_battery == last.low_battery) {
        return;
    }
    init = true;
    last = *in;
    usb_link_log("t%lu in acc %d vim3 %d svc %d usbsusp %d lowbat %d vbat %ld",
                 (unsigned long)(now_ms / 1000), in->acc, in->sbc_on, in->service,
                 in->usb_suspended, in->low_battery, (long)vbat_mv);
}

static int32_t pending_report = -1, pending_report_param;

void app_on_host_set(uint32_t prop, int32_t v0, int32_t v1) {
    switch (prop) {
    case MCU_PROP_DISPLAY_BRIGHTNESS:
        brightness = v0 < 0 ? 0 : v0 > 100 ? 100 : v0;
        usb_link_send_prop(MCU_PROP_DISPLAY_BRIGHTNESS, brightness, 0);
        break;
    case MCU_PROP_SCREEN_POWER:
        screen_on = v0 != 0;
        usb_link_send_prop(MCU_PROP_SCREEN_POWER, screen_on, 0);
        break;
    case MCU_PROP_AP_POWER_STATE_REPORT:
        pending_report = v0;   // handled in the main loop, before pwr_step
        pending_report_param = v1;
        break;
    case MCU_PROP_AMP_MODE:
        if (v0 >= 0 && v0 <= 2) amp_mode = v0;
        usb_link_send_prop(MCU_PROP_AMP_MODE, amp_mode, 0);
        break;
    case MCU_PROP_AUDIO_MUTE:
        host_mute = v0 != 0;
        usb_link_send_prop(MCU_PROP_AUDIO_MUTE, host_mute, 0);
        break;
    case MCU_PROP_OFF_DELAY_S:
        if (v0 >= 0 && v0 <= 7 * 24 * 3600) {
            off_delay_s = (uint32_t)v0;
            psm.cfg.off_delay_ms = off_delay_s * 1000u;
        }
        usb_link_send_prop(MCU_PROP_OFF_DELAY_S, (int32_t)off_delay_s, 0);
        break;
    case MCU_PROP_GNSS_CMD:
        gnss_command(v0);
        break;
    case MCU_PROP_KLINE_MODE:
        if (v0 == 0 || v0 == 1) kline_mode = v0;
        usb_link_send_prop(MCU_PROP_KLINE_MODE, kline_mode, 0);
        break;
    case MCU_PROP_KLINE_CMD:
        if (v0 == MCU_KLINE_CMD_CLEAR_FAULTS) kl_request_clear_faults(&ksm);
        break;
    case MCU_PROP_SUSPEND_SAVE:
        suspend_save = (uint32_t)v0 & (MCU_SAVE_HUB_PARK | MCU_SAVE_TPS_PFM);
        usb_link_send_prop(MCU_PROP_SUSPEND_SAVE, (int32_t)suspend_save, 0);
        break;
    default:
        usb_link_log("unknown prop 0x%08lx", (unsigned long)prop);
        break;
    }
}

static bool bootsel_requested;
void app_on_bootsel_request(void) { bootsel_requested = true; }

// ---------------------------------------------------------------- buttons

static void buttons(bool changed[IN_COUNT]) {
    // Volume and mute: HID consumer keys while held; Android repeats held keys itself.
    if (changed[IN_BTN_VOLUP] || changed[IN_BTN_VOLDN] || changed[IN_BTN_MUTE]) {
        uint16_t usage = 0;
        if (inputs[IN_BTN_VOLUP].stable) usage = 0x00E9;
        else if (inputs[IN_BTN_VOLDN].stable) usage = 0x00EA;
        else if (inputs[IN_BTN_MUTE].stable) usage = 0x00E2;
        usb_link_consumer_key(usage);
    }
    // Screen button: toggle the backlight here, tell the VHAL.
    if (changed[IN_BTN_SCREEN] && inputs[IN_BTN_SCREEN].stable && pwr_display_allowed(&psm)) {
        screen_on = !screen_on;
        usb_link_send_prop(MCU_PROP_SCREEN_POWER, screen_on, 0);
    }
}

// ---------------------------------------------------------------- main

int main(void) {
    reset_reason = watchdog_caused_reboot() ? MCU_RESET_WATCHDOG : MCU_RESET_POWER_ON;
    board_init();
    backlight_init();
    apply_display(false);
    nmea_init(&nmea);

    now_ms = to_ms_since_boot(get_absolute_time());
    for (int i = 0; i < IN_COUNT; i++) din_seed(&inputs[i], now_ms);

    // Did the VIM3 supply survive this reset (R72 pull-up, TPS55288 still enabled)?
    bool en_kept = en_pullup && tps_output_enabled();
    pwr_config_t cfg;
    pwr_default_config(&cfg);
    cfg.off_delay_ms = off_delay_s * 1000u;
    pwr_inputs_t pin = {
        .acc = inputs[IN_ACC].stable,
        .sbc_on = inputs[IN_SBC].stable,
        .service = inputs[IN_SERVICE].stable,
    };
    pwr_init(&psm, &cfg, now_ms, &pin, en_kept);
    if (en_kept) {
        supply_on = true;
        tps_ok = true;
        od_set(PIN_HUB_RST, false);
    } else {
        gpio_put(PIN_VIM3_PWR_EN, 0);
        od_set(PIN_HUB_RST, true);
    }

    usb_link_init();
    watchdog_enable(2000, true);

    uint32_t last_loop_ms = now_ms;
    while (true) {
        watchdog_update();
        now_ms = to_ms_since_boot(get_absolute_time());
        pps_task();
        usb_link_task(now_ms);

        bool changed[IN_COUNT];
        for (int i = 0; i < IN_COUNT; i++) changed[i] = din_update(&inputs[i], now_ms);
        buttons(changed);
        measure();
        lux_task();
        gnss_task();
        kline_task();

        bool link = usb_link_up();
        pwr_inputs_t in = {
            .acc = inputs[IN_ACC].stable,
            .sbc_on = inputs[IN_SBC].stable,
            .service = inputs[IN_SERVICE].stable,
            .link_up = link,
            .usb_suspended = usb_link_suspended(),
            .low_battery = low_batt,
        };
        if (pending_report >= 0) {
            pwr_on_report(&psm, pending_report, pending_report_param, &in);
            pending_report = -1;
        }
        log_power_inputs(&in);
        mcu_power_state_t before = psm.state;
        pwr_actions_t act = pwr_step(&psm, now_ms, &in);

        if (psm.state == MCU_PWR_RUNNING && before != MCU_PWR_RUNNING) {
            set_host_mute();
            screen_on = true;  // every drive starts with the screen on
            usb_link_send_prop(MCU_PROP_SCREEN_POWER, screen_on, 0);
        }
        if (link != link_was_up) {
            link_was_up = link;
            if (!link) set_host_mute();  // the VHAL must release it again after reconnecting
        }

        set_supply(act.power_en);
        service_supply();
        apply_hub();
        apply_tps_mode();
        if (act.key_press_ms && !key_down) {
            key_down = true;
            key_release_at = now_ms + act.key_press_ms;
            gpio_put(PIN_PWR_KEY, 1);
            usb_link_log("t%lu power key %lu ms", (unsigned long)(now_ms / 1000),
                         (unsigned long)act.key_press_ms);
        }
        if (key_down && (int32_t)(now_ms - key_release_at) >= 0) {
            key_down = false;
            gpio_put(PIN_PWR_KEY, 0);
        }
        if (act.send_req) usb_link_send_prop(MCU_PROP_AP_POWER_STATE_REQ, act.req, act.req_param);
        if (act.state_changed) {
            usb_link_send_prop(MCU_PROP_POWER_STATE, psm.state, 0);
            usb_link_log("t%lu power %s vbat %ld", (unsigned long)(now_ms / 1000), pwr_state_name(psm.state),
                         (long)vbat_mv);
        }

        apply_display(pwr_display_allowed(&psm) && supply_on);
        apply_audio();
        apply_gnss();
        led_task();
        report_changes(false);

        if (bootsel_requested) {
            // With R72 as a pull-down this also cuts the VIM3 supply (see README).
            gpio_put(PIN_AMP_EN, 0);
            gpio_put(PIN_DAC_MUTE, 0);
            sleep_ms(50);
            rom_reset_usb_boot_extra(-1, 0, false);
        }

        // Nothing urgent: idle until the next millisecond (the USB IRQ wakes us earlier).
        if (now_ms == last_loop_ms) best_effort_wfe_or_timeout(make_timeout_time_us(500));
        last_loop_ms = now_ms;
    }
}
