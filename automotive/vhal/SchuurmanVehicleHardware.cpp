#include "SchuurmanVehicleHardware.h"

#include <aidl/android/hardware/automotive/vehicle/FuelType.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleApPowerStateConfigFlag.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleApPowerStateReport.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleApPowerStateReq.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleApPowerStateShutdownParam.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleArea.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleGear.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleIgnitionState.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleProperty.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyAccess.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyChangeMode.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleSeatOccupancyState.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleUnit.h>

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android-base/stringprintf.h>

#include <algorithm>
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <string>
#include <thread>
#include <vector>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

using ::aidl::android::hardware::automotive::vehicle::FuelType;
using ::aidl::android::hardware::automotive::vehicle::VehicleApPowerStateConfigFlag;
using ::aidl::android::hardware::automotive::vehicle::VehicleApPowerStateReport;
using ::aidl::android::hardware::automotive::vehicle::VehicleApPowerStateReq;
using ::aidl::android::hardware::automotive::vehicle::VehicleApPowerStateShutdownParam;
using ::aidl::android::hardware::automotive::vehicle::VehicleArea;
using ::aidl::android::hardware::automotive::vehicle::VehicleGear;
using ::aidl::android::hardware::automotive::vehicle::VehicleUnit;
using ::aidl::android::hardware::automotive::vehicle::VehicleIgnitionState;
using ::aidl::android::hardware::automotive::vehicle::VehicleProperty;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyAccess;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyChangeMode;
using ::aidl::android::hardware::automotive::vehicle::VehicleSeatOccupancyState;

static const int32_t VENDOR_AUTO_BRIGHTNESS = 0x12000001;
static const int32_t VENDOR_SCREEN_POWER = MCU_PROP_SCREEN_POWER;  // 0x21400555
// VENDOR | GLOBAL | STRING: MCU firmware version and build, read-only.
static const int32_t VENDOR_MCU_FW_VERSION = 0x2110060D;

// SYSTEM | GLOBAL | STRING — VHAL → CarPowerPolicyService
static const int32_t POWER_POLICY_REQ       = 0x11100F21;
static const int32_t POWER_POLICY_GROUP_REQ = 0x11100F22;

static constexpr int32_t GLOBAL_AREA_ID = 0;
static constexpr int32_t DRIVER_SEAT_ID = 1;

// Publish AP_POWER_STATE_REQ ON ourselves if Android waits for us and the MCU does not
// answer within this time (MCU missing, old firmware, or link trouble).
static constexpr int64_t kFallbackOnNs = 10'000'000'000LL;

// Handbrake from GNSS speed: parked below 0.5 m/s for 3 s, moving above 2 m/s.
static constexpr float kParkedBelowMps = 0.5f;
static constexpr float kMovingAboveMps = 2.0f;
static constexpr int64_t kParkedAfterNs = 3'000'000'000LL;

// MCU vendor properties exposed to Android: {property, writable}.
struct McuVendorProp {
    int32_t prop;
    bool writable;
};
static const McuVendorProp kMcuVendorProps[] = {
        {static_cast<int32_t>(MCU_PROP_BATTERY_MV), false},
        {static_cast<int32_t>(MCU_PROP_RAIL_5V_MV), false},
        {static_cast<int32_t>(MCU_PROP_BOARD_TEMP), false},
        {static_cast<int32_t>(MCU_PROP_LUX), false},
        {static_cast<int32_t>(MCU_PROP_AMP_MODE), true},
        {static_cast<int32_t>(MCU_PROP_AMP_ON), false},
        {static_cast<int32_t>(MCU_PROP_AUDIO_MUTE), true},
        {static_cast<int32_t>(MCU_PROP_INPUTS), false},
        {static_cast<int32_t>(MCU_PROP_STATUS), false},
        {static_cast<int32_t>(MCU_PROP_POWER_STATE), false},
        {static_cast<int32_t>(MCU_PROP_OFF_DELAY_S), true},
        {static_cast<int32_t>(MCU_PROP_GNSS_CMD), true},
        {static_cast<int32_t>(MCU_PROP_GNSS_FIX), false},
};

static bool isMcuVendorProp(int32_t prop) {
    for (const auto& p : kMcuVendorProps)
        if (p.prop == prop) return true;
    return false;
}

static bool isVecProp(int32_t prop) {
    return (static_cast<uint32_t>(prop) & 0x00FF0000u) == 0x00410000u;
}

static int64_t elapsedRealtimeNano() {
    auto now = std::chrono::steady_clock::now();
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
                   now.time_since_epoch())
            .count();
}

