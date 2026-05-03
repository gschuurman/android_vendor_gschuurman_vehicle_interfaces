#include "SchuurmanVehicleHardware.h"

#include <aidl/android/hardware/automotive/vehicle/FuelType.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleApPowerStateReport.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleApPowerStateReq.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleArea.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleGear.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleIgnitionState.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleProperty.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyAccess.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyChangeMode.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleSeatOccupancyState.h>

#include <android-base/logging.h>
#include <android-base/properties.h>

#include <errno.h>
#include <fcntl.h>
#include <linux/gpio.h>
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
using ::aidl::android::hardware::automotive::vehicle::VehicleApPowerStateReport;
using ::aidl::android::hardware::automotive::vehicle::VehicleApPowerStateReq;
using ::aidl::android::hardware::automotive::vehicle::VehicleArea;
using ::aidl::android::hardware::automotive::vehicle::VehicleGear;
using ::aidl::android::hardware::automotive::vehicle::VehicleIgnitionState;
using ::aidl::android::hardware::automotive::vehicle::VehicleProperty;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyAccess;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyChangeMode;
using ::aidl::android::hardware::automotive::vehicle::VehicleSeatOccupancyState;

static const int32_t VENDOR_AUTO_BRIGHTNESS = 0x12000001;
static const int32_t VENDOR_SCREEN_POWER = 0x21400555;

static constexpr int32_t PWM_PERIOD_NS = 30518;
static constexpr int32_t GLOBAL_AREA_ID = 0;
static constexpr int32_t DRIVER_SEAT_ID = 1;

