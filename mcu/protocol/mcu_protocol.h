// Wire protocol between the peripheral board MCU (RP2350B) and the VHAL.
//
// Shared by the firmware (C) and the VHAL (C++). Keep it plain C and change
// MCU_PROTO_VERSION whenever a message layout changes.
//
// Transport: USB HID, vendor usage page 0xFF00, no report IDs, 64-byte input
// and output reports. Android sees it as /dev/hidraw*: one read() returns one
// report, one write() sends one. All integers are little endian.
//
// The MCU sends property updates keyed by real VHAL property IDs (standard IDs
// from VehicleProperty.aidl, plus the vendor IDs below). The host sends
// property writes the same way. A property carries up to two int32 values;
// for FLOAT properties (type bits 0x00600000) v0 holds the IEEE-754 bits.
#ifndef MCU_PROTOCOL_H
#define MCU_PROTOCOL_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MCU_USB_VID 0x2E8A        // Raspberry Pi
#define MCU_USB_PID 0xCA50        // private, not allocated by Raspberry Pi
#define MCU_PROTO_VERSION 1
#define MCU_REPORT_SIZE 64
#define MCU_HID_USAGE_PAGE 0xFF00

// ---- Message types (first byte of every report) ----
enum {
    // MCU -> host
    MCU_MSG_PROPS = 0x01,       // mcu_props_msg_t: property updates
    MCU_MSG_INFO = 0x02,        // mcu_info_msg_t: firmware and board info
    MCU_MSG_LOG = 0x03,         // mcu_log_msg_t: one line of text
    MCU_MSG_KLINE_FRAME = 0x04, // mcu_kline_frame_msg_t: one raw ECU response (K-line module)
    // host -> MCU
    MCU_MSG_HOST_HELLO = 0x81,  // mcu_hello_msg_t: heartbeat, send every second
    MCU_MSG_HOST_SET = 0x82,    // mcu_props_msg_t: property writes
    MCU_MSG_HOST_SNAPSHOT = 0x83, // ask for MCU_MSG_INFO plus every property
    MCU_MSG_HOST_BOOTSEL = 0x84,  // reboot into the USB bootloader (needs magic)
};

// Flags in mcu_props_msg_t.flags
#define MCU_PROPS_FLAG_SNAPSHOT 0x01      // part of a full snapshot
#define MCU_PROPS_FLAG_SNAPSHOT_END 0x02  // last report of a snapshot

#define MCU_PROPS_PER_MSG 5

typedef struct __attribute__((packed)) {
    uint32_t prop;
    int32_t v0;
    int32_t v1;
} mcu_prop_t;

typedef struct __attribute__((packed)) {
    uint8_t type;   // MCU_MSG_PROPS or MCU_MSG_HOST_SET
    uint8_t seq;
    uint8_t count;  // 1..MCU_PROPS_PER_MSG
    uint8_t flags;
    mcu_prop_t props[MCU_PROPS_PER_MSG];
} mcu_props_msg_t;

typedef struct __attribute__((packed)) {
    uint8_t type;   // MCU_MSG_INFO
    uint8_t proto_version;
    uint8_t fw_major, fw_minor, fw_patch;
    uint8_t reset_reason;   // MCU_RESET_*
    uint8_t board_rev;      // 6 = rev 0.6
    uint8_t flags;          // MCU_INFO_FLAG_*
    uint32_t uptime_s;
    char build[52];         // NUL-terminated build id
} mcu_info_msg_t;

#define MCU_INFO_FLAG_EN_PULLUP 0x01  // VIM3 supply survives MCU resets (R72 is a pull-up)

enum { MCU_RESET_POWER_ON = 0, MCU_RESET_WATCHDOG = 1, MCU_RESET_HOST = 2, MCU_RESET_OTHER = 3 };

typedef struct __attribute__((packed)) {
    uint8_t type;   // MCU_MSG_LOG
    uint8_t len;
    char text[62];
} mcu_log_msg_t;

typedef struct __attribute__((packed)) {
    uint8_t type;   // MCU_MSG_HOST_HELLO
    uint8_t proto_version;
    uint8_t reserved[2];
    uint32_t host_uptime_s;
} mcu_hello_msg_t;

// One complete ECU answer from the K-line module, undecoded: data[0] is the command the MCU
// sent (= the ECU's echo of it), then the ECU's response bytes. For the MEMS 1.x data frames
// (0x80, 0x7D) data[1] is the frame length including itself, so len = data[1] + 1. The VHAL
// decodes it; the firmware only does the transport, so a decoding fix needs no MCU update.
#define MCU_KLINE_FRAME_MAX 56

typedef struct __attribute__((packed)) {
    uint8_t type;      // MCU_MSG_KLINE_FRAME
    uint8_t seq;       // increments per frame (gaps = frames dropped on the MCU)
    uint8_t len;       // valid bytes in data
    uint8_t ecu;       // MCU_KLINE_ECU_*
    uint32_t t_ms;     // MCU clock when the last byte arrived
    uint8_t data[MCU_KLINE_FRAME_MAX];
} mcu_kline_frame_msg_t;