static std::string readSysFsString(const std::string& path, int retries = 3,
                                   int delayMs = 50) {
    for (int i = 0; i < retries; ++i) {
        std::ifstream file(path);
        if (file) {
            std::string s;
            if (std::getline(file, s)) {
                return s;
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(delayMs));
    }
    return std::string();
}

static constexpr char kDistanceUnitsProp[] = "persist.vendor.vehicle.distance_units";
static constexpr char kTemperatureUnitsProp[] = "persist.vendor.vehicle.temperature_units";
static constexpr char kFuelVolumeUnitsProp[] = "persist.vendor.vehicle.fuel_volume_units";
static constexpr char kHandbrakeModeProp[] = "persist.vendor.vehicle.handbrake";
static constexpr char kHandbrakeSeenProp[] = "persist.vendor.vehicle.handbrake_seen";
static constexpr char kAmpModeProp[] = "persist.vendor.vehicle.amp_mode";
static constexpr char kOffDelayProp[] = "persist.vendor.vehicle.off_delay_s";
static constexpr char kLuxMaxProp[] = "ro.vendor.vehicle.lux_max";

static const std::vector<int32_t> kDistanceUnits = {
        static_cast<int32_t>(VehicleUnit::KILOMETER), static_cast<int32_t>(VehicleUnit::MILE)};
static const std::vector<int32_t> kTemperatureUnits = {
        static_cast<int32_t>(VehicleUnit::CELSIUS), static_cast<int32_t>(VehicleUnit::FAHRENHEIT)};
static const std::vector<int32_t> kFuelVolumeUnits = {
        static_cast<int32_t>(VehicleUnit::LITER), static_cast<int32_t>(VehicleUnit::US_GALLON),
        static_cast<int32_t>(VehicleUnit::IMPERIAL_GALLON)};

SchuurmanVehicleHardware::SchuurmanVehicleHardware()
    : mCurrentGear(static_cast<int32_t>(VehicleGear::GEAR_PARK)),
      mCurrentBrightness(50),
      mLastNonZeroBrightness(50),
      mScreenOn(true),
      mIgnitionState(static_cast<int32_t>(VehicleIgnitionState::ON)),
      mParkingBrakeOn(1),
      mNightMode(0),
      mSpeed(0.0f),
      mLux(-1),
      mHandbrakeRaw(false),
      mHandbrakeSeen(android::base::GetBoolProperty(kHandbrakeSeenProp, false)),
      mGnssStationary(true),
      mDistanceUnits(android::base::GetIntProperty(kDistanceUnitsProp,
              static_cast<int32_t>(VehicleUnit::KILOMETER))),
      mTemperatureUnits(android::base::GetIntProperty(kTemperatureUnitsProp,
              static_cast<int32_t>(VehicleUnit::CELSIUS))),
      mFuelVolumeUnits(android::base::GetIntProperty(kFuelVolumeUnitsProp,
              static_cast<int32_t>(VehicleUnit::LITER))),
      mShuttingDown(false),
      mAutoBrightnessEnabled(false),
      mAutoTargetBrightness(-1),
      mDisplayThreadRunning(false),
      mTouchWakeThreadRunning(false),
      mTapToWakeSuppressed(false),
      mPausedForPower(false),
      mLastApPowerStateReq(static_cast<int32_t>(VehicleApPowerStateReq::ON)),
      mLastApPowerStateReqParam(0),
      mLastApPowerStateReport(static_cast<int32_t>(VehicleApPowerStateReport::ON)),
      mLastApPowerStateReportParam(0),
      mReportPending(false),
      mFallbackOnAtNs(0),
      mCurrentPolicyGroup("default_group"),
      mCurrentPolicyReq("") {
    LOG(INFO) << "Initializing SchuurmanVehicleHardware (MCU link, protocol "
              << MCU_PROTO_VERSION << ")";

    mHousekeepingThread = std::thread(&SchuurmanVehicleHardware::housekeepingLoop, this);

    mDisplayDpmsPath = findDisplayDpmsPath();
    if (!mDisplayDpmsPath.empty()) {
        mDisplayThreadRunning.store(true);
        mDisplayThread = std::thread(&SchuurmanVehicleHardware::displayStateLoop, this);
    } else {
        LOG(WARNING) << "Display DPMS path not found - backlight won't track display sleep";
    }

    mTouchWakeThreadRunning.store(true);
    mTouchWakeThread = std::thread(&SchuurmanVehicleHardware::touchWakeLoop, this);

    mMcu.start([this](const std::vector<mcu_prop_t>& p, bool s) { onMcuProps(p, s); },
               [this](const mcu_info_msg_t& info) { onMcuInfo(info); },
               [this](bool c) { onMcuConnect(c); });
}

SchuurmanVehicleHardware::~SchuurmanVehicleHardware() {
    mShuttingDown.store(true);
    mMcu.stop();
    if (mHousekeepingThread.joinable()) mHousekeepingThread.join();

    mDisplayThreadRunning.store(false);
    if (mDisplayThread.joinable()) mDisplayThread.join();

    mTouchWakeThreadRunning.store(false);
    if (mTouchWakeThread.joinable()) mTouchWakeThread.join();
}

void SchuurmanVehicleHardware::emitPropChange(const VehiclePropValue& v) {
    std::lock_guard<std::mutex> lk(mCallbackMutex);
    if (!mOnPropChange) return;
    std::vector<VehiclePropValue> events;
    events.push_back(v);
    (*mOnPropChange)(events);
}

void SchuurmanVehicleHardware::emitInts(int32_t propId, const std::vector<int32_t>& values) {
    VehiclePropValue v;
    v.prop = propId;
    v.areaId = GLOBAL_AREA_ID;
    v.timestamp = elapsedRealtimeNano();
    v.value.int32Values = values;
    emitPropChange(v);
}

void SchuurmanVehicleHardware::emitInt(int32_t propId, int32_t value) {
    emitInts(propId, {value});
}

void SchuurmanVehicleHardware::emitInitialStatesLocked() {
    if (!mOnPropChange) return;

    std::vector<VehiclePropValue> events;

    auto addIntEvent = [&](int32_t propId, int32_t areaId, int32_t value) {
        VehiclePropValue v;
        v.prop = propId;
        v.areaId = areaId;
        v.timestamp = elapsedRealtimeNano();
        v.value.int32Values = {value};
        events.push_back(v);
    };

    addIntEvent(static_cast<int32_t>(VehicleProperty::GEAR_SELECTION),
                GLOBAL_AREA_ID, mCurrentGear.load());

    {
        VehiclePropValue v;
        v.prop = static_cast<int32_t>(VehicleProperty::PERF_VEHICLE_SPEED);
        v.areaId = GLOBAL_AREA_ID;
        v.timestamp = elapsedRealtimeNano();
        v.value.floatValues = {mSpeed.load()};
        events.push_back(v);
    }

    addIntEvent(static_cast<int32_t>(VehicleProperty::IGNITION_STATE),
                GLOBAL_AREA_ID, mIgnitionState.load());
    addIntEvent(static_cast<int32_t>(VehicleProperty::PARKING_BRAKE_ON),
                GLOBAL_AREA_ID, mParkingBrakeOn.load());
    addIntEvent(static_cast<int32_t>(VehicleProperty::NIGHT_MODE),
                GLOBAL_AREA_ID, mNightMode.load());
    addIntEvent(static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS),
                GLOBAL_AREA_ID, mCurrentBrightness.load());
    addIntEvent(VENDOR_AUTO_BRIGHTNESS, GLOBAL_AREA_ID,
                mAutoBrightnessEnabled.load() ? 1 : 0);
    addIntEvent(VENDOR_SCREEN_POWER, GLOBAL_AREA_ID,
                mScreenOn.load() ? 1 : 0);
    addIntEvent(static_cast<int32_t>(VehicleProperty::SEAT_OCCUPANCY),
                DRIVER_SEAT_ID,
                static_cast<int32_t>(VehicleSeatOccupancyState::OCCUPIED));

    // Tell CarPowerPolicyService which policy group to use (defined in power_policy.xml).
    {
        VehiclePropValue v;
        v.prop = POWER_POLICY_GROUP_REQ;
        v.areaId = GLOBAL_AREA_ID;
        v.timestamp = elapsedRealtimeNano();
        v.value.stringValue = mCurrentPolicyGroup;
        events.push_back(v);
    }

    // Last request from the MCU (ON until it says otherwise).
    {
        VehiclePropValue v;
        v.prop = static_cast<int32_t>(VehicleProperty::AP_POWER_STATE_REQ);
        v.areaId = GLOBAL_AREA_ID;
        v.timestamp = elapsedRealtimeNano();
        v.value.int32Values = {
                mLastApPowerStateReq.load(),
                mLastApPowerStateReqParam.load()};
        events.push_back(v);
    }

    (*mOnPropChange)(events);
}

// ---------------------------------------------------------------- MCU link

