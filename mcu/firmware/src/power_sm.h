// Power state machine: car ACC line -> VIM3 supply, power key and AAOS power requests.
//
// Hardware independent so it builds and runs in the host tests (test/test_power_sm.c).
// The caller feeds it debounced inputs and Android's AP_POWER_STATE_REPORT values,
// and carries out the actions it returns.
//
// How a drive cycle goes:
//   OFF -> ACC on -> BOOTING: VIM3 supply on (TPS55288), power key if the VIM3 does not
//   start by itself -> RUNNING once the VIM3 3.3V rail is up.
//   ACC off for longer than the crank window -> SHUTDOWN_PREP: AP_POWER_STATE_REQ
//   SHUTDOWN_PREPARE/CAN_SLEEP over USB (or a short key press if the VHAL link is down).
//   Android reports DEEP_SLEEP_ENTRY -> SUSPENDED (supply stays on, VIM3 in RAM).
//   ACC on again -> key press wakes the VIM3 (GPIOAO_7 is its wakeup source) -> WAKING
//   -> AP_POWER_STATE_REQ ON once the VHAL is back -> RUNNING.
//   Off delay expired or battery low -> key press -> WAKING -> SHUTDOWN_PREPARE/
//   SHUTDOWN_ONLY -> Android reports SHUTDOWN_START -> SHUTTING_DOWN -> supply cut when
//   the VIM3 rail drops -> OFF.
#pragma once
#include <stdbool.h>
#include <stdint.h>

#include "mcu_protocol.h"

// VehicleApPowerStateReq / Report / ShutdownParam values (VHAL AIDL).
enum { REQ_ON = 0, REQ_SHUTDOWN_PREPARE = 1, REQ_CANCEL_SHUTDOWN = 2, REQ_FINISHED = 3 };
enum {
    REP_WAIT_FOR_VHAL = 1, REP_DEEP_SLEEP_ENTRY = 2, REP_DEEP_SLEEP_EXIT = 3,
    REP_SHUTDOWN_POSTPONE = 4, REP_SHUTDOWN_START = 5, REP_ON = 6, REP_SHUTDOWN_PREPARE = 7,
    REP_SHUTDOWN_CANCELLED = 8, REP_HIBERNATION_ENTRY = 9, REP_HIBERNATION_EXIT = 10,
};
enum { PARAM_CAN_SLEEP = 2, PARAM_SHUTDOWN_ONLY = 3 };

typedef struct {
    uint32_t crank_ignore_ms;     // ACC dips shorter than this are ignored (starter motor)
    uint32_t boot_key_after_ms;   // press the key if the VIM3 rail is not up by then
    uint32_t boot_timeout_ms;     // give up on a boot attempt, cut power and retry
    uint32_t boot_attempts;       // attempts before latching off until ACC cycles
    uint32_t key_short_ms;        // wake / sleep press
    uint32_t key_on_ms;           // power-on press
    uint32_t sbc_off_confirm_ms;  // VIM3 rail must stay low this long to count as off
    uint32_t prep_timeout_ms;     // SHUTDOWN_PREP without suspend or shutdown -> cut
    uint32_t suspend_detect_ms;   // no VHAL link and USB suspended this long = suspended
    uint32_t off_delay_ms;        // SUSPENDED -> full shutdown (0 = never)
    uint32_t wake_retry_ms;       // re-press the key while waking
    uint32_t wake_attempts;
    uint32_t wake_nolink_ms;      // VIM3 awake but no VHAL link: assume legacy software
    uint32_t shutdown_timeout_ms; // SHUTTING_DOWN -> cut even if the rail stays up
    uint32_t cut_settle_ms;       // supply stays off at least this long
} pwr_config_t;

typedef struct {
    bool acc;           // debounced ACC
    bool sbc_on;        // VIM3 3.3V rail (debounced)
    bool service;       // service jumper: keep the VIM3 on, never cut or press
    bool link_up;       // VHAL heartbeat seen recently
    bool usb_suspended; // USB bus suspended by the host
    bool low_battery;   // battery low for long enough to act on
} pwr_inputs_t;

typedef struct {
    bool power_en;        // VIM3 supply (TPS55288) should be on
    uint32_t key_press_ms;// one-shot: press the power key for this long (0 = none)
    bool send_req;        // one-shot: send AP_POWER_STATE_REQ {req, req_param}
    int32_t req, req_param;
    bool state_changed;
} pwr_actions_t;

typedef struct {
    pwr_config_t cfg;
    mcu_power_state_t state;
    uint32_t state_since;
    uint32_t now;
    // ACC-low tracking in RUNNING (crank window)
    bool acc_low_pending;
    uint32_t acc_low_since;
    // rail-low tracking
    bool sbc_low_pending;
    uint32_t sbc_low_since;
    // boot
    uint32_t boot_attempt;
    bool boot_key_pressed;
    uint32_t cut_since;
    bool cut_holding;
    // shutdown prep / suspend
    uint32_t prep_deadline;
    uint32_t suspend_since;
    bool suspend_pending;
    // waking
    bool wake_for_shutdown;
    uint32_t wake_attempt;
    uint32_t last_key;
    // last request sent to Android
    int32_t req, req_param;
    bool link_was_up;
    pwr_actions_t act;
} pwr_sm_t;

void pwr_default_config(pwr_config_t *cfg);

// en_kept: the VIM3 supply survived the MCU reset (R72 pull-up and output still on).
void pwr_init(pwr_sm_t *sm, const pwr_config_t *cfg, uint32_t now, const pwr_inputs_t *in,
              bool en_kept);

// Run once per main-loop pass. Returns the actions to carry out now.
pwr_actions_t pwr_step(pwr_sm_t *sm, uint32_t now, const pwr_inputs_t *in);

// Android's AP_POWER_STATE_REPORT, forwarded by the VHAL. Call before pwr_step.
void pwr_on_report(pwr_sm_t *sm, int32_t report, int32_t param, const pwr_inputs_t *in);

// True while audio may play (DAC unmuted, amp on in auto mode).
bool pwr_audio_allowed(const pwr_sm_t *sm);
// True while the backlight may be on.
bool pwr_display_allowed(const pwr_sm_t *sm);

const char *pwr_state_name(mcu_power_state_t s);