enum { MCU_KLINE_ECU_MEMS19 = 1 };

#define MCU_BOOTSEL_MAGIC 0xB007CAFEu

typedef struct __attribute__((packed)) {
    uint8_t type;   // MCU_MSG_HOST_BOOTSEL
    uint8_t reserved[3];
    uint32_t magic; // MCU_BOOTSEL_MAGIC
} mcu_bootsel_msg_t;

// ---- Property IDs ----
// Standard VHAL properties the link carries (values as in VehicleProperty.aidl).
#define MCU_PROP_PERF_VEHICLE_SPEED    0x11600207  // float m/s, from GNSS (MCU -> host)
#define MCU_PROP_GEAR_SELECTION        0x11400400  // VehicleGear: REVERSE or PARK (MCU -> host)
#define MCU_PROP_NIGHT_MODE            0x11200407  // illumination input (MCU -> host)
#define MCU_PROP_IGNITION_STATE        0x11400409  // VehicleIgnitionState: ON or OFF (MCU -> host)
#define MCU_PROP_AP_POWER_STATE_REQ    0x11410A00  // {VehicleApPowerStateReq, param} (MCU -> host)
#define MCU_PROP_AP_POWER_STATE_REPORT 0x11410A01  // {VehicleApPowerStateReport, param} (host -> MCU)
#define MCU_PROP_DISPLAY_BRIGHTNESS    0x11400A03  // 0..100 (host -> MCU, echoed back)

// Vendor properties (VENDOR | GLOBAL | type | id).
#define MCU_PROP_SCREEN_POWER    0x21400555  // 0/1 backlight on. Both ways (screen button, VHAL)
#define MCU_PROP_BATTERY_MV      0x21400600  // battery voltage at ISO A4, mV
#define MCU_PROP_RAIL_5V_MV      0x21400601  // +5V_SYS (VIM3/screen supply), mV
#define MCU_PROP_BOARD_TEMP      0x21400602  // board temperature (NTC TH1), 0.1 degC
#define MCU_PROP_LUX             0x21400603  // BH1750 light level, lux; -1 = no sensor
#define MCU_PROP_AMP_MODE        0x21400604  // RW: 0 off, 1 on, 2 auto (default)
#define MCU_PROP_AMP_ON          0x21400605  // amp remote output state
#define MCU_PROP_AUDIO_MUTE      0x21400606  // RW: host mute request for the DACs
#define MCU_PROP_INPUTS          0x21400607  // MCU_IN_* bitmask, debounced
#define MCU_PROP_STATUS          0x21400608  // MCU_ST_* bitmask
#define MCU_PROP_POWER_STATE     0x21400609  // mcu_power_state_t
#define MCU_PROP_OFF_DELAY_S     0x2140060A  // RW: suspend -> full power off delay, seconds
#define MCU_PROP_GNSS_CMD        0x2140060B  // W: MCU_GNSS_CMD_*
#define MCU_PROP_GNSS_FIX        0x2141060C  // INT32_VEC {fix 0/1, satellites used}
// INT32_VEC {PPS count, microseconds from the GNSS PPS rising edge to the moment the
// report was queued on the USB endpoint} (MCU -> host). Sent as its own report ahead of
// everything else, once per pulse. The host subtracts v1 from its read() timestamp
// (plus up to one 1 ms USB frame) to date the top of the UTC second. Not a VHAL property.
#define MCU_PROP_GNSS_PPS        0x2141060D
#define MCU_PROP_SUSPEND_SAVE    0x2140060E  // RW: MCU_SAVE_* bits, extra power savings in suspend (default 0)
#define MCU_PROP_TPS_MODE        0x2140060F  // R: TPS55288 MODE register (06h), raw
// K-line module (J10). INT32_VEC {MCU_KLINE_ST_*, ECU id (the 4 bytes after 0xD0, little endian)}
#define MCU_PROP_KLINE_STATE     0x21410610
#define MCU_PROP_KLINE_MODE      0x21400611  // RW: 0 off, 1 auto (default: poll while ACC is on)
#define MCU_PROP_KLINE_CMD       0x21400612  // W: MCU_KLINE_CMD_*

#define MCU_PROP_IS_FLOAT(p) (((p) & 0x00FF0000u) == 0x00600000u)

// MCU_PROP_INPUTS bits
#define MCU_IN_ACC        (1u << 0)
#define MCU_IN_REVERSE    (1u << 1)
#define MCU_IN_ILLUM      (1u << 2)
#define MCU_IN_HANDBRAKE  (1u << 3)  // reads 0 when the wire is not connected
#define MCU_IN_SBC_ON     (1u << 4)  // VIM3 3.3V rail present
#define MCU_IN_SERVICE    (1u << 5)  // service jumper JP1 fitted
#define MCU_IN_BTN_SCREEN (1u << 8)
#define MCU_IN_BTN_VOLUP  (1u << 9)
#define MCU_IN_BTN_VOLDN  (1u << 10)
#define MCU_IN_BTN_MUTE   (1u << 11)