void SchuurmanVehicleHardware::onMcuConnect(bool connected) {
    if (!connected) {
        LOG(INFO) << "MCU disconnected (VIM3 suspend, MCU restart or unplugged)";
        return;
    }
    pushSettingsToMcu();
    if (mReportPending.exchange(false)) {
        // Android reported while the link was down (typically DEEP_SLEEP_EXIT or
        // WAIT_FOR_VHAL right after resume): the MCU answers with AP_POWER_STATE_REQ.
        mMcu.set(MCU_PROP_AP_POWER_STATE_REPORT, mLastApPowerStateReport.load(),
                 mLastApPowerStateReportParam.load());
    }
}

void SchuurmanVehicleHardware::pushSettingsToMcu() {
    int brightness = mLastNonZeroBrightness.load();
    if (brightness <= 0) brightness = 50;
    std::vector<mcu_prop_t> props = {
            {MCU_PROP_DISPLAY_BRIGHTNESS, brightness, 0},
            {MCU_PROP_AMP_MODE, android::base::GetIntProperty(kAmpModeProp, 2, 0, 2), 0},
            {MCU_PROP_OFF_DELAY_S, android::base::GetIntProperty(kOffDelayProp, 15 * 60, 0,
                                                                 7 * 24 * 3600), 0},
    };
    mMcu.set(props);
}

void SchuurmanVehicleHardware::onMcuInfo(const mcu_info_msg_t& info) {
    std::string v = android::base::StringPrintf("%u.%u.%u (%s) board rev 0.%u proto %u%s",
                                                info.fw_major, info.fw_minor, info.fw_patch,
                                                info.build, info.board_rev, info.proto_version,
                                                (info.flags & MCU_INFO_FLAG_EN_PULLUP)
                                                        ? ""
                                                        : ", R72 pull-down");
    LOG(INFO) << "MCU firmware " << v << ", reset reason " << int(info.reset_reason)
              << ", up " << info.uptime_s << " s";
    if (info.proto_version != MCU_PROTO_VERSION) {
        LOG(ERROR) << "MCU protocol " << int(info.proto_version) << " != VHAL protocol "
                   << MCU_PROTO_VERSION << "; update the MCU firmware or the VHAL";
    }
    std::lock_guard<std::mutex> lk(mMcuMutex);
    mMcuVersion = v;
    mMcuEnPullup = info.flags & MCU_INFO_FLAG_EN_PULLUP;
}

void SchuurmanVehicleHardware::onMcuProps(const std::vector<mcu_prop_t>& props, bool snapshot) {
    for (const auto& p : props) {
        const int32_t prop = static_cast<int32_t>(p.prop);
        switch (p.prop) {
            case MCU_PROP_GEAR_SELECTION:
                if (mCurrentGear.exchange(p.v0) != p.v0 || snapshot) {
                    LOG(INFO) << "Gear " << p.v0;
                    emitInt(prop, p.v0);
                }
                break;
            case MCU_PROP_IGNITION_STATE:
                if (mIgnitionState.exchange(p.v0) != p.v0 || snapshot) emitInt(prop, p.v0);
                break;
            case MCU_PROP_NIGHT_MODE:
                if (mNightMode.exchange(p.v0 ? 1 : 0) != (p.v0 ? 1 : 0) || snapshot)
                    emitInt(prop, p.v0 ? 1 : 0);
                break;
            case MCU_PROP_PERF_VEHICLE_SPEED: {
                float speed;
                memcpy(&speed, &p.v0, sizeof(speed));
                mSpeed.store(speed);
                VehiclePropValue v;
                v.prop = prop;
                v.areaId = GLOBAL_AREA_ID;
                v.timestamp = elapsedRealtimeNano();
                v.value.floatValues = {speed};
                emitPropChange(v);
                updateParkingBrake(false);
                break;
            }
            case MCU_PROP_AP_POWER_STATE_REQ:
                mFallbackOnAtNs.store(0);
                if (p.v0 == static_cast<int32_t>(VehicleApPowerStateReq::SHUTDOWN_PREPARE)) {
                    // ACC off: pause media and keep stray touches from waking the screen.
                    mTapToWakeSuppressed.store(true);
                    if (!mPausedForPower.exchange(true)) injectMediaKey(KEY_PAUSECD);
                } else if (p.v0 == static_cast<int32_t>(VehicleApPowerStateReq::ON) ||
                           p.v0 == static_cast<int32_t>(VehicleApPowerStateReq::CANCEL_SHUTDOWN)) {
                    if (mPausedForPower.exchange(false)) injectMediaKey(KEY_PLAYCD);
                }
                publishApPowerStateReq(p.v0, p.v1);
                break;
            case MCU_PROP_SCREEN_POWER: {
                // The display button toggles the backlight on the MCU. Mirror it without
                // writing back (the MCU echoes our own writes too, which are no-ops here).
                bool on = p.v0 != 0;
                if (mScreenOn.load() != on) {
                    LOG(INFO) << "Screen " << (on ? "on" : "off") << " (MCU)";
                    mScreenOn.store(on);
                    if (on) {
                        mTapToWakeSuppressed.store(false);
                        mCurrentBrightness.store(mLastNonZeroBrightness.load());
                        publishCurrentBrightness();
                    } else {
                        if (mCurrentBrightness.load() > 0)
                            mLastNonZeroBrightness.store(mCurrentBrightness.load());
                        mCurrentBrightness.store(0);
                    }
                    publishVendorScreenPower();
                }
                break;
            }
            case MCU_PROP_DISPLAY_BRIGHTNESS:
                break;  // echo of our own write
            case MCU_PROP_LUX:
                mLux.store(p.v0);
                break;
            case MCU_PROP_INPUTS: {
                bool raw = p.v0 & MCU_IN_HANDBRAKE;
                mHandbrakeRaw.store(raw);
                if (raw && !mHandbrakeSeen.exchange(true)) {
                    LOG(INFO) << "Handbrake wire seen engaged: using it from now on";
                    android::base::SetProperty(kHandbrakeSeenProp, "1");
                }
                updateParkingBrake(snapshot);
                break;
            }
            default:
                break;
        }

        if (isMcuVendorProp(prop)) {
            bool changed;
            {
                std::lock_guard<std::mutex> lk(mMcuMutex);
                auto it = mMcuValues.find(prop);
                changed = it == mMcuValues.end() || it->second != std::make_pair(p.v0, p.v1);
                mMcuValues[prop] = {p.v0, p.v1};
            }
            if (changed || snapshot) {
                if (isVecProp(prop)) emitInts(prop, {p.v0, p.v1});
                else emitInt(prop, p.v0);
            }
        }
    }
}

