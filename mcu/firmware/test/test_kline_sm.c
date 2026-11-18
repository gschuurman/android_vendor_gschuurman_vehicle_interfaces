// K-line transport against a simulated MEMS 1.9 ECU and L9637D (local echo).
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "kline_sm.h"
#include "mcu_protocol.h"

// ---- simulated wire: bytes with delivery times ----
typedef struct { uint32_t at; uint8_t b; } rxb_t;
static rxb_t rxq[512];
static int rxn;
static void deliver(uint32_t at, uint8_t b) { assert(rxn < 512); rxq[rxn++] = (rxb_t){at, b}; }

// ---- fake ECU ----
static bool ecu_present = true;
static bool ecu_mute;          // stops answering (wiring fault mid-drive)
static bool ecu_in_session;
static uint32_t ecu_last_cmd;
static bool line_high = true, uart;
static uint32_t line_low_since, line_high_since;
static int addr_bit = -1;      // decoding the 5-baud address: -1 idle
static uint32_t addr_start;
static uint8_t addr;
static bool bad_len_once;      // next 0x80 answer has a bogus length byte
static const uint8_t ECU_ID[4] = {0x39, 0x00, 0x00, 0x5C};

static uint8_t frame80[29], frame7d[33];
static int sent_cc;

static void ecu_answer(uint32_t t, const uint8_t *b, int n) {
    for (int i = 0; i < n; i++) deliver(t + 2 + (uint32_t)i, b[i]);
}

static void ecu_on_byte(uint32_t t, uint8_t c) {
    if (!ecu_present || ecu_mute) return;
    if (ecu_in_session && t - ecu_last_cmd > 5000) ecu_in_session = false;  // P3 timeout
    if (c == 0x7C && !ecu_in_session) {  // ~KB2 after the sync
        uint8_t a = 0xE9;
        ecu_answer(t, &a, 1);
        ecu_in_session = true;
        ecu_last_cmd = t;
        return;
    }
    if (!ecu_in_session) return;
    ecu_last_cmd = t;
    switch (c) {
    case 0xCA: case 0x75: ecu_answer(t, &c, 1); break;
    case 0xF4: { uint8_t a[] = {0xF4, 0x00}; ecu_answer(t, a, 2); break; }
    case 0xD0: { uint8_t a[] = {0xD0, ECU_ID[0], ECU_ID[1], ECU_ID[2], ECU_ID[3]}; ecu_answer(t, a, 5); break; }
    case 0xCC: { uint8_t a[] = {0xCC, 0x00}; ecu_answer(t, a, 2); sent_cc++; break; }
    case 0x80:
        if (bad_len_once) { bad_len_once = false; uint8_t a[] = {0x80, 0x01, 0x00}; ecu_answer(t, a, 3); break; }
        ecu_answer(t, frame80, sizeof(frame80)); break;
    case 0x7D: ecu_answer(t, frame7d, sizeof(frame7d)); break;
    default: assert(!"command outside the whitelist");
    }
}

// Line level from the MCU while it bit-bangs: decode the 5-baud address.
static void ecu_on_line(uint32_t t) {
    if (!ecu_present || ecu_mute) return;
    if (addr_bit < 0) {
        if (!line_high && t - line_high_since >= 300 && t == line_low_since) {
            addr_bit = 0;
            addr_start = t;
            addr = 0;
        }
        return;
    }
    // sample in the middle of each bit
    uint32_t k = (t - addr_start) / 200, mid = addr_start + k * 200 + 100;
    if (t != mid) return;
    if (k >= 1 && k <= 8 && line_high) addr |= (uint8_t)(1u << (k - 1));
    if (k == 9) {
        addr_bit = -1;
        if (line_high && addr == KL_ECU_ADDR) {
            ecu_in_session = false;
            uint8_t a[] = {0x55, 0x76, 0x83};
            for (int i = 0; i < 3; i++) deliver(t + 100 + 60 + (uint32_t)i * 2, a[i]);
        }
    }
}

