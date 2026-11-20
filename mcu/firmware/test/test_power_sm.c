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

// 2026-11-15/16 in the car: Android reported DEEP_SLEEP_ENTRY but never suspended (it waited for
// FINISHED), so the link stayed up. After the off delay the MCU pressed the key to wake it for
// the shutdown and then waited in WAKING forever: the VIM3 stayed on all night.
static void test_sleep_entry_without_suspend(void) {
    boot_to_running();
    in.acc = false;
    run(3000);
    assert(sm.state == MCU_PWR_SHUTDOWN_PREP);
    report(REP_DEEP_SLEEP_ENTRY);
    assert(sm.state == MCU_PWR_SUSPENDED);
    uint32_t p = presses;
    run(15u * 60u * 1000u + 1000);  // off delay; link still up, USB not suspended
    assert(sm.state == MCU_PWR_WAKING && presses == p + 1);
    run(60000);  // Android never answers (it never slept, so no DEEP_SLEEP_EXIT)
    assert(sm.state == MCU_PWR_SHUTDOWN_PREP);
    assert(last_req == REQ_SHUTDOWN_PREPARE && last_param == PARAM_SHUTDOWN_ONLY);
    run(5u * 60u * 1000u + 1000);  // still no shutdown: the prepare timeout cuts the power
    assert(sm.state == MCU_PWR_OFF && !power);
}

// PSCI SYSTEM_SUSPEND: the VIM3's bl301 switches its 5V/3V3 rails off while asleep, so the rail
// sense goes low and the USB device disappears (tud_mounted false = usb_suspended).
static void enter_deep_sleep(void) {
    boot_to_running();
    in.acc = false;
    run(3000);
    report(REP_DEEP_SLEEP_ENTRY);
    in.link_up = false;
    in.usb_suspended = true;
    in.sbc_on = false;
}

static void test_deep_sleep_rail_off_resume(void) {
    enter_deep_sleep();
    run(60000);
    assert(sm.state == MCU_PWR_SUSPENDED && power);  // low rail is not an off
    uint32_t p = presses;
    in.acc = true;
    run(100);
    assert(sm.state == MCU_PWR_WAKING && presses == p + 1);
    run(3000);  // rail low for longer than sbc_off_confirm_ms while resuming
    assert(sm.state == MCU_PWR_WAKING && power);
    in.sbc_on = true;
    run(3000);
    in.usb_suspended = false;
    in.link_up = true;
    run(20);
    assert(sm.state == MCU_PWR_RUNNING && last_req == REQ_ON && power);
    // Afterwards a rail drop is a real power-off again.
    in.sbc_on = false;
    run(2500);
    assert(sm.state == MCU_PWR_LATCHED_OFF && !power);
    printf("deep sleep rail off -> resume ok\n");
}

static void test_deep_sleep_rail_off_full_off(void) {
    enter_deep_sleep();
    uint32_t p = presses;
    run(15u * 60u * 1000u + 100);
    assert(sm.state == MCU_PWR_WAKING && presses == p + 1 && power);
    run(2000);
    in.sbc_on = true;
    run(3000);
    in.usb_suspended = false;
    in.link_up = true;
    run(20);
    assert(sm.state == MCU_PWR_SHUTDOWN_PREP && last_param == PARAM_SHUTDOWN_ONLY);
    report(REP_SHUTDOWN_START);
    run(5000);
    in.sbc_on = false;
    in.link_up = false;
    run(2500);
    assert(sm.state == MCU_PWR_OFF && !power);
    printf("deep sleep rail off -> full off ok\n");
}

static void test_deep_sleep_wake_fails_acc_on(void) {
    enter_deep_sleep();
    run(10000);
    in.acc = true;
    run(100);
    assert(sm.state == MCU_PWR_WAKING);
    run(60000);  // never resumes: cut, then boot from cold because ACC is on
    assert(sm.state == MCU_PWR_BOOTING || sm.state == MCU_PWR_OFF);
    assert(sm.boot_attempt <= 1);
    printf("deep sleep wake fails, ACC on -> cold boot ok\n");
}

// 2026-11-18 bench: ACC on after a deep sleep, the VIM3 resumed far enough for USB to come back
// but hung in the kernel; no VHAL. Must end in a cold boot, not RUNNING forever.
static void test_resume_hangs_acc_on(void) {
    enter_deep_sleep();
    run(10000);
    in.acc = true;
    run(100);
    assert(sm.state == MCU_PWR_WAKING);
    in.sbc_on = true;
    in.usb_suspended = false;  // USB host back, Android never comes
    run(46000);
    assert(sm.state == MCU_PWR_RUNNING && sm.await_link && power);
    run(3u * 60u * 1000u - 2000);
    assert(sm.state == MCU_PWR_RUNNING);
    run(2100);
    assert(sm.state == MCU_PWR_OFF && !power);  // cut
    in.sbc_on = false;  // supply gone: the rail drops
    in.usb_suspended = true;
    run(4000);
    assert(sm.state == MCU_PWR_BOOTING && power);  // ACC on: cold boot
    printf("resume hangs, ACC on -> cold boot ok\n");
}

// The same, but the VHAL turns up late: no cut.
static void test_resume_slow_link(void) {
    enter_deep_sleep();
    run(10000);
    in.acc = true;
    run(100);
    in.sbc_on = true;
    in.usb_suspended = false;
    run(46000);
    assert(sm.state == MCU_PWR_RUNNING && sm.await_link);
    run(60000);
    in.link_up = true;
    report(REP_DEEP_SLEEP_EXIT);
    run(5u * 60u * 1000u);
    assert(sm.state == MCU_PWR_RUNNING && !sm.await_link && power);
    printf("resume with a late VHAL -> keeps running ok\n");
}

// s2idle wake with ACC on where the VIM3 never answers the key (USB stays suspended): cut too.
static void test_wake_fails_acc_on_shallow(void) {
    boot_to_running();
    in.acc = false;
    run(3000);
    report(REP_DEEP_SLEEP_ENTRY);
    sm.deep_sleep = false;  // s2idle: rail stays up
    in.link_up = false;
    in.usb_suspended = true;
    run(10000);
    in.acc = true;
    run(100);
    assert(sm.state == MCU_PWR_WAKING);
    run(44000);
    assert(sm.state == MCU_PWR_WAKING);
    run(2000);
    assert(sm.state == MCU_PWR_OFF && !power);  // 3 presses, then cut; ACC on boots it again
    printf("shallow wake fails, ACC on -> cold boot ok\n");
}

// Bench 2026-11-20: VIM3 ribbon unplugged (no rail sense), service jumper fitted: the boot timeout
// cut the supply every 90 s. Service mode must never cut.
static void test_service_no_rail_sense(void) {
    in = (pwr_inputs_t){0};
    reset(false);
    in.service = true;
    run(100);
    assert(sm.state == MCU_PWR_BOOTING && power);
    run(10u * 60u * 1000u);
    assert(sm.state == MCU_PWR_BOOTING && power && presses == 0);
    printf("service jumper, no rail sense -> stays powered ok\n");
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
    test_sleep_entry_without_suspend();
    test_deep_sleep_rail_off_resume();
    test_deep_sleep_rail_off_full_off();
    test_deep_sleep_wake_fails_acc_on();
    test_resume_hangs_acc_on();
    test_resume_slow_link();
    test_wake_fails_acc_on_shallow();
    test_service_no_rail_sense();
    printf("test_power_sm: ok\n");
    return 0;
}