void SchuurmanVehicleHardware::updateParkingBrake(bool force) {
    const std::string mode = android::base::GetProperty(kHandbrakeModeProp, "auto");
    bool wired = mode == "wired" || (mode == "auto" && mHandbrakeSeen.load());

    // GNSS speed with hysteresis, see kParkedBelowMps.
    const float speed = mSpeed.load();
    const int64_t now = elapsedRealtimeNano();
    if (speed > kMovingAboveMps) {
        mGnssStationary.store(false);
        mSlowSinceNs = 0;
    } else if (speed < kParkedBelowMps) {
        int64_t expected = 0;
        mSlowSinceNs.compare_exchange_strong(expected, now);
        if (now - mSlowSinceNs.load() >= kParkedAfterNs) mGnssStationary.store(true);
    } else {
        mSlowSinceNs = 0;
    }

    int32_t on = (wired ? mHandbrakeRaw.load() : mGnssStationary.load()) ? 1 : 0;
    if (mParkingBrakeOn.exchange(on) != on || force) {
        LOG(INFO) << "Parking brake " << on << " (" << (wired ? "wire" : "GNSS speed") << ")";
        emitInt(static_cast<int32_t>(VehicleProperty::PARKING_BRAKE_ON), on);
    }
}

void SchuurmanVehicleHardware::housekeepingLoop() {
    double ema = -1.0;
    const double alpha = 0.25;
    const int maxLux = android::base::GetIntProperty(kLuxMaxProp, 100000);

    while (!mShuttingDown.load()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(250));

        // Fallback: Android waits for an AP_POWER_STATE_REQ but the MCU does not answer.
        int64_t at = mFallbackOnAtNs.load();
        if (at != 0 && elapsedRealtimeNano() >= at) {
            mFallbackOnAtNs.store(0);
            LOG(WARNING) << "No answer from the MCU, publishing AP_POWER_STATE_REQ ON";
            publishApPowerStateReq(static_cast<int32_t>(VehicleApPowerStateReq::ON));
        }

        updateParkingBrake(false);

        // Auto brightness from the MCU's light sensor.
        int raw = mLux.load();
        if (raw < 0) continue;
        ema = ema < 0 ? raw : alpha * raw + (1.0 - alpha) * ema;
        double percent = (log(1.0 + ema) / log(1.0 + std::max(1, maxLux))) * 100.0;
        int intPercent = static_cast<int>(std::clamp(percent, 0.0, 100.0) + 0.5);
        if (intPercent < 1) intPercent = 1;  // 0 % on this panel is still lit, keep it usable

        if (mAutoBrightnessEnabled.load()) {
            int last = mAutoTargetBrightness.load();
            if (last < 0 || std::abs(intPercent - last) >= 2) {
                mAutoTargetBrightness.store(intPercent);
                if (mScreenOn.load()) {
                    mLastNonZeroBrightness.store(intPercent);
                    sendBrightness(intPercent);
                    mCurrentBrightness.store(intPercent);
                    publishCurrentBrightness();
                }
            }
        }
    }
}

// ---------------------------------------------------------------- display

void SchuurmanVehicleHardware::sendBrightness(int percentage) {
    percentage = std::clamp(percentage, 0, 100);
    mMcu.set(MCU_PROP_DISPLAY_BRIGHTNESS, percentage);
}

void SchuurmanVehicleHardware::publishCurrentBrightness() {
    emitInt(static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS), mCurrentBrightness.load());
}

void SchuurmanVehicleHardware::publishVendorScreenPower() {
    emitInt(VENDOR_SCREEN_POWER, mScreenOn.load() ? 1 : 0);
}

void SchuurmanVehicleHardware::publishApPowerStateReq(int32_t reqState,
                                                      int32_t param) {
    mLastApPowerStateReq.store(reqState);
    mLastApPowerStateReqParam.store(param);
    LOG(INFO) << "AP_POWER_STATE_REQ " << reqState << " param " << param;
    emitInts(static_cast<int32_t>(VehicleProperty::AP_POWER_STATE_REQ), {reqState, param});
}

void SchuurmanVehicleHardware::applyScreenPower(bool on, bool restoreBrightness) {
    if (on) {
        int restore = mLastNonZeroBrightness.load();
        if (restore <= 0) restore = 50;

        if (restoreBrightness || mCurrentBrightness.load() <= 0) {
            mCurrentBrightness.store(restore);
        }
        sendBrightness(mCurrentBrightness.load());
        mMcu.set(MCU_PROP_SCREEN_POWER, 1);

        mScreenOn.store(true);
        // Any legitimate screen-on (ACC back on, manual wake, etc.) re-arms
        // touch-to-wake for the next screen-off.
        mTapToWakeSuppressed.store(false);
    } else {
        int current = mCurrentBrightness.load();
        if (current > 0) {
            mLastNonZeroBrightness.store(current);
        }
        // Only the enable goes off; the MCU keeps the brightness for the next screen-on
        // (also when the display button turns it back on).
        mMcu.set(MCU_PROP_SCREEN_POWER, 0);
        mCurrentBrightness.store(0);
        mScreenOn.store(false);
    }

    // Only publish brightness to Android when turning on. Publishing brightness=0
    // on screen-off causes Android to cache 0; it then sends DISPLAY_BRIGHTNESS=0
    // back after wake-up, which overwrites the restored value.
    if (on) {
        publishCurrentBrightness();
    }
    publishVendorScreenPower();
}

void SchuurmanVehicleHardware::handleApPowerStateReport(
        const VehiclePropValue& request) {
    if (request.value.int32Values.empty()) {
        LOG(WARNING) << "AP_POWER_STATE_REPORT received without payload";
        return;
    }

    const int32_t state = request.value.int32Values[0];
    const int32_t param =
            request.value.int32Values.size() > 1 ? request.value.int32Values[1] : 0;

    mLastApPowerStateReport.store(state);
    mLastApPowerStateReportParam.store(param);

    LOG(INFO) << "AP_POWER_STATE_REPORT state=" << state << " param=" << param;

    // The MCU owns the power decisions: it answers with AP_POWER_STATE_REQ.
    if (mMcu.set(MCU_PROP_AP_POWER_STATE_REPORT, state, param)) {
        mReportPending.store(false);
    } else {
        mReportPending.store(true);
    }

    switch (static_cast<VehicleApPowerStateReport>(state)) {
        case VehicleApPowerStateReport::WAIT_FOR_VHAL:
        case VehicleApPowerStateReport::DEEP_SLEEP_EXIT:
        case VehicleApPowerStateReport::HIBERNATION_EXIT:
            // Android waits for AP_POWER_STATE_REQ. If the MCU does not answer
            // (not connected yet after resume, or missing) publish ON ourselves.
            mFallbackOnAtNs.store(elapsedRealtimeNano() + kFallbackOnNs);
            applyScreenPower(true, true);
            break;

        case VehicleApPowerStateReport::ON:
        case VehicleApPowerStateReport::SHUTDOWN_CANCELLED:
            applyScreenPower(true, true);
            break;

        case VehicleApPowerStateReport::DEEP_SLEEP_ENTRY:
        case VehicleApPowerStateReport::HIBERNATION_ENTRY:
        case VehicleApPowerStateReport::SHUTDOWN_PREPARE:
        case VehicleApPowerStateReport::SHUTDOWN_START:
            applyScreenPower(false, false);
            break;

        case VehicleApPowerStateReport::SHUTDOWN_POSTPONE:
            // Keep state as-is while Android finishes its cleanup work.
            break;

        default:
            LOG(INFO) << "Ignoring unhandled AP power report state=" << state;
            break;
    }
}