// MCU_PROP_SUSPEND_SAVE bits (from SUSPEND_SAVE_AFTER_MS into a suspend, undone when it ends)
#define MCU_SAVE_HUB_PARK    (1u << 0)   // hold hub 1 in reset (this MCU's USB, touch, GNSS, hub 2)
#define MCU_SAVE_TPS_PFM     (1u << 1)   // TPS55288 PFM at light load instead of forced PWM

// MCU_PROP_STATUS bits
#define MCU_ST_USBP_PG       (1u << 0)   // phone-port 5V supply power good
#define MCU_ST_USBP_FAULT1   (1u << 1)   // phone port 1 over-current
#define MCU_ST_USBP_FAULT2   (1u << 2)   // phone port 2 over-current
#define MCU_ST_BB_PRESENT    (1u << 3)   // TPS55288 answers on I2C
#define MCU_ST_BB_SCP        (1u << 4)   // TPS55288 short-circuit flag
#define MCU_ST_BB_OCP        (1u << 5)   // TPS55288 over-current flag
#define MCU_ST_BB_OVP        (1u << 6)   // TPS55288 over-voltage flag
#define MCU_ST_LUX_PRESENT   (1u << 7)   // BH1750 answers on I2C
#define MCU_ST_GNSS_POWER    (1u << 8)   // GNSS supply on
#define MCU_ST_GNSS_NMEA     (1u << 9)   // valid NMEA seen in the last 3 s
#define MCU_ST_EN_PULLUP     (1u << 10)  // R72 fitted as a pull-up
#define MCU_ST_LOW_BATTERY   (1u << 11)
#define MCU_ST_HOT           (1u << 12)  // board above the derating temperature
#define MCU_ST_DAC_UNMUTED   (1u << 13)

enum {
    MCU_KLINE_ST_OFF = 0,        // mode off or ACC off: module unpowered
    MCU_KLINE_ST_WAKING = 1,     // 5-baud wake-up / init in progress
    MCU_KLINE_ST_CONNECTED = 2,  // session up, frames flowing
    MCU_KLINE_ST_RETRY = 3,      // no answer (ECU off, no module, wiring): waiting to retry
};

enum { MCU_KLINE_CMD_CLEAR_FAULTS = 1 };  // send 0xCC once in the running session

typedef enum {
    MCU_PWR_OFF = 0,          // VIM3 unpowered, waiting for ACC
    MCU_PWR_BOOTING = 1,      // VIM3 supply on, waiting for its 3.3V rail
    MCU_PWR_RUNNING = 2,      // VIM3 running, ACC on
    MCU_PWR_SHUTDOWN_PREP = 3,// ACC off, Android asked to prepare for sleep
    MCU_PWR_SUSPENDED = 4,    // Android in suspend-to-RAM, VIM3 still powered
    MCU_PWR_WAKING = 5,       // power key pressed, waiting for Android
    MCU_PWR_SHUTTING_DOWN = 6,// Android shutting down, power cut when its rail drops
    MCU_PWR_LATCHED_OFF = 7,  // VIM3 was shut down with ACC on; waits for ACC off
} mcu_power_state_t;

enum {
    MCU_GNSS_CMD_RESET = 1,        // pulse RESET_N
    MCU_GNSS_CMD_POWER_CYCLE = 2,  // supply off for 1 s
    MCU_GNSS_CMD_SAFEBOOT = 3,     // power cycle with SAFEBOOT_N low (firmware recovery)
    MCU_GNSS_CMD_NORMAL = 4,       // leave safeboot: power cycle with SAFEBOOT_N released
};

#ifdef __cplusplus
}
#define MCU_STATIC_ASSERT static_assert
#else
#define MCU_STATIC_ASSERT _Static_assert
#endif

MCU_STATIC_ASSERT(sizeof(mcu_prop_t) == 12, "mcu_prop_t layout");
MCU_STATIC_ASSERT(sizeof(mcu_props_msg_t) == MCU_REPORT_SIZE, "mcu_props_msg_t layout");
MCU_STATIC_ASSERT(sizeof(mcu_info_msg_t) == MCU_REPORT_SIZE, "mcu_info_msg_t layout");
MCU_STATIC_ASSERT(sizeof(mcu_log_msg_t) == MCU_REPORT_SIZE, "mcu_log_msg_t layout");
MCU_STATIC_ASSERT(sizeof(mcu_hello_msg_t) <= MCU_REPORT_SIZE, "mcu_hello_msg_t layout");
MCU_STATIC_ASSERT(sizeof(mcu_bootsel_msg_t) <= MCU_REPORT_SIZE, "mcu_bootsel_msg_t layout");
MCU_STATIC_ASSERT(sizeof(mcu_kline_frame_msg_t) == MCU_REPORT_SIZE, "mcu_kline_frame_msg_t layout");

#endif  // MCU_PROTOCOL_H