static std::string findPwmChipPath() {
    const std::string baseDir = "/sys/class/pwm/";
    for (int i = 0; i < 10; i++) {
        const std::string chipName = "pwmchip" + std::to_string(i);
        const std::string fullPath = baseDir + chipName;
        const std::string linkPath = fullPath + "/device/of_node";

        char buf[1024];
        ssize_t len = readlink(linkPath.c_str(), buf, sizeof(buf) - 1);
        if (len != -1) {
            buf[len] = '\0';
            if (std::string(buf).find("19000") != std::string::npos) {
                LOG(INFO) << "Found PWM chip " << chipName << " for address 19000";
                return fullPath;
            }
        }
    }
    LOG(WARNING) << "PWM chip for address 19000 not found, falling back to pwmchip0";
    return baseDir + "pwmchip0";
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

static int readIntFileNoExcept(const std::string& path) {
    std::ifstream f(path);
    if (!f) return -1;
    long v = -1;
    if (!(f >> v)) return -1;
    return static_cast<int>(v);
}

SchuurmanVehicleHardware::SchuurmanVehicleHardware()
    : mCurrentGear(static_cast<int32_t>(VehicleGear::GEAR_PARK)),
      mCurrentBrightness(50),
      mLastNonZeroBrightness(50),
      mScreenOn(true),
      mIgnitionState(static_cast<int32_t>(VehicleIgnitionState::ON)),
      mParkingBrakeOn(1),
      mGearGpioOffset(51),
      mBacklightEnableGpioOffset(53),
      mBacklightEnableFd(-1),
      mGearFd(-1),
      mShuttingDown(false),
      mSensorThreadRunning(false),
      mLightSensorPath("/data/vendor/sensors/bh1750_lux"),
      mSensorRawMax(100000),
      mAutoBrightnessEnabled(false),
      mAutoTargetBrightness(-1),
      mDisplayThreadRunning(false),
      mLastApPowerStateReq(static_cast<int32_t>(VehicleApPowerStateReq::ON)),
      mLastApPowerStateReqParam(0),
      mLastApPowerStateReport(static_cast<int32_t>(VehicleApPowerStateReport::ON)),
      mLastApPowerStateReportParam(0) {
    LOG(INFO) << "Initializing SchuurmanVehicleHardware";

    mPwmChipBase = findPwmChipPath();
    mPathPwmDuty = mPwmChipBase + "/pwm1/duty_cycle";
    mPathPwmEnable = mPwmChipBase + "/pwm1/enable";
    mPathPwmPeriod = mPwmChipBase + "/pwm1/period";

    initPwm();
    initGpios();

    mSensorThreadRunning.store(true);
    mSensorThread = std::thread(&SchuurmanVehicleHardware::sensorLoop, this);
    mPollThread = std::thread(&SchuurmanVehicleHardware::pollInputs, this);

    mDisplayDpmsPath = findDisplayDpmsPath();
    if (!mDisplayDpmsPath.empty()) {
        mDisplayThreadRunning.store(true);
        mDisplayThread = std::thread(&SchuurmanVehicleHardware::displayStateLoop, this);
    } else {
        LOG(WARNING) << "Display DPMS path not found - backlight won't track display sleep";
    }

    LOG(INFO) << "Initial gear forced to PARK";
    LOG(INFO) << "Ignition forced ON; parking brake ON";
}

SchuurmanVehicleHardware::~SchuurmanVehicleHardware() {
    mShuttingDown.store(true);
    if (mPollThread.joinable()) mPollThread.join();

    mSensorThreadRunning.store(false);
    if (mSensorThread.joinable()) mSensorThread.join();

    mDisplayThreadRunning.store(false);
    if (mDisplayThread.joinable()) mDisplayThread.join();

    if (mBacklightEnableFd >= 0) close(mBacklightEnableFd);
    if (mGearFd >= 0) close(mGearFd);
}

void SchuurmanVehicleHardware::emitPropChange(const VehiclePropValue& v) {
    std::lock_guard<std::mutex> lk(mCallbackMutex);
    if (!mOnPropChange) return;
    std::vector<VehiclePropValue> events;
    events.push_back(v);
    (*mOnPropChange)(events);
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
        v.value.floatValues = {0.0f};
        events.push_back(v);
    }

    addIntEvent(static_cast<int32_t>(VehicleProperty::IGNITION_STATE),
                GLOBAL_AREA_ID, mIgnitionState.load());
    addIntEvent(static_cast<int32_t>(VehicleProperty::PARKING_BRAKE_ON),
                GLOBAL_AREA_ID, mParkingBrakeOn.load());
    addIntEvent(static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS),
                GLOBAL_AREA_ID, mCurrentBrightness.load());
    addIntEvent(VENDOR_AUTO_BRIGHTNESS, GLOBAL_AREA_ID,
                mAutoBrightnessEnabled.load() ? 1 : 0);
    addIntEvent(VENDOR_SCREEN_POWER, GLOBAL_AREA_ID,
                mScreenOn.load() ? 1 : 0);
    addIntEvent(static_cast<int32_t>(VehicleProperty::SEAT_OCCUPANCY),
                DRIVER_SEAT_ID,
                static_cast<int32_t>(VehicleSeatOccupancyState::OCCUPIED));

    // Since there is no external VMCU in your setup, expose a sane default AP request.
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