// ---------------------------------------------------------------- set / get

StatusCode SchuurmanVehicleHardware::setDisplayUnits(const VehiclePropValue& request,
                                                     const std::vector<int32_t>& supported,
                                                     const char* persistProp,
                                                     std::atomic<int32_t>* current,
                                                     VehiclePropValue* updatedValue) {
    if (request.value.int32Values.empty() ||
        std::find(supported.begin(), supported.end(), request.value.int32Values[0]) ==
                supported.end()) {
        return StatusCode::INVALID_ARG;
    }
    const int32_t unit = request.value.int32Values[0];
    current->store(unit);
    android::base::SetProperty(persistProp, std::to_string(unit));

    VehiclePropValue v = request;
    v.areaId = GLOBAL_AREA_ID;
    v.timestamp = elapsedRealtimeNano();
    emitPropChange(v);
    if (updatedValue) {
        *updatedValue = v;
    }
    return StatusCode::OK;
}

StatusCode SchuurmanVehicleHardware::setMcuSetting(const VehiclePropValue& request,
                                                   int32_t minValue, int32_t maxValue,
                                                   const char* persistProp) {
    if (request.value.int32Values.empty()) return StatusCode::INVALID_ARG;
    const int32_t value = request.value.int32Values[0];
    if (value < minValue || value > maxValue) return StatusCode::INVALID_ARG;
    if (persistProp) android::base::SetProperty(persistProp, std::to_string(value));
    if (!mMcu.set(static_cast<uint32_t>(request.prop), value)) {
        // Persisted settings reach the MCU when it connects; commands do not.
        return persistProp ? StatusCode::OK : StatusCode::TRY_AGAIN;
    }
    return StatusCode::OK;  // the MCU echoes the new value as a property change
}

StatusCode SchuurmanVehicleHardware::setValueInternal(
        const VehiclePropValue& request, VehiclePropValue* updatedValue) {
    if (request.prop == static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS)) {
        if (!request.value.int32Values.empty()) {
            int brightness = std::clamp(request.value.int32Values[0], 0, 100);

            if (!mAutoBrightnessEnabled.load()) {
                if (brightness > 0) {
                    mLastNonZeroBrightness.store(brightness);
                }
                mCurrentBrightness.store(brightness);

                if (mScreenOn.load()) {
                    sendBrightness(brightness);
                }

                publishCurrentBrightness();
            } else {
                LOG(INFO) << "Ignoring manual brightness update because auto brightness is enabled";
            }
        }
    } else if (request.prop == VENDOR_SCREEN_POWER) {
        if (!request.value.int32Values.empty()) {
            const bool on = (request.value.int32Values[0] == 1);
            applyScreenPower(on, true);
        }
    } else if (request.prop == VENDOR_AUTO_BRIGHTNESS) {
        if (!request.value.int32Values.empty()) {
            const bool enable = request.value.int32Values[0] == 1;
            mAutoBrightnessEnabled.store(enable);
            mAutoTargetBrightness.store(-1);

            VehiclePropValue v = request;
            v.areaId = GLOBAL_AREA_ID;
            v.timestamp = elapsedRealtimeNano();
            emitPropChange(v);
        }
    } else if (request.prop ==
               static_cast<int32_t>(VehicleProperty::AP_POWER_STATE_REPORT)) {
        handleApPowerStateReport(request);
    } else if (request.prop == static_cast<int32_t>(VehicleProperty::DISTANCE_DISPLAY_UNITS)) {
        return setDisplayUnits(request, kDistanceUnits, kDistanceUnitsProp, &mDistanceUnits,
                               updatedValue);
    } else if (request.prop ==
               static_cast<int32_t>(VehicleProperty::HVAC_TEMPERATURE_DISPLAY_UNITS)) {
        return setDisplayUnits(request, kTemperatureUnits, kTemperatureUnitsProp,
                               &mTemperatureUnits, updatedValue);
    } else if (request.prop == static_cast<int32_t>(VehicleProperty::FUEL_VOLUME_DISPLAY_UNITS)) {
        return setDisplayUnits(request, kFuelVolumeUnits, kFuelVolumeUnitsProp, &mFuelVolumeUnits,
                               updatedValue);
    } else if (request.prop == static_cast<int32_t>(MCU_PROP_AMP_MODE)) {
        return setMcuSetting(request, 0, 2, kAmpModeProp);
    } else if (request.prop == static_cast<int32_t>(MCU_PROP_OFF_DELAY_S)) {
        return setMcuSetting(request, 0, 7 * 24 * 3600, kOffDelayProp);
    } else if (request.prop == static_cast<int32_t>(MCU_PROP_AUDIO_MUTE)) {
        return setMcuSetting(request, 0, 1, nullptr);
    } else if (request.prop == static_cast<int32_t>(MCU_PROP_GNSS_CMD)) {
        return setMcuSetting(request, MCU_GNSS_CMD_RESET, MCU_GNSS_CMD_NORMAL, nullptr);
    } else {
        return StatusCode::INVALID_ARG;
    }

    if (updatedValue) {
        *updatedValue = request;
        updatedValue->areaId = GLOBAL_AREA_ID;
        updatedValue->timestamp = elapsedRealtimeNano();
    }
    return StatusCode::OK;
}