// ---- harness ----
static kl_sm_t sm;
static kl_inputs_t in = {.acc = true, .enabled = true};
static uint32_t t;
static bool power;
static int frames80, frames7d, framesd0, txcount;
static uint32_t first_connected_at;
static bool saw_addr;
static uint8_t last80[64];

static void run(uint32_t ms) {
    for (uint32_t i = 0; i < ms; i++) {
        t++;
        // deliver due bytes
        for (int j = 0; j < rxn;) {
            if (rxq[j].at <= t) {
                if (power && uart) kl_rx(&sm, rxq[j].b, t);
                memmove(&rxq[j], &rxq[j + 1], sizeof(rxq[0]) * (size_t)(rxn - j - 1));
                rxn--;
            } else {
                j++;
            }
        }
        kl_actions_t a = kl_step(&sm, t, &in);
        power = a.power;
        bool was_high = line_high;
        uart = a.uart;
        line_high = a.uart ? true : a.line_high;
        if (!power) line_high = true;
        if (line_high != was_high) {
            if (line_high) line_high_since = t; else line_low_since = t;
        }
        if (sm.state == KL_ADDR) saw_addr = true;
        if (power) ecu_on_line(t);
        if (a.flush_rx) {
            // only bytes already on the wire are dropped
            for (int j = 0; j < rxn;) {
                if (rxq[j].at <= t) { memmove(&rxq[j], &rxq[j + 1], sizeof(rxq[0]) * (size_t)(rxn - j - 1)); rxn--; }
                else j++;
            }
        }
        if (a.tx >= 0) {
            assert(power && uart);
            uint8_t c = (uint8_t)a.tx;
            assert(c == 0xCA || c == 0x75 || c == 0xF4 || c == 0xD0 || c == 0x80 || c == 0x7D ||
                   c == 0xCC || c == 0x7C);
            txcount++;
            deliver(t + 1, c);  // L9637D local echo
            ecu_on_byte(t + 1, c);
        }
        if (a.frame) {
            if (a.frame_data[0] == 0x80) { frames80++; memcpy(last80, a.frame_data, a.frame_len); assert(a.frame_len == sizeof(frame80)); }
            if (a.frame_data[0] == 0x7D) { frames7d++; assert(a.frame_len == sizeof(frame7d)); }
            if (a.frame_data[0] == 0xD0) framesd0++;
        }
        if (kl_public_state(&sm) == MCU_KLINE_ST_CONNECTED && !first_connected_at) first_connected_at = t;
    }
}

static void reset(void) {
    rxn = 0;
    ecu_present = true;
    ecu_mute = false;
    ecu_in_session = false;
    line_high = true; uart = false;
    line_high_since = 0;
    addr_bit = -1;
    bad_len_once = false;
    sent_cc = 0;
    t = 1000;
    in = (kl_inputs_t){.acc = true, .enabled = true};
    frames80 = frames7d = framesd0 = txcount = 0;
    first_connected_at = 0;
    saw_addr = false;
    power = false;
    kl_init(&sm, t);
    frame80[0] = 0x80; frame80[1] = sizeof(frame80) - 1;
    frame80[2] = 0x03; frame80[3] = 0x20;   // 800 rpm
    frame80[4] = 90 + 55;                   // coolant 90 C
    for (int i = 5; i < (int)sizeof(frame80); i++) frame80[i] = (uint8_t)i;
    frame7d[0] = 0x7D; frame7d[1] = sizeof(frame7d) - 1;
    for (int i = 2; i < (int)sizeof(frame7d); i++) frame7d[i] = (uint8_t)(0x40 + i);
}

static void test_cold_wake(void) {
    reset();
    run(2000 + 2000 + 1000);  // power-up + failed probe + idle + address + sync
    assert(saw_addr);
    run(2000);
    assert(kl_public_state(&sm) == MCU_KLINE_ST_CONNECTED);
    assert(sm.ecu_id == (0x39u | 0x5Cu << 24));
    assert(framesd0 == 1);
    assert(frames80 > 10 && frames7d > 10);
    assert(last80[4] == 90 + 55);
    printf("cold wake: connected after %u ms, %d+%d frames in 2 s ok\n",
           first_connected_at - 1000, frames80, frames7d);
}