void SchuurmanVehicleHardware::initGpios() {
    if (mBacklightGpioChipName.empty()) {
        mBacklightGpioChipName = "/dev/" +
                android::base::GetProperty(
                        "ro.vendor.vehicle.backlight.enable.gpio.chip",
                        "gpiochip0");
    }

    if (mGearGpioChipName.empty()) {
        mGearGpioChipName = "/dev/" +
                android::base::GetProperty(
                        "ro.vendor.vehicle.gear.gpio.chip",
                        "gpiochip0");
    }

    mBacklightEnableGpioOffset = android::base::GetIntProperty(
            "ro.vendor.vehicle.backlight.enable.gpio.offset", 53);
    mGearGpioOffset = android::base::GetIntProperty(
            "ro.vendor.vehicle.gear.gpio.offset", 51);

    LOG(INFO) << "Backlight GPIO config: chip=" << mBacklightGpioChipName
              << " offset=" << mBacklightEnableGpioOffset;
    LOG(INFO) << "Gear GPIO config: chip=" << mGearGpioChipName
              << " offset=" << mGearGpioOffset;

    if (mBacklightEnableFd < 0) {
        int chipFd = open(mBacklightGpioChipName.c_str(), O_RDWR);
        if (chipFd < 0) {
            LOG(ERROR) << "Failed to open backlight GPIO chip "
                       << mBacklightGpioChipName << ": " << strerror(errno);
        } else {
            struct gpiohandle_request reqBl;
            memset(&reqBl, 0, sizeof(reqBl));
            reqBl.lineoffsets[0] = mBacklightEnableGpioOffset;
            reqBl.lines = 1;
            reqBl.flags = GPIOHANDLE_REQUEST_OUTPUT;
            reqBl.default_values[0] = 1;
            strncpy(reqBl.consumer_label, "vhal_backlight",
                    sizeof(reqBl.consumer_label) - 1);

            if (ioctl(chipFd, GPIO_GET_LINEHANDLE_IOCTL, &reqBl) >= 0) {
                mBacklightEnableFd = reqBl.fd;
                LOG(INFO) << "Backlight GPIO initialized";
            } else {
                LOG(ERROR) << "Failed to request backlight GPIO line "
                           << mBacklightEnableGpioOffset << ": "
                           << strerror(errno);
            }
            close(chipFd);
        }
    }

    if (mGearFd < 0) {
        int chipFd = open(mGearGpioChipName.c_str(), O_RDWR);
        if (chipFd < 0) {
            LOG(ERROR) << "Failed to open gear GPIO chip "
                       << mGearGpioChipName << ": " << strerror(errno);
        } else {
            struct gpiohandle_request reqGear;
            memset(&reqGear, 0, sizeof(reqGear));
            reqGear.lineoffsets[0] = mGearGpioOffset;
            reqGear.lines = 1;
            reqGear.flags = GPIOHANDLE_REQUEST_INPUT;
            strncpy(reqGear.consumer_label, "vhal_gear",
                    sizeof(reqGear.consumer_label) - 1);

            if (ioctl(chipFd, GPIO_GET_LINEHANDLE_IOCTL, &reqGear) >= 0) {
                mGearFd = reqGear.fd;
                LOG(INFO) << "Gear GPIO initialized";
            } else {
                LOG(ERROR) << "Failed to request gear GPIO line "
                           << mGearGpioOffset << ": " << strerror(errno);
            }
            close(chipFd);
        }
    }
}

void SchuurmanVehicleHardware::setBacklightEnable(bool on) {
    if (mBacklightEnableFd < 0) return;

    struct gpiohandle_data data;
    memset(&data, 0, sizeof(data));
    data.values[0] = on ? 1 : 0;

    if (ioctl(mBacklightEnableFd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, &data) < 0) {
        LOG(ERROR) << "Failed to set backlight GPIO: " << strerror(errno);
    } else {
        LOG(INFO) << "Backlight GPIO set to " << (on ? "ON" : "OFF");
    }
}

int SchuurmanVehicleHardware::readGearGpio() {
    if (mGearFd < 0) return -1;

    struct gpiohandle_data data;
    memset(&data, 0, sizeof(data));

    if (ioctl(mGearFd, GPIOHANDLE_GET_LINE_VALUES_IOCTL, &data) < 0) {
        LOG(ERROR) << "Failed reading gear GPIO: " << strerror(errno);
        return -1;
    }
    return data.values[0];
}

void SchuurmanVehicleHardware::initPwm() {
    LOG(INFO) << "Initializing PWM";
    ensurePwmExported(mPwmChipBase);

    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    writeSysFs(mPathPwmEnable, "0");
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    writeSysFs(mPathPwmPeriod, std::to_string(PWM_PERIOD_NS));
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    writeSysFs(mPathPwmDuty, std::to_string(PWM_PERIOD_NS / 2));
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
    writeSysFs(mPathPwmEnable, "1");
}

