// Decoder for Rover MEMS 1.x data frames (MEMS 1.9 in the MG F), as forwarded raw by the MCU
// (MCU_MSG_KLINE_FRAME). Field layout from rover-mems-documentation, ECUs/1.x-ECU-all/diagnostics:
// the documented offset k (0 = the length byte) is frame[k + 1], because frame[0] is the
// command echo. Scalings marked (unverified) still have to be confirmed against car captures.
//
// The decoded values travel to apps as one FLOAT_VEC vendor property, VENDOR_MEMS_LIVE, laid out
// by MemsField. Keep the order stable: CarStatus reads it by index (MemsFields.java).
#pragma once

#include <cstddef>
#include <cstdint>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

enum MemsField : int {
    // frame 0x80
    MEMS_RPM = 0,
    MEMS_COOLANT_C,
    MEMS_AMBIENT_C,
    MEMS_INTAKE_AIR_C,
    MEMS_FUEL_RAIL_C,      // NaN when the ECU reports 0xFF (no sensor)
    MEMS_MAP_KPA,
    MEMS_BATTERY_V,
    MEMS_THROTTLE_V,
    MEMS_IDLE_SWITCH,      // 1 = throttle closed
    MEMS_FAULTS_1,         // byte 0x0D bits (bit 0 coolant sensor, bit 1 intake air sensor, ...)
    MEMS_FAULTS_2,         // byte 0x0E bits (bit 1 fuel pump circuit, bit 7 throttle pot, ...)
    MEMS_IDLE_SET_RPM,
    MEMS_IAC_STEPS,
    MEMS_IGNITION_ADV_DEG, // (unverified)
    MEMS_COIL_MS,
    // frame 0x7D
    MEMS_THROTTLE_DEG,
    MEMS_LAMBDA_MV,        // (unverified: docs say 0.5 mV/LSB, the agent uses 5 mV/LSB)
    MEMS_LAMBDA_STATUS,
    MEMS_CLOSED_LOOP,
    MEMS_FUEL_TRIM,
    MEMS_IDLE_POS,
    MEMS_FAN1,
    MEMS_FAN2,
    MEMS_FIELD_COUNT
};

struct MemsValues {
    float v[MEMS_FIELD_COUNT];
    bool have80 = false;
    bool have7d = false;
    MemsValues();
};

// Decode one frame (command echo first) into `out`. Returns false for frames that are not
// 0x80/0x7D or are shorter than the fields we read; fields beyond a short frame keep their value.
bool memsDecode(const uint8_t* frame, size_t len, MemsValues* out);

// Temperature byte: degC + 55 offset.
inline float memsTempC(uint8_t b) { return static_cast<float>(b) - 55.0f; }

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android
