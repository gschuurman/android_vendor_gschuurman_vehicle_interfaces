#include "kline_sm.h"

#include <string.h>

#include "mcu_protocol.h"

static uint32_t since(uint32_t now, uint32_t t) { return now - t; }

int kl_public_state(const kl_sm_t *sm) {
    switch (sm->state) {
    case KL_OFF: return MCU_KLINE_ST_OFF;
    case KL_SESSION: return MCU_KLINE_ST_CONNECTED;
    case KL_BACKOFF: return MCU_KLINE_ST_RETRY;
    default: return MCU_KLINE_ST_WAKING;
    }
}

static void set_state(kl_sm_t *sm, kl_state_t s) {
    if (sm->state == s) return;
    sm->state = s;
    sm->state_since = sm->now;
    int pub = kl_public_state(sm);
    if (pub != sm->public_state) {
        sm->public_state = pub;
        sm->act.state_changed = true;
    }
}

void kl_init(kl_sm_t *sm, uint32_t now) {
    memset(sm, 0, sizeof(*sm));
    sm->now = sm->state_since = now;
    sm->state = KL_OFF;
    sm->public_state = MCU_KLINE_ST_OFF;
    sm->act.tx = -1;
    sm->act.line_high = true;
}

void kl_request_clear_faults(kl_sm_t *sm) {
    if (sm->state == KL_SESSION) sm->clear_faults = true;
}

int kl_answer_len(uint8_t cmd, const uint8_t *buf, uint8_t len) {
    if (len == 0) return 0;
    if (buf[0] != cmd) return -1;  // the ECU echoes the command first
    switch (cmd) {
    case 0xCA:
    case 0x75: return 1;
    case 0xF4:
    case 0xCC: return 2;
    case 0xD0: return 5;
    case 0x80:
    case 0x7D:
        if (len < 2) return 0;
        if (buf[1] < 2 || buf[1] + 1 > KL_BUF) return -1;
        return buf[1] + 1;
    default: return -1;
    }
}

static uint8_t cmd_after(kl_sm_t *sm, uint8_t cmd) {
    switch (cmd) {
    case 0xCA: return 0x75;
    case 0x75: return 0xF4;
    case 0xF4: return 0xD0;
    case 0x80:
    case 0x7D:
        if (sm->clear_faults) {
            sm->clear_faults = false;
            return 0xCC;
        }
        return cmd == 0x80 ? 0x7D : 0x80;
    default: return 0x80;  // D0, CC
    }
}

static void send_cmd(kl_sm_t *sm, uint8_t c) {
    sm->cmd = c;
    sm->cmd_sent = true;
    sm->echo_seen = false;
    sm->len = 0;
    sm->sent_at = sm->now;
    sm->act.tx = c;
}

static void line_idle(kl_sm_t *sm) {
    sm->act.uart = false;
    sm->act.line_high = true;
}

void kl_rx(kl_sm_t *sm, uint8_t b, uint32_t now) {
    sm->last_byte_at = now;
    switch (sm->state) {
    case KL_PROBE:
    case KL_SESSION:
        if (!sm->cmd_sent) return;  // stray byte between commands
        if (!sm->echo_seen) {
            if (b == sm->cmd) sm->echo_seen = true;  // the transceiver's copy of our byte
            return;
        }
        break;
    case KL_SYNC:
        if (sm->len == 0 && b != 0x55) return;  // break / bit-bang residue
        break;
    case KL_SYNC_ACK:
        if (!sm->echo_seen && b == (uint8_t)~sm->kb2) {
            sm->echo_seen = true;
            return;
        }
        break;
    default:
        return;
    }
    if (sm->len < KL_BUF) sm->buf[sm->len++] = b;
}

static void start_backoff(kl_sm_t *sm, uint32_t ms) {
    line_idle(sm);
    sm->act.flush_rx = true;
    sm->cmd_sent = false;
    sm->len = 0;
    sm->backoff_ms = ms;
    set_state(sm, KL_BACKOFF);
}

static void wake_failed(kl_sm_t *sm) {
    if (sm->wake_fails < 255) sm->wake_fails++;
    start_backoff(sm, sm->wake_fails >= KL_WAKE_FAILS_LONG ? KL_RETRY_LONG_MS : KL_RETRY_MS);
}

static void enter_session(kl_sm_t *sm, uint8_t next) {
    sm->wake_fails = 0;
    sm->errors = 0;
    sm->cmd_sent = false;
    sm->next_cmd = next;
    sm->sent_at = sm->now;  // gap reference
    set_state(sm, KL_SESSION);
}

// A complete answer to sm->cmd is in buf[0..n).
static void answered(kl_sm_t *sm, int n) {
    if (sm->cmd == 0xD0) {
        uint32_t id = (uint32_t)sm->buf[1] | (uint32_t)sm->buf[2] << 8 |
                      (uint32_t)sm->buf[3] << 16 | (uint32_t)sm->buf[4] << 24;
        if (id != sm->ecu_id) {
            sm->ecu_id = id;
            sm->act.state_changed = true;
        }
    }
    if (sm->cmd == 0x80 || sm->cmd == 0x7D || sm->cmd == 0xD0 || sm->cmd == 0xCC) {
        memcpy(sm->frame, sm->buf, (size_t)n);
        sm->act.frame = true;
        sm->act.frame_len = (uint8_t)n;
        sm->act.frame_data = sm->frame;
    }
    sm->errors = 0;
    sm->next_cmd = cmd_after(sm, sm->cmd);
    sm->cmd_sent = false;
    sm->sent_at = sm->now;
}