void SchuurmanVehicleHardware::writePwm(int percentage) {
    if (percentage < 0) percentage = 0;
    if (percentage > 100) percentage = 100;

    int inverted = 100 - percentage;
    long long dutyCalc =
            (static_cast<long long>(inverted) *
             static_cast<long long>(PWM_PERIOD_NS)) /
            100;
    writeSysFs(mPathPwmDuty, std::to_string(dutyCalc));
}

void SchuurmanVehicleHardware::ensurePwmExported(const std::string& base) {
    const std::string pwmEnablePath = base + "/pwm1/enable";
    const std::string exportPath = base + "/export";

    if (access(pwmEnablePath.c_str(), W_OK) == 0) return;

    if (!std::filesystem::exists(base + "/pwm1")) {
        writeSysFs(exportPath, "1");
    }
}

void SchuurmanVehicleHardware::writeSysFs(const std::string& path,
                                          const std::string& val) {
    int fd = open(path.c_str(), O_WRONLY | O_TRUNC);
    if (fd < 0) {
        LOG(ERROR) << "Failed to open " << path << ": " << strerror(errno);
        return;
    }
    if (write(fd, val.c_str(), val.size()) < 0) {
        LOG(ERROR) << "Failed to write " << path << ": " << strerror(errno);
    }
    fsync(fd);
    close(fd);
}

int SchuurmanVehicleHardware::readSysFsInt(const std::string& path) {
    std::string s = readSysFsString(path);
    if (s.empty()) return -1;
    return std::stoi(s);
}

void SchuurmanVehicleHardware::publishCurrentBrightness() {
    VehiclePropValue v;
    v.prop = static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS);
    v.areaId = GLOBAL_AREA_ID;
    v.timestamp = elapsedRealtimeNano();
    v.value.int32Values = {mCurrentBrightness.load()};
    emitPropChange(v);
}

void SchuurmanVehicleHardware::publishVendorScreenPower() {
    VehiclePropValue v;
    v.prop = VENDOR_SCREEN_POWER;
    v.areaId = GLOBAL_AREA_ID;
    v.timestamp = elapsedRealtimeNano();
    v.value.int32Values = {mScreenOn.load() ? 1 : 0};
    emitPropChange(v);
}

void SchuurmanVehicleHardware::publishApPowerStateReq(int32_t reqState,
                                                      int32_t param) {
    mLastApPowerStateReq.store(reqState);
    mLastApPowerStateReqParam.store(param);

    VehiclePropValue v;
    v.prop = static_cast<int32_t>(VehicleProperty::AP_POWER_STATE_REQ);
    v.areaId = GLOBAL_AREA_ID;
    v.timestamp = elapsedRealtimeNano();
    v.value.int32Values = {reqState, param};
    emitPropChange(v);
}

