// mcutool: look at and poke the peripheral board MCU from an adb root shell.
//
//   mcutool status            info and every property once
//   mcutool watch             print everything the MCU sends (Ctrl-C to stop)
//   mcutool set NAME V0 [V1]  write a property (name below or 0x... id)
//   mcutool bootsel [--force] reboot the MCU into its USB bootloader for picotool
//
// It opens the same /dev/hidraw node as the VHAL; hidraw hands every report to both.
#include <android-base/logging.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <atomic>
#include <chrono>
#include <string>
#include <thread>

#include "McuLink.h"

using android::hardware::automotive::vehicle::McuLink;

namespace {

struct Name {
    uint32_t prop;
    const char* name;
};

const Name kNames[] = {
        {MCU_PROP_PERF_VEHICLE_SPEED, "speed"},
        {MCU_PROP_GEAR_SELECTION, "gear"},
        {MCU_PROP_NIGHT_MODE, "night"},
        {MCU_PROP_IGNITION_STATE, "ignition"},
        {MCU_PROP_AP_POWER_STATE_REQ, "ap_req"},
        {MCU_PROP_AP_POWER_STATE_REPORT, "ap_report"},
        {MCU_PROP_DISPLAY_BRIGHTNESS, "brightness"},
        {MCU_PROP_SCREEN_POWER, "screen"},
        {MCU_PROP_BATTERY_MV, "battery_mv"},
        {MCU_PROP_RAIL_5V_MV, "rail5v_mv"},
        {MCU_PROP_BOARD_TEMP, "temp_dC"},
        {MCU_PROP_LUX, "lux"},
        {MCU_PROP_AMP_MODE, "amp_mode"},
        {MCU_PROP_AMP_ON, "amp_on"},
        {MCU_PROP_AUDIO_MUTE, "audio_mute"},
        {MCU_PROP_INPUTS, "inputs"},
        {MCU_PROP_STATUS, "status"},
        {MCU_PROP_POWER_STATE, "power_state"},
        {MCU_PROP_OFF_DELAY_S, "off_delay_s"},
        {MCU_PROP_GNSS_CMD, "gnss_cmd"},
        {MCU_PROP_GNSS_FIX, "gnss_fix"},
};

const char* propName(uint32_t prop) {
    for (const auto& n : kNames)
        if (n.prop == prop) return n.name;
    return nullptr;
}

const char* kPowerStates[] = {"off", "booting", "running", "shutdown_prep",
                              "suspended", "waking", "shutting_down", "latched_off"};

std::string bits(uint32_t v, const char* const* names, int n) {
    std::string s;
    for (int i = 0; i < n; i++)
        if (names[i] && (v & (1u << i))) s += std::string(s.empty() ? "" : ",") + names[i];
    return s.empty() ? "-" : s;
}

void printProp(const mcu_prop_t& p) {
    static const char* const inputs[] = {"acc", "reverse", "illum", "handbrake", "vim3_on",
                                         "service", nullptr, nullptr, "btn_screen", "btn_volup",
                                         "btn_voldn", "btn_mute"};
    static const char* const status[] = {"usbp_pg", "usbp_fault1", "usbp_fault2", "bb_ok",
                                         "bb_scp", "bb_ocp", "bb_ovp", "lux_ok", "gnss_power",
                                         "gnss_nmea", "r72_pullup", "low_battery", "hot",
                                         "dac_unmuted"};
    const char* name = propName(p.prop);
    if (name) printf("%-12s", name);
    else printf("0x%08x  ", p.prop);
    if (MCU_PROP_IS_FLOAT(p.prop)) {
        float f;
        memcpy(&f, &p.v0, sizeof(f));
        printf(" %.2f", f);
    } else {
        printf(" %d", p.v0);
        if (p.v1) printf(" %d", p.v1);
    }
    if (p.prop == MCU_PROP_INPUTS) printf("  [%s]", bits(p.v0, inputs, 12).c_str());
    if (p.prop == MCU_PROP_STATUS) printf("  [%s]", bits(p.v0, status, 14).c_str());
    if (p.prop == MCU_PROP_POWER_STATE && p.v0 >= 0 && p.v0 < 8) printf("  [%s]", kPowerStates[p.v0]);
    printf("\n");
}

int usage() {
    fprintf(stderr, "usage: mcutool status | watch | set NAME V0 [V1] | bootsel [--force]\n");
    return 2;
}

}  // namespace

int main(int argc, char** argv) {
    android::base::InitLogging(argv, android::base::StderrLogger);
    if (argc < 2) return usage();
    std::string cmd = argv[1];

    std::atomic<bool> enPullup{false};
    std::atomic<bool> gotInfo{false};
    bool quiet = cmd == "set" || cmd == "bootsel";
    McuLink link;
    link.start(
            [&](const std::vector<mcu_prop_t>& props, bool snapshot) {
                if (!quiet && (cmd == "watch" || snapshot))
                    for (const auto& p : props) printProp(p);
                (void)snapshot;
            },
            [&](const mcu_info_msg_t& info) {
                enPullup = info.flags & MCU_INFO_FLAG_EN_PULLUP;
                gotInfo = true;
                if (!quiet)
                    printf("firmware %u.%u.%u (%s), board rev 0.%u, protocol %u, up %u s%s\n",
                           info.fw_major, info.fw_minor, info.fw_patch, info.build,
                           info.board_rev, info.proto_version, info.uptime_s,
                           enPullup ? "" : ", R72 is a pull-down");
            },
            [](bool) {});

    for (int i = 0; i < 50 && !link.connected(); i++)
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    if (!link.connected()) {
        fprintf(stderr, "MCU not found (USB %04x:%04x)\n", MCU_USB_VID, MCU_USB_PID);
        return 1;
    }

    if (cmd == "status") {
        link.requestSnapshot();
        std::this_thread::sleep_for(std::chrono::milliseconds(1500));
    } else if (cmd == "watch") {
        link.requestSnapshot();
        while (link.connected()) std::this_thread::sleep_for(std::chrono::milliseconds(200));
        fprintf(stderr, "MCU disconnected\n");
    } else if (cmd == "set") {
        if (argc < 4) return usage();
        uint32_t prop = 0;
        for (const auto& n : kNames)
            if (strcmp(argv[2], n.name) == 0) prop = n.prop;
        if (!prop) prop = static_cast<uint32_t>(strtoul(argv[2], nullptr, 0));
        if (!prop) return usage();
        int32_t v1 = argc > 4 ? atoi(argv[4]) : 0;
        if (!link.set(prop, atoi(argv[3]), v1)) return 1;
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    } else if (cmd == "bootsel") {
        link.requestSnapshot();  // the MCU sends its info first
        for (int i = 0; i < 20 && !gotInfo; i++)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        bool force = argc > 2 && strcmp(argv[2], "--force") == 0;
        if (!enPullup && !force) {
            fprintf(stderr,
                    "R72 is a pull-down on this board: the VIM3 loses power as soon as the MCU\n"
                    "resets. Flash over SWD or from a PC instead, or use --force.\n");
            return 1;
        }
        link.rebootToBootloader();
        printf("MCU rebooting into BOOTSEL; flash with: picotool load -x carradio_mcu.uf2\n");
    } else {
        return usage();
    }
    link.stop();
    return 0;
}
