#include "power_sm.h"

#include <stddef.h>

static bool reached(uint32_t now, uint32_t deadline) { return (int32_t)(now - deadline) >= 0; }
static uint32_t since(uint32_t now, uint32_t t) { return now - t; }

void pwr_default_config(pwr_config_t *c) {
    c->crank_ignore_ms = 2500;
    c->boot_key_after_ms = 4000;
    c->boot_timeout_ms = 90000;
    c->boot_attempts = 3;
    c->key_short_ms = 150;
    c->key_on_ms = 1000;
    c->sbc_off_confirm_ms = 2000;
    c->prep_timeout_ms = 5u * 60u * 1000u;
    c->suspend_detect_ms = 3000;
    c->off_delay_ms = 15u * 60u * 1000u;
    c->wake_retry_ms = 15000;
    c->wake_attempts = 3;
    c->wake_nolink_ms = 45000;
    c->shutdown_timeout_ms = 120000;
    c->cut_settle_ms = 3000;
}

static void set_state(pwr_sm_t *sm, mcu_power_state_t s) {
    if (sm->state == s) return;
    sm->state = s;
    sm->state_since = sm->now;
    sm->act.state_changed = true;
}

static void press(pwr_sm_t *sm, const pwr_inputs_t *in, uint32_t ms) {
    if (in->service) return;
    sm->act.key_press_ms = ms;
    sm->last_key = sm->now;
}

static void send_req(pwr_sm_t *sm, int32_t req, int32_t param) {
    sm->req = req;
    sm->req_param = param;
    sm->act.send_req = true;
    sm->act.req = req;
    sm->act.req_param = param;
}

// Cut the VIM3 supply and hold it off for cut_settle_ms.
static void cut_power(pwr_sm_t *sm, mcu_power_state_t next) {
    sm->act.power_en = false;
    sm->cut_holding = true;
    sm->cut_since = sm->now;
    sm->req = REQ_ON;
    sm->req_param = 0;
    set_state(sm, next);
}

static void enter_running(pwr_sm_t *sm) {
    sm->acc_low_pending = false;
    sm->sbc_low_pending = false;
    sm->boot_attempt = 0;
    set_state(sm, MCU_PWR_RUNNING);
}

static void request_sleep(pwr_sm_t *sm, const pwr_inputs_t *in, int32_t param) {
    if (in->link_up) {
        send_req(sm, REQ_SHUTDOWN_PREPARE, param);
    } else {
        // No VHAL link: old software. A short key press asks Android to sleep.
        sm->req = REQ_SHUTDOWN_PREPARE;
        sm->req_param = param;
        press(sm, in, sm->cfg.key_short_ms);
    }
    sm->prep_deadline = sm->now + sm->cfg.prep_timeout_ms;
    sm->suspend_pending = false;
    set_state(sm, MCU_PWR_SHUTDOWN_PREP);
}

static void start_wake(pwr_sm_t *sm, const pwr_inputs_t *in, bool for_shutdown) {
    sm->wake_for_shutdown = for_shutdown;
    sm->wake_attempt = 1;
    press(sm, in, sm->cfg.key_short_ms);
    set_state(sm, MCU_PWR_WAKING);
}

// Android is up and asks what to do (WAIT_FOR_VHAL, DEEP_SLEEP_EXIT, ON, link back).
static void answer_android(pwr_sm_t *sm, const pwr_inputs_t *in) {
    if (in->acc || in->service) {
        send_req(sm, REQ_ON, 0);
        enter_running(sm);
    } else {
        int32_t param = (sm->state == MCU_PWR_WAKING && sm->wake_for_shutdown) ? PARAM_SHUTDOWN_ONLY
                                                                               : PARAM_CAN_SLEEP;
        request_sleep(sm, in, param);
    }
}

void pwr_init(pwr_sm_t *sm, const pwr_config_t *cfg, uint32_t now, const pwr_inputs_t *in,
              bool en_kept) {
    *sm = (pwr_sm_t){0};
    sm->cfg = *cfg;
    sm->now = now;
    sm->state_since = now;
    sm->req = REQ_ON;
    sm->state = MCU_PWR_OFF;
    if (en_kept && in->sbc_on) {
        // MCU restarted under a running VIM3 (watchdog, firmware update). Carry on;
        // the crank logic in RUNNING handles ACC being off.
        sm->act.power_en = true;
        sm->state = MCU_PWR_RUNNING;
    }
    sm->act.state_changed = true;
}

