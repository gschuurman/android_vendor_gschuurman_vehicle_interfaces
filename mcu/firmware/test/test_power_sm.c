// Drive-cycle scenarios for the power state machine.
#include <assert.h>
#include <stdio.h>

#include "power_sm.h"

static pwr_sm_t sm;
static pwr_inputs_t in;
static uint32_t t;
static uint32_t presses, last_press_ms;
static int reqs, last_req = -1, last_param = -1;
static bool power;

static void run(uint32_t ms) {
    for (uint32_t i = 0; i < ms; i += 10) {
        t += 10;
        pwr_actions_t a = pwr_step(&sm, t, &in);
        power = a.power_en;
        if (a.key_press_ms) { presses++; last_press_ms = a.key_press_ms; }
        if (a.send_req) { reqs++; last_req = a.req; last_param = a.req_param; }
    }
}

static void report(int r) {
    pwr_on_report(&sm, r, 0, &in);
    pwr_actions_t a = pwr_step(&sm, t, &in);
    power = a.power_en;
    if (a.key_press_ms) { presses++; last_press_ms = a.key_press_ms; }
    if (a.send_req) { reqs++; last_req = a.req; last_param = a.req_param; }
}

static void reset(bool en_kept) {
    pwr_config_t c;
    pwr_default_config(&c);
    t = 1000;
    presses = 0;
    reqs = 0;
    last_req = last_param = -1;
    pwr_init(&sm, &c, t, &in, en_kept);
    power = sm.act.power_en;
}

static void boot_to_running(void) {
    in = (pwr_inputs_t){0};
    reset(false);
    run(1000);
    assert(sm.state == MCU_PWR_OFF && !power);
    in.acc = true;
    run(100);
    assert(sm.state == MCU_PWR_BOOTING && power);
    run(2000);
    in.sbc_on = true;  // VIM3 starts by itself on power
    run(100);
    assert(sm.state == MCU_PWR_RUNNING);
    assert(presses == 0);
    in.link_up = true;
    report(REP_WAIT_FOR_VHAL);
    assert(last_req == REQ_ON);
}

static void test_drive_suspend_resume(void) {
    boot_to_running();
    // Crank dip: ignored.
    in.acc = false;
    run(1500);
    in.acc = true;
    run(1000);
    assert(sm.state == MCU_PWR_RUNNING);
    // ACC off: SHUTDOWN_PREPARE / CAN_SLEEP.
    in.acc = false;
    run(3000);
    assert(sm.state == MCU_PWR_SHUTDOWN_PREP);
    assert(last_req == REQ_SHUTDOWN_PREPARE && last_param == PARAM_CAN_SLEEP);
    report(REP_DEEP_SLEEP_ENTRY);
    assert(sm.state == MCU_PWR_SUSPENDED && power);
    in.link_up = false;
    in.usb_suspended = true;
    run(60000);
    assert(sm.state == MCU_PWR_SUSPENDED);
    // ACC back: key press, then ON when the VHAL is back.
    uint32_t p = presses;
    in.acc = true;
    run(100);
    assert(sm.state == MCU_PWR_WAKING && presses == p + 1);
    run(1000);
    in.usb_suspended = false;
    in.link_up = true;
    run(20);
    assert(sm.state == MCU_PWR_RUNNING && last_req == REQ_ON);
    printf("drive/suspend/resume ok\n");
}

static void test_suspend_then_full_off(void) {
    boot_to_running();
    in.acc = false;
    run(3000);
    report(REP_DEEP_SLEEP_ENTRY);
    in.link_up = false;
    in.usb_suspended = true;
    uint32_t p = presses;
    run(15u * 60u * 1000u + 100);
    assert(sm.state == MCU_PWR_WAKING && presses == p + 1);
    in.usb_suspended = false;
    in.link_up = true;
    run(20);
    assert(sm.state == MCU_PWR_SHUTDOWN_PREP);
    assert(last_req == REQ_SHUTDOWN_PREPARE && last_param == PARAM_SHUTDOWN_ONLY);
    report(REP_SHUTDOWN_START);
    assert(sm.state == MCU_PWR_SHUTTING_DOWN && power);
    run(5000);
    in.sbc_on = false;
    in.link_up = false;
    run(1000);
    assert(power);   // rail must stay low for 2 s
    run(1500);
    assert(sm.state == MCU_PWR_OFF && !power);
    // Must not restart while ACC is off.
    run(10000);
    assert(sm.state == MCU_PWR_OFF && !power);
    printf("suspend then full off ok\n");
}

