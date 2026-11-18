#include "MemsDecoder.h"

#include <cmath>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

MemsValues::MemsValues() {
    for (float& f : v) f = NAN;
}

bool memsDecode(const uint8_t* f, size_t len, MemsValues* out) {
    if (len < 2) return false;
    // f[0] command echo, f[1] length byte (documented offset 0), so offset k = f[k + 1]
    size_t n = len;
    if (static_cast<size_t>(f[1]) + 1 < n) n = static_cast<size_t>(f[1]) + 1;
    auto has = [&](int docOffset) { return static_cast<size_t>(docOffset) + 1 < n; };
    auto at = [&](int docOffset) { return f[docOffset + 1]; };
    float* v = out->v;

    if (f[0] == 0x80) {
        if (!has(0x08)) return false;  // up to the battery voltage at least
        v[MEMS_RPM] = static_cast<float>(at(0x01) << 8 | at(0x02));
        v[MEMS_COOLANT_C] = memsTempC(at(0x03));
        v[MEMS_AMBIENT_C] = memsTempC(at(0x04));
        v[MEMS_INTAKE_AIR_C] = memsTempC(at(0x05));
        v[MEMS_FUEL_RAIL_C] = at(0x06) == 0xFF ? NAN : memsTempC(at(0x06));
        v[MEMS_MAP_KPA] = at(0x07);
        v[MEMS_BATTERY_V] = at(0x08) * 0.1f;
        if (has(0x09)) v[MEMS_THROTTLE_V] = at(0x09) * 0.02f;
        if (has(0x0A)) v[MEMS_IDLE_SWITCH] = (at(0x0A) >> 4) & 1;
        if (has(0x0D)) v[MEMS_FAULTS_1] = at(0x0D);
        if (has(0x0E)) v[MEMS_FAULTS_2] = at(0x0E);
        if (has(0x0F)) v[MEMS_IDLE_SET_RPM] = at(0x0F) * 6.1f;
        if (has(0x12)) v[MEMS_IAC_STEPS] = at(0x12);
        if (has(0x16)) v[MEMS_IGNITION_ADV_DEG] = at(0x16) * 0.5f - 24.0f;
        if (has(0x18)) v[MEMS_COIL_MS] = static_cast<float>(at(0x17) << 8 | at(0x18)) * 0.002f;
        out->have80 = true;
        return true;
    }
    if (f[0] == 0x7D) {
        if (!has(0x0A)) return false;
        v[MEMS_THROTTLE_DEG] = at(0x02) * 0.5f;
        v[MEMS_FAN1] = (at(0x05) >> 5) & 1;
        v[MEMS_FAN2] = (at(0x05) >> 7) & 1;
        v[MEMS_LAMBDA_MV] = at(0x06) * 5.0f;
        v[MEMS_LAMBDA_STATUS] = at(0x09);
        v[MEMS_CLOSED_LOOP] = at(0x0A) ? 1.0f : 0.0f;
        if (has(0x0C)) v[MEMS_FUEL_TRIM] = at(0x0C);
        if (has(0x0F)) v[MEMS_IDLE_POS] = at(0x0F);
        out->have7d = true;
        return true;
    }
    return false;
}

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android