void pwr_on_report(pwr_sm_t *sm, int32_t report, int32_t param, const pwr_inputs_t *in) {
    (void)param;
    switch (report) {
    case REP_ON:
        // Android reached ON (after our REQ_ON): nothing to answer.
        if (sm->state == MCU_PWR_WAKING || sm->state == MCU_PWR_BOOTING) enter_running(sm);
        break;
    case REP_WAIT_FOR_VHAL:
    case REP_DEEP_SLEEP_EXIT:
    case REP_HIBERNATION_EXIT:
    case REP_SHUTDOWN_CANCELLED:
        if (sm->state == MCU_PWR_BOOTING || sm->state == MCU_PWR_WAKING ||
            sm->state == MCU_PWR_RUNNING || sm->state == MCU_PWR_SUSPENDED ||
            sm->state == MCU_PWR_SHUTDOWN_PREP) {
            if (sm->state == MCU_PWR_SUSPENDED) set_state(sm, MCU_PWR_WAKING);
            // In SHUTDOWN_PREP with ACC still off this repeats the sleep request.
            if (sm->state == MCU_PWR_SHUTDOWN_PREP && !in->acc && !in->service &&
                report != REP_SHUTDOWN_CANCELLED) {
                send_req(sm, REQ_SHUTDOWN_PREPARE, sm->req_param);
            } else {
                answer_android(sm, in);
            }
        }
        break;
    case REP_DEEP_SLEEP_ENTRY:
    case REP_HIBERNATION_ENTRY:
        if (sm->state == MCU_PWR_SHUTDOWN_PREP || sm->state == MCU_PWR_RUNNING) {
            sm->suspend_since = sm->now;
            set_state(sm, MCU_PWR_SUSPENDED);
        }
        break;
    case REP_SHUTDOWN_POSTPONE:
        if (sm->state == MCU_PWR_SHUTDOWN_PREP)
            sm->prep_deadline = sm->now + sm->cfg.prep_timeout_ms;
        break;
    case REP_SHUTDOWN_START:
        if (sm->state != MCU_PWR_OFF && sm->state != MCU_PWR_LATCHED_OFF)
            set_state(sm, MCU_PWR_SHUTTING_DOWN);
        break;
    default:
        break;
    }
}

