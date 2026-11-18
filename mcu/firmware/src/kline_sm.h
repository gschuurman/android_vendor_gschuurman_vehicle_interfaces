// K-line transport for the Rover MEMS 1.9 ECU (MGF), on the K-line module at J10.
//
// Hardware independent so it runs in the host tests (test/test_kline_sm.c) against a fake ECU.
// The caller feeds it received bytes and the time, and carries out the actions it returns
// (module power, line mode, bytes to send, frames to forward).
//
// Protocol (rover-mems-documentation, ECUs/1.x-ECU-all/diagnostics):
//   9600 8N1, single-byte commands. The L9637D echoes every byte we send (local echo); the
//   ECU then echoes the command and sends its answer.
//   Wake-up: line idle (high) for 2 s, then the address 0x16 at 5 baud (start bit, 8 data
//   bits LSB first, stop bit, 200 ms each) by driving the TX pin directly. The ECU answers
//   55 KB1 KB2 (55 76 83) at 9600; we send ~KB2 (0x7C), the ECU answers ~address (0xE9).
//   Then CA, 75, F4 (answer F4 00), D0 (answer D0 + 4-byte ECU id), then 80 / 7D alternately:
//   data frames whose first byte after the echo is the frame length including itself.
//   An ECU that is still in a session answers CA directly, so that is tried first.
//
// Only CA 75 F4 D0 80 7D (and CC = clear faults, on request) are ever sent: the head unit
// never runs actuator tests or changes adjustments.
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define KL_BUF 64

typedef enum {
    KL_OFF,         // module unpowered
    KL_POWERUP,     // module powered, line idle, settling
    KL_PROBE,       // CA sent without a wake-up (ECU may still be in a session)
    KL_IDLE,        // line idle high before the 5-baud address
    KL_ADDR,        // sending the address at 5 baud
    KL_SYNC,        // waiting for 55 KB1 KB2
    KL_SYNC_ACK,    // sent ~KB2, waiting for ~address
    KL_SESSION,     // command / response loop
    KL_BACKOFF,     // failed: line idle, retry later
} kl_state_t;

typedef struct {
    bool acc;
    bool enabled;   // MCU_PROP_KLINE_MODE != 0
} kl_inputs_t;

typedef struct {
    bool power;          // GPIO28: K-line side of the module powered
    bool uart;           // TX pin on the UART (true) or driven as a GPIO (false)
    bool line_high;      // GPIO level while !uart (high = recessive / idle)
    bool flush_rx;       // one-shot: drop anything in the RX buffer
    int tx;              // one-shot: byte to send (-1 = none)
    bool frame;          // one-shot: frame[0..frame_len) is a complete ECU answer
    uint8_t frame_len;
    const uint8_t *frame_data;
    bool state_changed;  // one-shot: public state or ECU id changed
} kl_actions_t;

typedef struct {
    kl_state_t state;
    uint32_t now, state_since;
    // session
    uint8_t cmd;             // command in flight
    bool cmd_sent;
    bool echo_seen;          // local echo of cmd received
    uint32_t sent_at;
    uint8_t next_cmd;        // queued after the current answer
    bool clear_faults;       // CC requested
    uint8_t buf[KL_BUF];
    uint8_t len;
    uint32_t last_byte_at;
    uint32_t ecu_id;
    uint8_t errors;          // consecutive bad / missing answers
    uint8_t wake_fails;      // consecutive failed wake-ups
    uint32_t backoff_ms;
    // wake-up
    uint8_t kb2;
    uint32_t sync_done_at;
    bool sync_ack_sent;
    int public_state;        // MCU_KLINE_ST_*
    kl_actions_t act;
    uint8_t frame[KL_BUF];
} kl_sm_t;

// Timing (ms). The poll loop runs as fast as the ECU answers.
#define KL_POWERUP_MS 100
#define KL_IDLE_MS 2000
#define KL_BIT_MS 200
#define KL_SYNC_TIMEOUT_MS 1000   // address end -> 55 KB1 KB2
#define KL_W4_MS 40               // KB2 -> ~KB2 (ISO 9141 W4: 25..50 ms)
#define KL_ACK_TIMEOUT_MS 500
#define KL_ANSWER_TIMEOUT_MS 1000 // command -> complete answer
#define KL_GAP_MS 2               // between an answer and the next command
#define KL_MAX_ERRORS 3
#define KL_RETRY_MS 3000          // after a lost session or the first failed wake-ups
#define KL_RETRY_LONG_MS 30000    // after KL_WAKE_FAILS_LONG wake-ups without an answer
#define KL_WAKE_FAILS_LONG 5

#define KL_ECU_ADDR 0x16

void kl_init(kl_sm_t *sm, uint32_t now);
// A byte arrived on RX (already includes our own local echo).
void kl_rx(kl_sm_t *sm, uint8_t b, uint32_t now);
// Ask for one 0xCC (clear faults) in the running session.
void kl_request_clear_faults(kl_sm_t *sm);
// Run once per main-loop pass.
kl_actions_t kl_step(kl_sm_t *sm, uint32_t now, const kl_inputs_t *in);

// MCU_KLINE_ST_* for MCU_PROP_KLINE_STATE.
int kl_public_state(const kl_sm_t *sm);
// Expected total answer length for cmd given what has arrived (0 = not known yet, -1 = bad).
int kl_answer_len(uint8_t cmd, const uint8_t *buf, uint8_t len);