static void test_acc_cycle_probe(void) {
    reset();
    run(6000);
    assert(kl_public_state(&sm) == MCU_KLINE_ST_CONNECTED);
    in.acc = false;
    run(10);
    assert(sm.state == KL_OFF && !power);
    run(1000);   // ECU still in its session (< 5 s)
    in.acc = true;
    saw_addr = false;
    first_connected_at = 0;
    uint32_t t0 = t;
    run(1000);
    assert(kl_public_state(&sm) == MCU_KLINE_ST_CONNECTED && !saw_addr);
    printf("ACC cycle: probe reconnects in %u ms without a wake-up ok\n", first_connected_at - t0);
}

static void test_no_ecu(void) {
    reset();
    ecu_present = false;
    run(20000);
    assert(kl_public_state(&sm) == MCU_KLINE_ST_RETRY || kl_public_state(&sm) == MCU_KLINE_ST_WAKING);
    assert(power);
    run(60000);
    assert(sm.wake_fails >= KL_WAKE_FAILS_LONG && sm.backoff_ms == KL_RETRY_LONG_MS);
    int tx_before = txcount;
    run(25000);
    assert(txcount - tx_before <= 2);  // long back-off: at most one more attempt
    // ECU appears (ignition on later): connects at the next attempt
    ecu_present = true;
    run(40000);
    assert(kl_public_state(&sm) == MCU_KLINE_ST_CONNECTED);
    printf("no ECU: backs off, connects once it answers ok\n");
}

static void test_ecu_goes_silent(void) {
    reset();
    run(6000);
    assert(kl_public_state(&sm) == MCU_KLINE_ST_CONNECTED);
    ecu_mute = true;
    run(KL_ANSWER_TIMEOUT_MS * KL_MAX_ERRORS + 100);
    assert(kl_public_state(&sm) == MCU_KLINE_ST_RETRY);
    ecu_mute = false;
    ecu_in_session = false;
    run(KL_RETRY_MS + 2000 + 2000 + 1000);
    assert(kl_public_state(&sm) == MCU_KLINE_ST_CONNECTED);
    printf("ECU silent: retry and reconnect ok\n");
}

static void test_clear_faults_once(void) {
    reset();
    run(6000);
    kl_request_clear_faults(&sm);
    run(2000);
    assert(sent_cc == 1);
    assert(kl_public_state(&sm) == MCU_KLINE_ST_CONNECTED);
    printf("clear faults: one 0xCC ok\n");
}

static void test_bad_length(void) {
    reset();
    run(6000);
    int f = frames80;
    bad_len_once = true;
    run(1000);
    assert(kl_public_state(&sm) == MCU_KLINE_ST_CONNECTED && frames80 > f);
    printf("bad length byte: recovers ok\n");
}

static void test_disabled(void) {
    reset();
    in.enabled = false;
    run(10000);
    assert(sm.state == KL_OFF && !power && txcount == 0);
    printf("disabled: module stays off ok\n");
}

static void test_answer_len(void) {
    uint8_t a[] = {0x80, 0x1C};
    assert(kl_answer_len(0x80, a, 1) == 0);
    assert(kl_answer_len(0x80, a, 2) == 0x1D);
    uint8_t b[] = {0x7D};
    assert(kl_answer_len(0x80, b, 1) == -1);
    uint8_t c[] = {0x80, 0x01};
    assert(kl_answer_len(0x80, c, 2) == -1);
    uint8_t d[] = {0xD0};
    assert(kl_answer_len(0xD0, d, 1) == 5);
}

int main(void) {
    test_answer_len();
    test_cold_wake();
    test_acc_cycle_probe();
    test_no_ecu();
    test_ecu_goes_silent();
    test_clear_faults_once();
    test_bad_length();
    test_disabled();
    printf("test_kline_sm: ok\n");
    return 0;
}