pwr_actions_t pwr_step(pwr_sm_t *sm, uint32_t now, const pwr_inputs_t *in) {
    sm->now = now;
    const pwr_config_t *c = &sm->cfg;

    // VIM3 rail low for sbc_off_confirm_ms?
    bool sbc_off = false;
    if (in->sbc_on) {
        sm->sbc_low_pending = false;
    } else if (!sm->sbc_low_pending) {
        sm->sbc_low_pending = true;
        sm->sbc_low_since = now;
    } else {
        sbc_off = since(now, sm->sbc_low_since) >= c->sbc_off_confirm_ms;
    }

    if (sm->cut_holding && since(now, sm->cut_since) >= c->cut_settle_ms) sm->cut_holding = false;

    switch (sm->state) {
    case MCU_PWR_OFF:
        sm->act.power_en = false;
        if ((in->acc || in->service) && !sm->cut_holding) {
            sm->act.power_en = true;
            sm->boot_key_pressed = false;
            sm->boot_attempt++;
            set_state(sm, MCU_PWR_BOOTING);
        }
        break;

    case MCU_PWR_BOOTING:
        if (in->sbc_on) {
            enter_running(sm);
            // Android asks with WAIT_FOR_VHAL once the VHAL is up; answer_android replies.
        } else if (!in->acc && !in->service) {
            // ACC went away before the VIM3 came up: nothing to save yet.
            cut_power(sm, MCU_PWR_OFF);
            sm->boot_attempt = 0;
        } else if (!sm->boot_key_pressed && since(now, sm->state_since) >= c->boot_key_after_ms) {
            // VIM3 not set to start on power: press its key.
            sm->boot_key_pressed = true;
            press(sm, in, c->key_on_ms);
        } else if (since(now, sm->state_since) >= c->boot_timeout_ms) {
            cut_power(sm, sm->boot_attempt >= c->boot_attempts ? MCU_PWR_LATCHED_OFF : MCU_PWR_OFF);
        }
        break;

    case MCU_PWR_RUNNING:
        sm->act.power_en = true;
        if (sbc_off && !in->service) {
            // Android shut down by itself (power menu) or crashed off.
            cut_power(sm, in->acc ? MCU_PWR_LATCHED_OFF : MCU_PWR_OFF);
            break;
        }
        if (in->acc || in->service) {
            sm->acc_low_pending = false;
            break;
        }
        if (!sm->acc_low_pending) {
            sm->acc_low_pending = true;
            sm->acc_low_since = now;
        } else if (since(now, sm->acc_low_since) >= c->crank_ignore_ms) {
            sm->acc_low_pending = false;
            request_sleep(sm, in, PARAM_CAN_SLEEP);
        }
        break;

    case MCU_PWR_SHUTDOWN_PREP:
        if (sbc_off) {
            cut_power(sm, in->acc ? MCU_PWR_LATCHED_OFF : MCU_PWR_OFF);
            break;
        }
        if ((in->acc || in->service) && sm->req_param == PARAM_CAN_SLEEP) {
            // ACC back while Android prepares for sleep.
            if (in->link_up) {
                send_req(sm, REQ_CANCEL_SHUTDOWN, 0);
                // Android answers with SHUTDOWN_CANCELLED (or WAIT_FOR_VHAL); see pwr_on_report.
                // Until then count as running so a second ACC drop starts over.
                sm->req = REQ_ON;
                enter_running(sm);
            } else {
                press(sm, in, c->key_short_ms);
                sm->req = REQ_ON;
                enter_running(sm);
            }
            break;
        }
        if (in->link_up && !sm->link_was_up && !in->acc && !in->service) {
            // The sleep request went out as a key press, or the link dropped: repeat it.
            send_req(sm, REQ_SHUTDOWN_PREPARE, sm->req_param);
        }
        if (!in->link_up && in->usb_suspended) {
            if (!sm->suspend_pending) {
                sm->suspend_pending = true;
                sm->suspend_since = now;
            } else if (since(now, sm->suspend_since) >= c->suspend_detect_ms) {
                sm->suspend_since = now;
                set_state(sm, MCU_PWR_SUSPENDED);
                break;
            }
        } else {
            sm->suspend_pending = false;
        }
        if (reached(now, sm->prep_deadline)) {
            cut_power(sm, in->acc ? MCU_PWR_LATCHED_OFF : MCU_PWR_OFF);
        }
        break;

    case MCU_PWR_SUSPENDED:
        if (sbc_off) {
            cut_power(sm, MCU_PWR_OFF);
            break;
        }
        if (in->acc) {
            start_wake(sm, in, false);
        } else if (!in->service &&
                   ((c->off_delay_ms && since(now, sm->suspend_since) >= c->off_delay_ms) ||
                    in->low_battery)) {
            start_wake(sm, in, true);
        }
        break;

    case MCU_PWR_WAKING:
        if (sbc_off) {
            cut_power(sm, in->acc ? MCU_PWR_LATCHED_OFF : MCU_PWR_OFF);
            break;
        }
        if (in->link_up && !sm->link_was_up) {
            // VHAL back after resume: tell Android what we want right away.
            answer_android(sm, in);
            break;
        }
        if (in->usb_suspended && since(now, sm->last_key) >= c->wake_retry_ms) {
            if (sm->wake_attempt < c->wake_attempts) {
                sm->wake_attempt++;
                press(sm, in, c->key_short_ms);
            } else if (sm->wake_for_shutdown || !in->acc) {
                cut_power(sm, MCU_PWR_OFF);  // will not wake; nothing left to save
            }
            break;
        }
        if (!in->usb_suspended && !in->link_up && since(now, sm->state_since) >= c->wake_nolink_ms) {
            // Awake but no VHAL link (old software): run on, or cut when shutting down.
            if (in->acc && !sm->wake_for_shutdown) enter_running(sm);
            else cut_power(sm, MCU_PWR_OFF);
        }
        break;

    case MCU_PWR_SHUTTING_DOWN:
        if (sbc_off || since(now, sm->state_since) >= c->shutdown_timeout_ms) {
            // If ACC is on again, OFF powers straight back up after the settle time.
            cut_power(sm, MCU_PWR_OFF);
        }
        break;

    case MCU_PWR_LATCHED_OFF:
        sm->act.power_en = false;
        if (!in->acc && !in->service) {
            sm->boot_attempt = 0;
            set_state(sm, MCU_PWR_OFF);
        }
        break;
    }

    sm->link_was_up = in->link_up;

    pwr_actions_t out = sm->act;
    sm->act.key_press_ms = 0;
    sm->act.send_req = false;
    sm->act.state_changed = false;
    return out;
}

bool pwr_audio_allowed(const pwr_sm_t *sm) { return sm->state == MCU_PWR_RUNNING; }

bool pwr_display_allowed(const pwr_sm_t *sm) {
    switch (sm->state) {
    case MCU_PWR_BOOTING:
    case MCU_PWR_RUNNING:
    case MCU_PWR_SHUTDOWN_PREP:
    case MCU_PWR_WAKING:
        return true;
    default:
        return false;
    }
}

const char *pwr_state_name(mcu_power_state_t s) {
    switch (s) {
    case MCU_PWR_OFF: return "off";
    case MCU_PWR_BOOTING: return "booting";
    case MCU_PWR_RUNNING: return "running";
    case MCU_PWR_SHUTDOWN_PREP: return "shutdown_prep";
    case MCU_PWR_SUSPENDED: return "suspended";
    case MCU_PWR_WAKING: return "waking";
    case MCU_PWR_SHUTTING_DOWN: return "shutting_down";
    case MCU_PWR_LATCHED_OFF: return "latched_off";
    }
    return "?";
}