void SchuurmanVehicleHardware::applyScreenPower(bool on, bool restoreBrightness) {
    if (on) {
        int restore = mLastNonZeroBrightness.load();
        if (restore <= 0) restore = 50;

        setBacklightEnable(true);

        if (restoreBrightness) {
            writePwm(restore);
            mCurrentBrightness.store(restore);
        }

        // Ensure PWM is non-zero even if current brightness was 0.
        if (mCurrentBrightness.load() <= 0) {
            mCurrentBrightness.store(restore);
            writePwm(restore);
        }

        mScreenOn.store(true);
    } else {
        int current = mCurrentBrightness.load();
        if (current > 0) {
            mLastNonZeroBrightness.store(current);
        }

        writePwm(0);
        setBacklightEnable(false);
        mCurrentBrightness.store(0);
        mScreenOn.store(false);
    }

    publishCurrentBrightness();
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

    switch (static_cast<VehicleApPowerStateReport>(state)) {
        case VehicleApPowerStateReport::ON:
        case VehicleApPowerStateReport::DEEP_SLEEP_EXIT:
        case VehicleApPowerStateReport::HIBERNATION_EXIT:
        case VehicleApPowerStateReport::SHUTDOWN_CANCELLED:
        case VehicleApPowerStateReport::WAIT_FOR_VHAL:
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

StatusCode SchuurmanVehicleHardware::setValueInternal(
        const VehiclePropValue& request, VehiclePropValue* updatedValue) {
    if (request.prop == static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS)) {
        if (!request.value.int32Values.empty()) {
            int brightness = request.value.int32Values[0];
            if (brightness < 0) brightness = 0;
            if (brightness > 100) brightness = 100;

            if (!mAutoBrightnessEnabled.load()) {
                if (brightness > 0) {
                    mLastNonZeroBrightness.store(brightness);
                }
                mCurrentBrightness.store(brightness);

                if (mScreenOn.load()) {
                    writePwm(brightness);
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

            VehiclePropValue v = request;
            v.areaId = GLOBAL_AREA_ID;
            v.timestamp = elapsedRealtimeNano();
            emitPropChange(v);
        }
    } else if (request.prop ==
               static_cast<int32_t>(VehicleProperty::AP_POWER_STATE_REPORT)) {
        handleApPowerStateReport(request);
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
                    static_cast<int32_t>(FuelType::FUEL_TYPE_ELECTRIC)};
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
            response->value.floatValues = {0.0f};
            return StatusCode::OK;
        case VehicleProperty::IGNITION_STATE:
            response->value.int32Values = {mIgnitionState.load()};
            return StatusCode::OK;
        case VehicleProperty::PARKING_BRAKE_ON:
            response->value.int32Values = {mParkingBrakeOn.load()};
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
            if (request.prop == VENDOR_AUTO_BRIGHTNESS) {
                response->value.int32Values = {
                        mAutoBrightnessEnabled.load() ? 1 : 0};
                return StatusCode::OK;
            }
            if (request.prop == VENDOR_SCREEN_POWER) {
                response->value.int32Values = {mScreenOn.load() ? 1 : 0};
                return StatusCode::OK;
            }
            return StatusCode::INVALID_ARG;
    }
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

    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{
                .areaId = GLOBAL_AREA_ID,
                .minInt32Value = static_cast<int32_t>(VehicleGear::GEAR_PARK),
                .maxInt32Value = static_cast<int32_t>(VehicleGear::GEAR_REVERSE),
        }};
        configs.push_back(c);
    }

    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::PERF_VEHICLE_SPEED);
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::CONTINUOUS;
        c.minSampleRate = 1.0f;
        c.maxSampleRate = 100.0f;
        c.areaConfigs = {{
                .areaId = GLOBAL_AREA_ID,
                .minFloatValue = 0.0f,
                .maxFloatValue = 100.0f,
        }};
        configs.push_back(c);
    }

    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::IGNITION_STATE);
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{
                .areaId = GLOBAL_AREA_ID,
                .minInt32Value = 0,
                .maxInt32Value = 7,
        }};
        configs.push_back(c);
    }

    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::PARKING_BRAKE_ON);
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{
                .areaId = GLOBAL_AREA_ID,
                .minInt32Value = 0,
                .maxInt32Value = 1,
        }};
        configs.push_back(c);
    }

    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS);
        c.access = VehiclePropertyAccess::READ_WRITE;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{
                .areaId = GLOBAL_AREA_ID,
                .minInt32Value = 0,
                .maxInt32Value = 100,
        }};
        configs.push_back(c);
    }

    {
        VehiclePropConfig c;
        c.prop = VENDOR_AUTO_BRIGHTNESS;
        c.access = VehiclePropertyAccess::READ_WRITE;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{
                .areaId = GLOBAL_AREA_ID,
                .minInt32Value = 0,
                .maxInt32Value = 1,
        }};
        configs.push_back(c);
    }

    {
        VehiclePropConfig c;
        c.prop = VENDOR_SCREEN_POWER;
        c.access = VehiclePropertyAccess::READ_WRITE;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{
                .areaId = GLOBAL_AREA_ID,
                .minInt32Value = 0,
                .maxInt32Value = 1,
        }};
        configs.push_back(c);
    }

    // Correct AAOS direction:
    // AP_POWER_STATE_REQ is VHAL -> Android
    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::AP_POWER_STATE_REQ);
        c.access = VehiclePropertyAccess::READ;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{.areaId = GLOBAL_AREA_ID}};
        configs.push_back(c);
    }

    // AP_POWER_STATE_REPORT is Android -> VHAL
    {
        VehiclePropConfig c;
        c.prop = static_cast<int32_t>(VehicleProperty::AP_POWER_STATE_REPORT);
        c.access = VehiclePropertyAccess::READ_WRITE;
        c.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        c.areaConfigs = {{.areaId = GLOBAL_AREA_ID}};
        configs.push_back(c);
    }

    return configs;
}