// Bad or missing answer in the session.
static void answer_error(kl_sm_t *sm) {
    sm->act.flush_rx = true;
    sm->cmd_sent = false;
    sm->len = 0;
    sm->sent_at = sm->now;
    sm->next_cmd = sm->cmd;  // ask again
    if (++sm->errors >= KL_MAX_ERRORS) {
        sm->wake_fails = 0;
        start_backoff(sm, KL_RETRY_MS);
    }
}

kl_actions_t kl_step(kl_sm_t *sm, uint32_t now, const kl_inputs_t *in) {
    sm->now = now;

    if (!in->acc || !in->enabled) {
        if (sm->state != KL_OFF) {
            sm->act.power = false;
            line_idle(sm);
            sm->cmd_sent = false;
            sm->clear_faults = false;
            sm->wake_fails = 0;
            set_state(sm, KL_OFF);
        }
        goto out;
    }

    switch (sm->state) {
    case KL_OFF:
        sm->act.power = true;
        line_idle(sm);
        set_state(sm, KL_POWERUP);
        break;

    case KL_POWERUP:
        if (since(now, sm->state_since) >= KL_POWERUP_MS) {
            sm->act.uart = true;
            sm->act.flush_rx = true;
            set_state(sm, KL_PROBE);
            send_cmd(sm, 0xCA);
        }
        break;

    case KL_PROBE: {
        int n = kl_answer_len(sm->cmd, sm->buf, sm->len);
        if (n > 0 && sm->len >= n) {
            enter_session(sm, 0x75);  // ECU was still in a session: carry on with the init
        } else if (n < 0 || since(now, sm->sent_at) >= KL_ANSWER_TIMEOUT_MS / 3) {
            sm->cmd_sent = false;
            line_idle(sm);
            set_state(sm, KL_IDLE);
        }
        break;
    }

    case KL_IDLE:
        line_idle(sm);
        if (since(now, sm->state_since) >= KL_IDLE_MS) set_state(sm, KL_ADDR);
        break;

    case KL_ADDR: {
        uint32_t k = since(now, sm->state_since) / KL_BIT_MS;
        if (k >= 10) {
            sm->act.uart = true;
            sm->act.line_high = true;
            sm->act.flush_rx = true;
            sm->len = 0;
            set_state(sm, KL_SYNC);
            break;
        }
        bool level;
        if (k == 0) level = false;                                     // start bit
        else if (k <= 8) level = (KL_ECU_ADDR >> (k - 1)) & 1;         // data, LSB first
        else level = true;                                             // stop bit
        sm->act.uart = false;
        sm->act.line_high = level;
        break;
    }

    case KL_SYNC:
        if (sm->len >= 3) {
            if (sm->sync_done_at == 0) sm->sync_done_at = now ? now : 1;
            if (since(now, sm->sync_done_at) >= KL_W4_MS) {
                sm->kb2 = sm->buf[2];
                sm->len = 0;
                sm->echo_seen = false;
                sm->sync_done_at = 0;
                sm->act.tx = (uint8_t)~sm->kb2;
                set_state(sm, KL_SYNC_ACK);
            }
        } else if (since(now, sm->state_since) >= KL_SYNC_TIMEOUT_MS) {
            sm->sync_done_at = 0;
            wake_failed(sm);
        }
        break;

    case KL_SYNC_ACK:
        if (sm->len >= 1) {
            if (sm->buf[0] == (uint8_t)~KL_ECU_ADDR) enter_session(sm, 0xCA);
            else wake_failed(sm);
        } else if (since(now, sm->state_since) >= KL_ACK_TIMEOUT_MS) {
            wake_failed(sm);
        }
        break;

    case KL_SESSION:
        if (!sm->cmd_sent) {
            if (since(now, sm->sent_at) >= KL_GAP_MS) send_cmd(sm, sm->next_cmd);
            break;
        }
        {
            int n = kl_answer_len(sm->cmd, sm->buf, sm->len);
            if (n < 0) answer_error(sm);
            else if (n > 0 && sm->len >= n) answered(sm, n);
            else if (since(now, sm->sent_at) >= KL_ANSWER_TIMEOUT_MS) answer_error(sm);
        }
        break;

    case KL_BACKOFF:
        line_idle(sm);
        if (since(now, sm->state_since) >= sm->backoff_ms) set_state(sm, KL_IDLE);
        break;
    }

out:;
    kl_actions_t out = sm->act;
    sm->act.tx = -1;
    sm->act.flush_rx = false;
    sm->act.frame = false;
    sm->act.state_changed = false;
    return out;
}
