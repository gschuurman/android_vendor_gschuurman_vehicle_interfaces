#include "power_sm.h"

static bool reached(uint32_t now, uint32_t deadline) {
    return (int32_t)(now - deadline) >= 0;
}

void pwr_default_config(pwr_config_t *cfg) {
    cfg->pwr_on_press_ms = 1000;
    cfg->sleep_press_ms = 120;
    cfg->pwr_off_press_ms = 3000;
    cfg->crank_ignore_ms = 2500;
    cfg->wake_settle_ms = 1000;
    cfg->boot_grace_ms = 10000;
    cfg->full_off_delay_ms = 15u * 60u * 1000u;
    cfg->boot_if_acc_high = true;
}

static void set_state(pwr_sm_t *sm, pwr_state_t s, uint32_t now) {
    if (sm->state != s) sm->state_since_ms = now;
    sm->state = s;
}

static void wake_or_power_on(pwr_sm_t *sm, uint32_t now, const pwr_inputs_t *in, uint32_t *press) {
    if (in->service) return;
    sm->off_deadline_set = false;
    sm->crank_pending = false;
    *press = in->sbc_power ? sm->cfg.sleep_press_ms : sm->cfg.pwr_on_press_ms;
    set_state(sm, PWR_STATE_ON, now);
    sm->ignore_acc_until_ms = now + sm->cfg.wake_settle_ms;
}

void pwr_init(pwr_sm_t *sm, const pwr_config_t *cfg, uint32_t now, const pwr_inputs_t *in,
              uint32_t *press) {
    *press = 0;
    sm->cfg = *cfg;
    sm->state = PWR_STATE_OFF;
    sm->state_since_ms = now;
    sm->boot_ms = now;
    sm->ignore_acc_until_ms = now;
    sm->crank_pending = false;
    sm->off_deadline_set = false;

    if (sm->cfg.boot_if_acc_high && in->acc) {
        wake_or_power_on(sm, now, in, press);
    } else if (in->sbc_power) {
        // MCU restarted while the VIM3 was already running with ACC low.
        set_state(sm, PWR_STATE_SLEEP_PENDING, now);
        sm->off_deadline_set = true;
        sm->off_deadline_ms = now + sm->cfg.full_off_delay_ms;
    }
}

void pwr_step(pwr_sm_t *sm, uint32_t now, const pwr_inputs_t *in, uint32_t *press) {
    *press = 0;

    switch (sm->state) {
    case PWR_STATE_OFF:
        if (in->acc) wake_or_power_on(sm, now, in, press);
        break;

    case PWR_STATE_SLEEP_PENDING:
        if (in->acc) {
            wake_or_power_on(sm, now, in, press);
        } else if (sm->off_deadline_set && reached(now, sm->off_deadline_ms)) {
            if (in->service) break;
            *press = sm->cfg.pwr_off_press_ms;
            set_state(sm, PWR_STATE_OFF, now);
            sm->off_deadline_set = false;
        }
        break;

    case PWR_STATE_ON:
        if (in->acc) {
            sm->crank_pending = false; // ACC recovered (or never dropped)
            break;
        }
        if (!reached(now, sm->ignore_acc_until_ms)) break;
        if ((uint32_t)(now - sm->boot_ms) < sm->cfg.boot_grace_ms) break;
        if (!sm->crank_pending) {
            sm->crank_pending = true;
            sm->crank_deadline_ms = now + sm->cfg.crank_ignore_ms;
            break;
        }
        if (reached(now, sm->crank_deadline_ms)) {
            sm->crank_pending = false;
            if (in->service) break;
            *press = sm->cfg.sleep_press_ms;
            set_state(sm, PWR_STATE_SLEEP_PENDING, now);
            sm->off_deadline_set = true;
            sm->off_deadline_ms = now + sm->cfg.full_off_delay_ms;
        }
        break;
    }
}

const char *pwr_state_name(pwr_state_t s) {
    switch (s) {
    case PWR_STATE_OFF: return "off";
    case PWR_STATE_ON: return "on";
    case PWR_STATE_SLEEP_PENDING: return "sleep_pending";
    }
    return "?";
}
