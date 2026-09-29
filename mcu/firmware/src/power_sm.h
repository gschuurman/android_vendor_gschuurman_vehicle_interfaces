// Vehicle power state machine: ACC line -> VIM3 power key presses.
//
// Hardware independent so it can be unit tested on the host. The caller feeds
// it debounced inputs every loop iteration and carries out the key press it
// asks for. Behaviour matches the MicroPython firmware (mcu/main.py) with one
// fix: ACC is handled as a level, not only as an edge, so an ACC drop that
// happens during the boot-grace or wake-settle window is acted on once the
// window closes instead of being lost.
#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef enum {
    PWR_STATE_OFF = 0,
    PWR_STATE_ON,
    PWR_STATE_SLEEP_PENDING,
} pwr_state_t;

typedef struct {
    uint32_t pwr_on_press_ms;   // power on from off
    uint32_t sleep_press_ms;    // short press: wake / request sleep
    uint32_t pwr_off_press_ms;  // long press: force power off
    uint32_t crank_ignore_ms;   // ACC dips shorter than this are ignored
    uint32_t wake_settle_ms;    // ignore ACC low right after a wake
    uint32_t boot_grace_ms;     // ignore ACC low right after MCU boot
    uint32_t full_off_delay_ms; // sleep -> forced power off
    bool boot_if_acc_high;
} pwr_config_t;

typedef struct {
    bool acc;       // debounced ACC
    bool sbc_power; // VIM3 3.3V rail present
    bool service;   // service jumper fitted: never press the key
} pwr_inputs_t;

typedef struct {
    pwr_config_t cfg;
    pwr_state_t state;
    uint32_t boot_ms;
    uint32_t ignore_acc_until_ms;
    bool crank_pending;
    uint32_t crank_deadline_ms;
    bool off_deadline_set;
    uint32_t off_deadline_ms;
    uint32_t state_since_ms;
} pwr_sm_t;

void pwr_default_config(pwr_config_t *cfg);
void pwr_init(pwr_sm_t *sm, const pwr_config_t *cfg, uint32_t now_ms, const pwr_inputs_t *in,
              uint32_t *press_ms);

// Advance the state machine. Sets *press_ms to a key press duration when the
// power key must be pressed now (0 = no press). The caller must not call
// pwr_step while a previous press is still in progress.
void pwr_step(pwr_sm_t *sm, uint32_t now_ms, const pwr_inputs_t *in, uint32_t *press_ms);

const char *pwr_state_name(pwr_state_t s);