static void test_acc_back_during_prepare(void) {
    boot_to_running();
    in.acc = false;
    run(3000);
    assert(sm.state == MCU_PWR_SHUTDOWN_PREP);
    in.acc = true;
    run(20);
    assert(sm.state == MCU_PWR_RUNNING && last_req == REQ_CANCEL_SHUTDOWN);
    report(REP_SHUTDOWN_CANCELLED);
    assert(last_req == REQ_ON);
    printf("acc back during prepare ok\n");
}

static void test_no_link_legacy(void) {
    in = (pwr_inputs_t){0};
    reset(false);
    in.acc = true;
    run(100);
    run(5000);  // VIM3 does not start by itself: key press after 4 s
    assert(presses == 1 && last_press_ms == 1000);
    in.sbc_on = true;
    run(200);
    assert(sm.state == MCU_PWR_RUNNING);
    in.acc = false;
    run(3000);
    assert(sm.state == MCU_PWR_SHUTDOWN_PREP && presses == 2 && last_press_ms == 150);
    assert(reqs == 0);
    in.usb_suspended = true;
    run(4000);
    assert(sm.state == MCU_PWR_SUSPENDED);
    printf("legacy (no link) ok\n");
}

static void test_user_shutdown_with_acc_on(void) {
    boot_to_running();
    report(REP_SHUTDOWN_START);
    assert(sm.state == MCU_PWR_SHUTTING_DOWN);
    in.sbc_on = false;
    run(2500);
    assert(sm.state == MCU_PWR_OFF && !power);
    // ACC still on: OFF powers the VIM3 again after the settle time.
    run(4000);
    assert(sm.state == MCU_PWR_BOOTING && power);
    printf("shutdown from Android with ACC on ok\n");
}

static void test_mcu_reset_under_running_vim3(void) {
    in = (pwr_inputs_t){.acc = false, .sbc_on = true};
    reset(true);
    assert(sm.state == MCU_PWR_RUNNING && power);
    in.link_up = true;
    run(3000);
    assert(sm.state == MCU_PWR_SHUTDOWN_PREP && last_req == REQ_SHUTDOWN_PREPARE);
    printf("mcu reset under running vim3 ok\n");
}

static void test_low_battery(void) {
    boot_to_running();
    in.acc = false;
    run(3000);
    report(REP_DEEP_SLEEP_ENTRY);
    in.link_up = false;
    in.usb_suspended = true;
    run(1000);
    in.low_battery = true;
    run(20);
    assert(sm.state == MCU_PWR_WAKING);
    printf("low battery ok\n");
}

static void test_service_mode(void) {
    in = (pwr_inputs_t){.service = true};
    reset(false);
    run(100);
    assert(sm.state == MCU_PWR_BOOTING && power);
    run(5000);
    assert(presses == 0);  // never presses in service mode
    in.sbc_on = true;
    run(200);
    assert(sm.state == MCU_PWR_RUNNING);
    run(60000);
    assert(sm.state == MCU_PWR_RUNNING);
    printf("service mode ok\n");
}

static void test_wake_fails(void) {
    boot_to_running();
    in.acc = false;
    run(3000);
    report(REP_DEEP_SLEEP_ENTRY);
    in.link_up = false;
    in.usb_suspended = true;
    run(15u * 60u * 1000u + 100);
    assert(sm.state == MCU_PWR_WAKING);
    run(60000);  // never wakes
    assert(sm.state == MCU_PWR_OFF && !power);
    printf("wake fails -> cut ok\n");
}

int main(void) {
    test_drive_suspend_resume();
    test_suspend_then_full_off();
    test_acc_back_during_prepare();
    test_no_link_legacy();
    test_user_shutdown_with_acc_on();
    test_mcu_reset_under_running_vim3();
    test_low_battery();
    test_service_mode();
    test_wake_fails();
    printf("test_power_sm: ok\n");
    return 0;
}