StatusCode SchuurmanVehicleHardware::getValueInternal(
        const VehiclePropValue& request, VehiclePropValue* response) const {
    response->prop = request.prop;
    response->areaId = (request.areaId != 0 ? request.areaId : GLOBAL_AREA_ID);
    response->timestamp = elapsedRealtimeNano();

    switch (static_cast<VehicleProperty>(request.prop)) {
        case VehicleProperty::INFO_MAKE:
            response->value.stringValue = "Schuurman";
            return StatusCode::OK;
        case VehicleProperty::INFO_MODEL:
            response->value.stringValue = "VIM3-Android16";
            return StatusCode::OK;
        case VehicleProperty::INFO_MODEL_YEAR:
            response->value.int32Values = {2026};
            return StatusCode::OK;
        case VehicleProperty::INFO_FUEL_CAPACITY:
            response->value.floatValues = {50000.0f};
            return StatusCode::OK;
        case VehicleProperty::INFO_FUEL_TYPE:
            response->value.int32Values = {
                    static_cast<int32_t>(FuelType::FUEL_TYPE_UNLEADED)};
            return StatusCode::OK;
        case VehicleProperty::INFO_DRIVER_SEAT:
            response->value.int32Values = {DRIVER_SEAT_ID};
            return StatusCode::OK;
        case VehicleProperty::SEAT_OCCUPANCY:
            response->value.int32Values = {
                    static_cast<int32_t>(VehicleSeatOccupancyState::OCCUPIED)};
            return StatusCode::OK;
        case VehicleProperty::DISPLAY_BRIGHTNESS:
            response->value.int32Values = {mCurrentBrightness.load()};
            return StatusCode::OK;
        case VehicleProperty::GEAR_SELECTION:
            response->value.int32Values = {mCurrentGear.load()};
            return StatusCode::OK;
        case VehicleProperty::PERF_VEHICLE_SPEED:
            response->value.floatValues = {mSpeed.load()};
            return StatusCode::OK;
        case VehicleProperty::IGNITION_STATE:
            response->value.int32Values = {mIgnitionState.load()};
            return StatusCode::OK;
        case VehicleProperty::PARKING_BRAKE_ON:
            response->value.int32Values = {mParkingBrakeOn.load()};
            return StatusCode::OK;
        case VehicleProperty::NIGHT_MODE:
            response->value.int32Values = {mNightMode.load()};
            return StatusCode::OK;
        case VehicleProperty::DISTANCE_DISPLAY_UNITS:
            response->value.int32Values = {mDistanceUnits.load()};
            return StatusCode::OK;
        case VehicleProperty::HVAC_TEMPERATURE_DISPLAY_UNITS:
            response->value.int32Values = {mTemperatureUnits.load()};
            return StatusCode::OK;
        case VehicleProperty::FUEL_VOLUME_DISPLAY_UNITS:
            response->value.int32Values = {mFuelVolumeUnits.load()};
            return StatusCode::OK;
        case VehicleProperty::AP_POWER_STATE_REQ:
            response->value.int32Values = {
                    mLastApPowerStateReq.load(),
                    mLastApPowerStateReqParam.load()};
            return StatusCode::OK;
        case VehicleProperty::AP_POWER_STATE_REPORT:
            response->value.int32Values = {
                    mLastApPowerStateReport.load(),
                    mLastApPowerStateReportParam.load()};
            return StatusCode::OK;
        default:
            break;
    }

    if (request.prop == VENDOR_AUTO_BRIGHTNESS) {
        response->value.int32Values = {mAutoBrightnessEnabled.load() ? 1 : 0};
        return StatusCode::OK;
    }
    if (request.prop == VENDOR_SCREEN_POWER) {
        response->value.int32Values = {mScreenOn.load() ? 1 : 0};
        return StatusCode::OK;
    }
    if (request.prop == POWER_POLICY_GROUP_REQ) {
        response->value.stringValue = mCurrentPolicyGroup;
        return StatusCode::OK;
    }
    if (request.prop == POWER_POLICY_REQ) {
        response->value.stringValue = mCurrentPolicyReq;
        return StatusCode::OK;
    }
    if (request.prop == VENDOR_MCU_FW_VERSION) {
        std::lock_guard<std::mutex> lk(mMcuMutex);
        if (mMcuVersion.empty()) return StatusCode::NOT_AVAILABLE;
        response->value.stringValue = mMcuVersion;
        return StatusCode::OK;
    }
    if (isMcuVendorProp(request.prop)) {
        if (request.prop == static_cast<int32_t>(MCU_PROP_GNSS_CMD)) {
            response->value.int32Values = {0};
            return StatusCode::OK;
        }
        std::lock_guard<std::mutex> lk(mMcuMutex);
        auto it = mMcuValues.find(request.prop);
        if (it == mMcuValues.end()) return StatusCode::NOT_AVAILABLE;
        if (isVecProp(request.prop)) {
            response->value.int32Values = {it->second.first, it->second.second};
        } else {
            response->value.int32Values = {it->second.first};
        }
        return StatusCode::OK;
    }
    return StatusCode::INVALID_ARG;
}

std::vector<VehiclePropConfig> SchuurmanVehicleHardware::getAllPropertyConfigs() const {
    std::vector<VehiclePropConfig> configs;

    auto addGlobalRO = [&](int32_t propId,
                           int32_t changeMode =
                                   static_cast<int32_t>(VehiclePropertyChangeMode::STATIC)) {
        VehiclePropConfig c;
        c.prop = propId;
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = static_cast<VehiclePropertyChangeMode>(changeMode);
        c.areaConfigs = {{.areaId = GLOBAL_AREA_ID}};
        configs.push_back(c);
    };

    auto addOnChange = [&](int32_t propId, VehiclePropertyAccess access, int32_t minValue,
                           int32_t maxValue) {
        VehiclePropConfig c;
        c.prop = propId;
        c.access = access;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{
                .areaId = GLOBAL_AREA_ID,
                .minInt32Value = minValue,
                .maxInt32Value = maxValue,
        }};
        configs.push_back(c);
    };

    addGlobalRO(static_cast<int32_t>(VehicleProperty::INFO_MAKE));
    addGlobalRO(static_cast<int32_t>(VehicleProperty::INFO_MODEL));
    addGlobalRO(static_cast<int32_t>(VehicleProperty::INFO_MODEL_YEAR));
    addGlobalRO(static_cast<int32_t>(VehicleProperty::INFO_FUEL_CAPACITY));
    addGlobalRO(static_cast<int32_t>(VehicleProperty::INFO_FUEL_TYPE));
    addGlobalRO(static_cast<int32_t>(VehicleProperty::INFO_DRIVER_SEAT));

    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::SEAT_OCCUPANCY);
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{
                .areaId = DRIVER_SEAT_ID,
                .minInt32Value = 0,
                .maxInt32Value = 3,
        }};
        configs.push_back(c);
    }

    addOnChange(static_cast<int32_t>(VehicleProperty::GEAR_SELECTION),
                VehiclePropertyAccess::READ, static_cast<int32_t>(VehicleGear::GEAR_PARK),
                static_cast<int32_t>(VehicleGear::GEAR_REVERSE));

    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::PERF_VEHICLE_SPEED);
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::CONTINUOUS;
        c.minSampleRate = 1.0f;
        c.maxSampleRate = 10.0f;
        c.areaConfigs = {{
                .areaId = GLOBAL_AREA_ID,
                .minFloatValue = 0.0f,
                .maxFloatValue = 100.0f,
        }};
        configs.push_back(c);
    }

    addOnChange(static_cast<int32_t>(VehicleProperty::IGNITION_STATE),
                VehiclePropertyAccess::READ, 0, 7);
    addOnChange(static_cast<int32_t>(VehicleProperty::PARKING_BRAKE_ON),
                VehiclePropertyAccess::READ, 0, 1);
    addOnChange(static_cast<int32_t>(VehicleProperty::NIGHT_MODE),
                VehiclePropertyAccess::READ, 0, 1);
    addOnChange(static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS),
                VehiclePropertyAccess::READ_WRITE, 0, 100);
    addOnChange(VENDOR_AUTO_BRIGHTNESS, VehiclePropertyAccess::READ_WRITE, 0, 1);
    addOnChange(VENDOR_SCREEN_POWER, VehiclePropertyAccess::READ_WRITE, 0, 1);

    // POWER_POLICY_GROUP_REQ and POWER_POLICY_REQ are VHAL → CarPowerPolicyService.
    {
        VehiclePropConfig c;
        c.prop = POWER_POLICY_GROUP_REQ;
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{.areaId = GLOBAL_AREA_ID}};
        configs.push_back(c);
    }

    {
        VehiclePropConfig c;
        c.prop = POWER_POLICY_REQ;
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{.areaId = GLOBAL_AREA_ID}};
        configs.push_back(c);
    }

    // Display units: configArray lists the supported VehicleUnit values (Car Settings' units page).
    auto addDisplayUnits = [&](VehicleProperty prop, const std::vector<int32_t>& units) {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(prop);
        c.access = VehiclePropertyAccess::READ_WRITE;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.configArray = units;
        c.areaConfigs = {{.areaId = GLOBAL_AREA_ID}};
        configs.push_back(c);
    };
    addDisplayUnits(VehicleProperty::DISTANCE_DISPLAY_UNITS, kDistanceUnits);
    addDisplayUnits(VehicleProperty::HVAC_TEMPERATURE_DISPLAY_UNITS, kTemperatureUnits);
    addDisplayUnits(VehicleProperty::FUEL_VOLUME_DISPLAY_UNITS, kFuelVolumeUnits);

    // AP_POWER_STATE_REQ is VHAL -> Android; the MCU decides it.
    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::AP_POWER_STATE_REQ);
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{.areaId = GLOBAL_AREA_ID}};
        // ENABLE_DEEP_SLEEP_FLAG: the MCU wakes the VIM3 by pressing its power key
        // (GPIOAO_7, an interrupt-capable wakeup source in meson-khadas-vim3.dtsi) and keeps
        // its supply on while suspended, so SHUTDOWN_PREPARE with CAN_SLEEP is a real,
        // resumable suspend-to-RAM.
        c.configArray = {
                static_cast<int32_t>(VehicleApPowerStateConfigFlag::ENABLE_DEEP_SLEEP_FLAG)};
        configs.push_back(c);
    }

    // AP_POWER_STATE_REPORT is Android -> VHAL -> MCU
    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::AP_POWER_STATE_REPORT);
        c.access = VehiclePropertyAccess::READ_WRITE;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{.areaId = GLOBAL_AREA_ID}};
        configs.push_back(c);
    }

    // Peripheral board values (mcu_protocol.h).
    for (const auto& p : kMcuVendorProps) {
        VehiclePropConfig c;
        c.prop = p.prop;
        c.access = p.writable ? VehiclePropertyAccess::READ_WRITE : VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{.areaId = GLOBAL_AREA_ID}};
        configs.push_back(c);
    }
    addGlobalRO(VENDOR_MCU_FW_VERSION, static_cast<int32_t>(VehiclePropertyChangeMode::ON_CHANGE));

    return configs;
}