void SchuurmanVehicleHardware::pollInputs() {
    int lastGearState = -2;

    while (!mShuttingDown.load()) {
        if (mGearFd < 0 || mBacklightEnableFd < 0) {
            static int retryCounter = 0;
            if (retryCounter++ % 10 == 0) {
                LOG(INFO) << "Retrying GPIO initialization";
                initGpios();
            }
        }

        if (mGearFd >= 0) {
            int gearState = readGearGpio();

            if (gearState < 0) {
                LOG(ERROR) << "Failed to read gear GPIO, resetting FD";
                close(mGearFd);
                mGearFd = -1;
            } else if (gearState != lastGearState) {
                LOG(INFO) << "Gear GPIO changed: " << lastGearState
                          << " -> " << gearState;

                int32_t newGear = (gearState == 1)
                        ? static_cast<int32_t>(VehicleGear::GEAR_REVERSE)
                        : static_cast<int32_t>(VehicleGear::GEAR_PARK);

                if (newGear != mCurrentGear.load()) {
                    mCurrentGear.store(newGear);

                    VehiclePropValue v;
                    v.prop = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
                    v.areaId = GLOBAL_AREA_ID;
                    v.timestamp = elapsedRealtimeNano();
                    v.value.int32Values = {newGear};
                    emitPropChange(v);

                    LOG(INFO) << "Published gear state " << newGear;
                }
                lastGearState = gearState;
            }
        } else {
            static bool forcedOnce = false;
            if (!forcedOnce) {
                forcedOnce = true;
                mCurrentGear.store(static_cast<int32_t>(VehicleGear::GEAR_PARK));

                VehiclePropValue v;
                v.prop = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
                v.areaId = GLOBAL_AREA_ID;
                v.timestamp = elapsedRealtimeNano();
                v.value.int32Values = {mCurrentGear.load()};
                emitPropChange(v);

                LOG(WARNING) << "GPIO unavailable, forcing gear=PARK";
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
}

void SchuurmanVehicleHardware::sensorLoop() {
    double ema = -1.0;
    const double alpha = 0.25;
    const int pollMs = 250;

    while (mSensorThreadRunning.load()) {
        int raw = readIntFileNoExcept(mLightSensorPath);
        if (raw >= 0) {
            if (ema < 0) {
                ema = static_cast<double>(raw);
            } else {
                ema = alpha * static_cast<double>(raw) + (1.0 - alpha) * ema;
            }

            double maxLux = static_cast<double>(mSensorRawMax);
            if (maxLux < 1.0) maxLux = 1.0;

            double percent =
                    (log(1.0 + ema) / log(1.0 + maxLux)) * 100.0;
            if (percent < 0.0) percent = 0.0;
            if (percent > 100.0) percent = 100.0;

            int intPercent = static_cast<int>(percent + 0.5);

            if (mAutoBrightnessEnabled.load()) {
                int last = mAutoTargetBrightness.load();
                if (last < 0 || std::abs(intPercent - last) >= 2) {
                    mAutoTargetBrightness.store(intPercent);

                    if (mScreenOn.load()) {
                        if (intPercent > 0) {
                            mLastNonZeroBrightness.store(intPercent);
                        }
                        writePwm(intPercent);
                        mCurrentBrightness.store(intPercent);
                        publishCurrentBrightness();
                    }
                }
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(pollMs));
    }
}

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
    return {};
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

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android