// ---------------------------------------------------------------- display power (DPMS)

std::string SchuurmanVehicleHardware::findDisplayDpmsPath() {
    std::string prop = android::base::GetProperty(
            "ro.vendor.vehicle.display.dpms_path", "");
    if (!prop.empty() && access(prop.c_str(), R_OK) == 0) {
        LOG(INFO) << "Using configured DPMS path: " << prop;
        return prop;
    }

    const std::string drmBase = "/sys/class/drm/";
    std::error_code ec;
    for (const auto& entry : std::filesystem::directory_iterator(drmBase, ec)) {
        const std::string name = entry.path().filename().string();
        if (name.find("HDMI") != std::string::npos ||
            name.find("hdmi") != std::string::npos) {
            const std::string dpmsPath = entry.path().string() + "/dpms";
            if (access(dpmsPath.c_str(), R_OK) == 0) {
                LOG(INFO) << "Auto-detected DPMS path: " << dpmsPath;
                return dpmsPath;
            }
        }
    }
    if (ec) LOG(WARNING) << "Error scanning " << drmBase << ": " << ec.message();
    return "";
}

void SchuurmanVehicleHardware::displayStateLoop() {
    std::string lastState = "On";  // display assumed on at boot

    while (mDisplayThreadRunning.load()) {
        std::string state = readSysFsString(mDisplayDpmsPath, /*retries=*/1, /*delayMs=*/0);

        if (!state.empty() && state != lastState) {
            const bool isOn = (state == "On");
            LOG(INFO) << "DPMS: '" << lastState << "' -> '" << state << "'";
            lastState = state;
            applyScreenPower(isOn, isOn);
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }
}

// ---------------------------------------------------------------- IVehicleHardware

StatusCode SchuurmanVehicleHardware::checkHealth() {
    return StatusCode::OK;
}

void SchuurmanVehicleHardware::registerOnPropertyChangeEvent(
        std::unique_ptr<const PropertyChangeCallback> callback) {
    std::lock_guard<std::mutex> lk(mCallbackMutex);
    mOnPropChange = std::move(callback);
    emitInitialStatesLocked();
}

void SchuurmanVehicleHardware::registerOnPropertySetErrorEvent(
        std::unique_ptr<const PropertySetErrorCallback> callback) {
    std::lock_guard<std::mutex> lk(mCallbackMutex);
    mOnSetError = std::move(callback);
}

StatusCode SchuurmanVehicleHardware::subscribe(SubscribeOptions) {
    return StatusCode::OK;
}

StatusCode SchuurmanVehicleHardware::unsubscribe(int32_t, int32_t) {
    return StatusCode::OK;
}

StatusCode SchuurmanVehicleHardware::updateSampleRate(int32_t, int32_t, float) {
    return StatusCode::OK;
}

DumpResult SchuurmanVehicleHardware::dump(const std::vector<std::string>&) {
    std::string out = "Schuurman VHAL\n";
    out += "  MCU: " + std::string(mMcu.connected() ? "connected on " + mMcu.devicePath()
                                                     : "not connected") + "\n";
    {
        std::lock_guard<std::mutex> lk(mMcuMutex);
        out += "  MCU firmware: " + (mMcuVersion.empty() ? std::string("?") : mMcuVersion) + "\n";
        for (const auto& [prop, v] : mMcuValues) {
            out += android::base::StringPrintf("  0x%08x = %d, %d\n", prop, v.first, v.second);
        }
    }
    out += android::base::StringPrintf(
            "  gear %d, ignition %d, parking brake %d (handbrake wire %s, seen %d), night %d, "
            "speed %.2f m/s, lux %d\n",
            mCurrentGear.load(), mIgnitionState.load(), mParkingBrakeOn.load(),
            mHandbrakeRaw.load() ? "on" : "off", mHandbrakeSeen.load() ? 1 : 0, mNightMode.load(),
            mSpeed.load(), mLux.load());
    out += android::base::StringPrintf("  AP_POWER_STATE_REQ %d/%d, REPORT %d/%d\n",
                                       mLastApPowerStateReq.load(),
                                       mLastApPowerStateReqParam.load(),
                                       mLastApPowerStateReport.load(),
                                       mLastApPowerStateReportParam.load());
    DumpResult result;
    result.callerShouldDumpState = true;
    result.buffer = out;
    return result;
}

StatusCode SchuurmanVehicleHardware::getValues(
        std::shared_ptr<const GetValuesCallback> callback,
        const std::vector<GetValueRequest>& requests) const {
    std::vector<GetValueResult> results;
    results.reserve(requests.size());

    for (const auto& req : requests) {
        GetValueResult res;
        res.requestId = req.requestId;
        VehiclePropValue val = req.prop;
        res.status = getValueInternal(req.prop, &val);
        if (res.status == StatusCode::OK) {
            res.prop = std::move(val);
        }
        results.push_back(std::move(res));
    }

    (*callback)(std::move(results));
    return StatusCode::OK;
}

StatusCode SchuurmanVehicleHardware::setValues(
        std::shared_ptr<const SetValuesCallback> callback,
        const std::vector<SetValueRequest>& requests) {
    std::vector<SetValueResult> results;
    results.reserve(requests.size());

    for (const auto& req : requests) {
        SetValueResult res;
        res.requestId = req.requestId;
        res.status = setValueInternal(req.value, nullptr);
        results.push_back(std::move(res));
    }

    (*callback)(std::move(results));
    return StatusCode::OK;
}

// ---------------------------------------------------------------- input devices

// Scan /dev/input/event* for a device matching the given USB vendor/product ID.
// Returns an open O_RDONLY fd, or -1 if not found.
int SchuurmanVehicleHardware::findInputDeviceByVidPid(uint16_t vendor, uint16_t product) {
    for (int i = 0; i < 32; i++) {
        std::string path = "/dev/input/event" + std::to_string(i);
        int fd = open(path.c_str(), O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) continue;
        struct input_id id = {};
        if (ioctl(fd, EVIOCGID, &id) == 0 &&
            id.vendor == vendor && id.product == product) {
            return fd;
        }
        close(fd);
    }
    return -1;
}

// Scan /dev/input/event* for a device that reports the given EV_KEY keyCode.
// Returns an open O_RDWR fd (needed to write events), or -1 if not found.
int SchuurmanVehicleHardware::findInputDeviceWithKey(uint16_t keyCode) {
    // 32 bytes covers key codes 0-255.
    constexpr size_t kBufBytes = 32;
    for (int i = 0; i < 32; i++) {
        std::string path = "/dev/input/event" + std::to_string(i);
        int fd = open(path.c_str(), O_RDWR | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) continue;
        uint8_t bits[kBufBytes] = {};
        if (ioctl(fd, EVIOCGBIT(EV_KEY, kBufBytes), bits) >= 0 &&
            (bits[keyCode / 8] & (1u << (keyCode % 8)))) {
            return fd;
        }
        close(fd);
    }
    return -1;
}

static void writeKeyPress(int fd, uint16_t keyCode) {
    auto writeEvent = [&](uint16_t type, uint16_t code, int32_t value) {
        struct input_event out = {};
        out.type  = type;
        out.code  = code;
        out.value = value;
        write(fd, &out, sizeof(out));
    };
    writeEvent(EV_KEY, keyCode, 1);
    writeEvent(EV_SYN, SYN_REPORT, 0);
    writeEvent(EV_KEY, keyCode, 0);
    writeEvent(EV_SYN, SYN_REPORT, 0);
}

// Inject a media key (KEY_PAUSECD -> KEYCODE_MEDIA_PAUSE, KEY_PLAYCD -> KEYCODE_MEDIA_PLAY
// per Generic.kl) through the CEC-backed injectable device, as touchWakeLoop does.
void SchuurmanVehicleHardware::injectMediaKey(uint16_t keyCode) {
    int fd = findInputDeviceWithKey(keyCode);
    if (fd < 0) {
        LOG(WARNING) << "No input device can inject key " << keyCode;
        return;
    }
    writeKeyPress(fd, keyCode);
    close(fd);
}

// Monitor the WaveShare touch device. When a finger-down event arrives while
// the display is off, inject KEY_WAKEUP into the CEC device to wake Android.
void SchuurmanVehicleHardware::touchWakeLoop() {
    constexpr uint16_t kVendor  = 0x0eef;
    constexpr uint16_t kProduct = 0x0005;
    constexpr uint16_t kKeyWakeup = KEY_WAKEUP;  // 143

    int touchFd = -1;
    int wakeFd  = -1;

    while (mTouchWakeThreadRunning.load()) {
        // (Re-)open devices if needed.
        if (touchFd < 0) {
            touchFd = findInputDeviceByVidPid(kVendor, kProduct);
            if (touchFd < 0) {
                std::this_thread::sleep_for(std::chrono::seconds(2));
                continue;
            }
            // Switch to blocking mode for poll().
            int flags = fcntl(touchFd, F_GETFL, 0);
            fcntl(touchFd, F_SETFL, flags & ~O_NONBLOCK);
            LOG(INFO) << "touchWakeLoop: opened touch device";
        }
        if (wakeFd < 0) {
            wakeFd = findInputDeviceWithKey(kKeyWakeup);
            if (wakeFd < 0) {
                LOG(WARNING) << "touchWakeLoop: no KEY_WAKEUP device found, retrying";
                std::this_thread::sleep_for(std::chrono::seconds(2));
                continue;
            }
            LOG(INFO) << "touchWakeLoop: opened wakeup injection device";
        }

        struct pollfd pfd = {touchFd, POLLIN, 0};
        int ret = poll(&pfd, 1, 500);  // 500 ms timeout so we can check mTouchWakeThreadRunning
        if (ret <= 0) continue;
        if (!(pfd.revents & POLLIN)) continue;

        struct input_event ev = {};
        ssize_t n = read(touchFd, &ev, sizeof(ev));
        if (n != sizeof(ev)) {
            if (n == 0 || (n < 0 && errno != EAGAIN)) {
                LOG(WARNING) << "touchWakeLoop: touch device read error, reopening";
                close(touchFd);
                touchFd = -1;
            }
            continue;
        }

        // BTN_TOUCH DOWN while screen is off → inject KEY_WAKEUP, unless the
        // screen went off because the car was switched off (ACC low).
        if (ev.type == EV_KEY && ev.code == BTN_TOUCH && ev.value == 1 &&
            !mScreenOn.load() && !mTapToWakeSuppressed.load()) {
            LOG(INFO) << "touchWakeLoop: touch while screen off, injecting KEY_WAKEUP";
            writeKeyPress(wakeFd, kKeyWakeup);
            // The display button turns off only the backlight (Android's display stays on,
            // so no DPMS change follows): switch it back on here as well.
            applyScreenPower(true, true);
        }
    }

    if (touchFd >= 0) close(touchFd);
    if (wakeFd  >= 0) close(wakeFd);
}

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android
