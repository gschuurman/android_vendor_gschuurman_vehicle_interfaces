/*
 * Copyright (C) 2021 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "SchuurmanVehicleHardware.h"

#include <aidl/android/hardware/automotive/vehicle/VehicleGear.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleProperty.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyAccess.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyChangeMode.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/gpio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <regex>
#include <thread>
#include <vector>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

using ::aidl::android::hardware::automotive::vehicle::VehicleGear;
using ::aidl::android::hardware::automotive::vehicle::VehicleProperty;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyAccess;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyChangeMode;

// Vendor Properties
static const int32_t VENDOR_AUTO_BRIGHTNESS = 0x12000001;
// New dedicated property for Screen Power (GPIO 53)
static const int32_t VENDOR_SCREEN_POWER = 0x21400555;

// Constants
static constexpr int32_t PWM_PERIOD_NS = 30518;

// Helper: Find PWM Chip 19000 (VIM3 specific)
std::string findPwmChipPath() {
    std::string baseDir = "/sys/class/pwm/";
    for (int i = 0; i < 10; i++) {
        std::string chipName = "pwmchip" + std::to_string(i);
        std::string fullPath = baseDir + chipName;
        std::string linkPath = fullPath + "/device/of_node";

        char buf[1024];
        ssize_t len = readlink(linkPath.c_str(), buf, sizeof(buf) - 1);
        if (len != -1) {
            buf[len] = '\0';
            if (std::string(buf).find("19000") != std::string::npos) {
                LOG(INFO) << "Found PWM Chip: " << chipName << " (Address 19000)";
                return fullPath;
            }
        }
    }
    LOG(ERROR) << "PWM Chip 19000 not found! Fallback to pwmchip0";
    return baseDir + "pwmchip0";
}

static int64_t elapsedRealtimeNano() {
    auto now = std::chrono::steady_clock::now();
    return std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
}

static std::string readSysFsString(const std::string& path, int retries = 3, int delayMs = 50) {
    for (int i = 0; i < retries; ++i) {
        std::ifstream file(path);
        if (file) {
            std::string s;
            if (std::getline(file, s)) {
                auto start = s.find_first_not_of(" \t\n\r");
                auto end = s.find_last_not_of(" \t\n\r");
                if (start == std::string::npos) return std::string();
                return s.substr(start, end - start + 1);
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
      mScreenOn(true),
      mBacklightEnableFd(-1),
      mShuttingDown(false),
      mSensorThreadRunning(false),
      mLightSensorPath("/data/vendor/sensors/bh1750_lux"),
      mSensorRawMax(100000),
      mAutoBrightnessEnabled(false),
      mAutoTargetBrightness(-1) {
    LOG(INFO) << ">>> INIT START SchuurmanVehicleHardware <<<";

    // 1. PWM Setup
    mPwmChipBase = findPwmChipPath();
    mPathPwmDuty = mPwmChipBase + "/pwm1/duty_cycle";
    mPathPwmEnable = mPwmChipBase + "/pwm1/enable";
    mPathPwmPeriod = mPwmChipBase + "/pwm1/period";

    initPwm();

    // 2. GPIO Setup
    initGpios();

    // 3. Threads
    mSensorThreadRunning.store(true);
    mSensorThread = std::thread(&SchuurmanVehicleHardware::sensorLoop, this);
    mPollThread = std::thread(&SchuurmanVehicleHardware::pollInputs, this);
}

SchuurmanVehicleHardware::~SchuurmanVehicleHardware() {
    mShuttingDown = true;
    if (mPollThread.joinable()) mPollThread.join();

    mSensorThreadRunning.store(false);
    if (mSensorThread.joinable()) mSensorThread.join();

    if (mBacklightEnableFd >= 0) close(mBacklightEnableFd);
}

void SchuurmanVehicleHardware::initGpios() {
    mGpioChipName =
            "/dev/" + android::base::GetProperty("ro.vendor.vehicle.gpio.chip", "gpiochip0");

    mBrightnessGpioOffset =
            android::base::GetIntProperty("ro.vendor.vehicle.brightness.gpio.offset", 51);

    mBacklightEnableGpioOffset =
            android::base::GetIntProperty("ro.vendor.vehicle.backlight.enable.gpio.offset", 53);

    mGearGpioOffset = android::base::GetIntProperty("ro.vendor.vehicle.gear.gpio.offset", -1);

    LOG(INFO) << "GPIO Config: Chip=" << mGpioChipName
              << " BL_Enable=" << mBacklightEnableGpioOffset
              << " BrightnessRef=" << mBrightnessGpioOffset << " Gear=" << mGearGpioOffset;

    int chipFd = open(mGpioChipName.c_str(), O_RDWR);
    if (chipFd < 0) {
        LOG(ERROR) << "Could not open GPIO chip " << mGpioChipName << ": " << strerror(errno);
        return;
    }

    struct gpiohandle_request req;
    memset(&req, 0, sizeof(req));
    req.lineoffsets[0] = mBacklightEnableGpioOffset;
    req.lines = 1;
    req.flags = GPIOHANDLE_REQUEST_OUTPUT;
    req.default_values[0] = 1;  // Default ON
    strncpy(req.consumer_label, "vhal_backlight", sizeof(req.consumer_label) - 1);

    int ret = ioctl(chipFd, GPIO_GET_LINEHANDLE_IOCTL, &req);
    if (ret < 0) {
        LOG(ERROR) << "Failed to request Backlight GPIO line " << mBacklightEnableGpioOffset << ": "
                   << strerror(errno);
    } else {
        mBacklightEnableFd = req.fd;
        mScreenOn.store(true);
        LOG(INFO) << "Backlight Enable GPIO " << mBacklightEnableGpioOffset << " initialized.";
    }

    close(chipFd);
}

void SchuurmanVehicleHardware::setBacklightEnable(bool on) {
    if (mBacklightEnableFd < 0) return;

    struct gpiohandle_data data;
    memset(&data, 0, sizeof(data));
    data.values[0] = on ? 1 : 0;

    if (ioctl(mBacklightEnableFd, GPIOHANDLE_SET_LINE_VALUES_IOCTL, &data) < 0) {
        LOG(ERROR) << "Failed to set Backlight GPIO: " << strerror(errno);
    } else {
        LOG(INFO) << "Set Backlight GPIO " << mBacklightEnableGpioOffset << " to "
                  << (on ? "ON" : "OFF");
    }
}

int SchuurmanVehicleHardware::readGearGpio() {
    if (mGearGpioOffset < 0) return -1;

    int fd = open(mGpioChipName.c_str(), O_RDWR);
    if (fd < 0) return -1;

    struct gpiohandle_request req;
    memset(&req, 0, sizeof(req));
    req.lineoffsets[0] = mGearGpioOffset;
    req.lines = 1;
    req.flags = GPIOHANDLE_REQUEST_INPUT;

    int ret = ioctl(fd, GPIO_GET_LINEHANDLE_IOCTL, &req);
    if (ret < 0) {
        close(fd);
        return -1;
    }

    struct gpiohandle_data data;
    memset(&data, 0, sizeof(data));
    ioctl(req.fd, GPIOHANDLE_GET_LINE_VALUES_IOCTL, &data);

    close(req.fd);
    close(fd);
    return data.values[0];
}

void SchuurmanVehicleHardware::initPwm() {
    LOG(INFO) << ">>> Initializing PWM Hardware <<<";
    ensurePwmExported(mPwmChipBase);

    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    writeSysFs(mPathPwmEnable, "0");
    std::this_thread::sleep_for(std::chrono::milliseconds(20));

    writeSysFs(mPathPwmPeriod, std::to_string(PWM_PERIOD_NS));
    std::this_thread::sleep_for(std::chrono::milliseconds(20));

    writeSysFs(mPathPwmDuty, std::to_string(PWM_PERIOD_NS / 2));
    std::this_thread::sleep_for(std::chrono::milliseconds(20));

    writeSysFs(mPathPwmEnable, "1");
    LOG(INFO) << "PWM Initialized.";
}

void SchuurmanVehicleHardware::writePwm(int percentage) {
    if (percentage < 0) percentage = 0;
    if (percentage > 100) percentage = 100;

    int inverted = 100 - percentage;
    long long dutyCalc = ((long long)inverted * (long long)PWM_PERIOD_NS) / 100;

    writeSysFs(mPathPwmDuty, std::to_string(dutyCalc));
}

void SchuurmanVehicleHardware::ensurePwmExported(const std::string& base) {
    std::string pwmEnablePath = base + "/pwm1/enable";
    std::string exportPath = base + "/export";

    if (access(pwmEnablePath.c_str(), W_OK) == 0) return;

    if (!std::filesystem::exists(base + "/pwm1")) {
        writeSysFs(exportPath, "1");
    }
}

void SchuurmanVehicleHardware::writeSysFs(const std::string& path, const std::string& val) {
    int fd = open(path.c_str(), O_WRONLY | O_TRUNC);
    if (fd < 0) {
        LOG(ERROR) << "Failed to open " << path << ": " << strerror(errno);
        return;
    }
    write(fd, val.c_str(), val.size());
    fsync(fd);
    close(fd);
}

int SchuurmanVehicleHardware::readSysFsInt(const std::string& path) {
    std::string s = readSysFsString(path);
    if (s.empty()) return -1;
    return std::stoi(s);
}

StatusCode SchuurmanVehicleHardware::setValueInternal(const VehiclePropValue& request,
                                                      VehiclePropValue* updatedValue) {
    if (request.prop == static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS)) {
        if (!request.value.int32Values.empty()) {
            int brightness = request.value.int32Values[0];
            if (!mAutoBrightnessEnabled.load()) {
                writePwm(brightness);
                mCurrentBrightness = brightness;
            } else {
                LOG(INFO) << "Manual brightness set ignored (Auto Enabled)";
            }
        }
        if (updatedValue) {
            *updatedValue = request;
            updatedValue->timestamp = elapsedRealtimeNano();
        }
        return StatusCode::OK;
    } else if (request.prop == VENDOR_SCREEN_POWER) {
        if (!request.value.int32Values.empty()) {
            bool on = (request.value.int32Values[0] == 1);
            setBacklightEnable(on);
            mScreenOn.store(on);
            LOG(INFO) << "VHAL: Screen Power set to " << on;

            if (mOnPropChange) {
                std::vector<VehiclePropValue> events;
                VehiclePropValue v = request;
                v.timestamp = elapsedRealtimeNano();
                events.push_back(v);
                (*mOnPropChange)(events);
            }
        }
        if (updatedValue) {
            *updatedValue = request;
            updatedValue->timestamp = elapsedRealtimeNano();
        }
        return StatusCode::OK;
    } else if (request.prop == VENDOR_AUTO_BRIGHTNESS) {
        if (!request.value.int32Values.empty()) {
            bool enable = request.value.int32Values[0] == 1;
            mAutoBrightnessEnabled.store(enable);
        }
        if (updatedValue) {
            *updatedValue = request;
            updatedValue->timestamp = elapsedRealtimeNano();
        }
        return StatusCode::OK;
    }

    return StatusCode::INVALID_ARG;
}

StatusCode SchuurmanVehicleHardware::getValueInternal(const VehiclePropValue& request,
                                                      VehiclePropValue* response) const {
    response->timestamp = elapsedRealtimeNano();
    if (request.prop == static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS)) {
        response->value.int32Values = {mCurrentBrightness};
        return StatusCode::OK;
    }
    if (request.prop == static_cast<int32_t>(VehicleProperty::GEAR_SELECTION)) {
        response->value.int32Values = {mCurrentGear};
        return StatusCode::OK;
    }
    if (request.prop == VENDOR_AUTO_BRIGHTNESS) {
        response->value.int32Values = {mAutoBrightnessEnabled.load() ? 1 : 0};
        return StatusCode::OK;
    }
    if (request.prop == VENDOR_SCREEN_POWER) {
        response->value.int32Values = {mScreenOn.load() ? 1 : 0};
        return StatusCode::OK;
    }
    return StatusCode::INVALID_ARG;
}

std::vector<VehiclePropConfig> SchuurmanVehicleHardware::getAllPropertyConfigs() const {
    std::vector<VehiclePropConfig> configs;

    VehiclePropConfig gearConfig;
    gearConfig.prop = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
    gearConfig.access = VehiclePropertyAccess::READ;
    gearConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
    configs.push_back(gearConfig);

    VehiclePropConfig brightConfig;
    brightConfig.prop = static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS);
    brightConfig.access = VehiclePropertyAccess::READ_WRITE;
    brightConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
    brightConfig.areaConfigs = {{.minInt32Value = 0, .maxInt32Value = 100}};
    configs.push_back(brightConfig);

    VehiclePropConfig autoConfig;
    autoConfig.prop = VENDOR_AUTO_BRIGHTNESS;
    autoConfig.access = VehiclePropertyAccess::READ_WRITE;
    autoConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
    autoConfig.areaConfigs = {{.minInt32Value = 0, .maxInt32Value = 1}};
    configs.push_back(autoConfig);

    VehiclePropConfig screenPowerConfig;
    screenPowerConfig.prop = VENDOR_SCREEN_POWER;
    screenPowerConfig.access = VehiclePropertyAccess::READ_WRITE;
    screenPowerConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
    screenPowerConfig.areaConfigs = {{.minInt32Value = 0, .maxInt32Value = 1}};
    configs.push_back(screenPowerConfig);

    return configs;
}

void SchuurmanVehicleHardware::pollInputs() {
    int lastGearState = -1;
    while (!mShuttingDown) {
        int gearState = readGearGpio();
        if (gearState >= 0 && gearState != lastGearState) {
            mCurrentGear = (gearState == 1) ? static_cast<int32_t>(VehicleGear::GEAR_REVERSE)
                                            : static_cast<int32_t>(VehicleGear::GEAR_DRIVE);

            if (mOnPropChange) {
                std::vector<VehiclePropValue> events;
                VehiclePropValue v;
                v.prop = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
                v.timestamp = elapsedRealtimeNano();
                v.value.int32Values = {mCurrentGear};
                events.push_back(v);
                (*mOnPropChange)(events);
            }
            lastGearState = gearState;
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
            if (ema < 0)
                ema = (double)raw;
            else
                ema = alpha * (double)raw + (1.0 - alpha) * ema;

            double maxLux = (double)mSensorRawMax;
            if (maxLux < 1.0) maxLux = 1.0;
            double percent = (log(1.0 + ema) / log(1.0 + maxLux)) * 100.0;
            if (percent < 0.0) percent = 0.0;
            if (percent > 100.0) percent = 100.0;

            int intPercent = static_cast<int>(percent + 0.5);

            if (mAutoBrightnessEnabled.load()) {
                int last = mAutoTargetBrightness.load();
                if (last < 0 || abs(intPercent - last) >= 2) {
                    mAutoTargetBrightness.store(intPercent);
                    if (mScreenOn.load()) {
                        writePwm(intPercent);
                        mCurrentBrightness = intPercent;
                        if (mOnPropChange) {
                            std::vector<VehiclePropValue> events;
                            VehiclePropValue v;
                            v.prop = static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS);
                            v.timestamp = elapsedRealtimeNano();
                            v.value.int32Values = {mCurrentBrightness};
                            events.push_back(v);
                            (*mOnPropChange)(events);
                        }
                    }
                }
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(pollMs));
    }
}

// IVehicleHardware Boilerplate
StatusCode SchuurmanVehicleHardware::checkHealth() {
    return StatusCode::OK;
}
void SchuurmanVehicleHardware::registerOnPropertyChangeEvent(
        std::unique_ptr<const PropertyChangeCallback> callback) {
    mOnPropChange = std::move(callback);
}
void SchuurmanVehicleHardware::registerOnPropertySetErrorEvent(
        std::unique_ptr<const PropertySetErrorCallback> callback) {
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

// Corrected getValues logic:
// Use a temporary variable 'val' to capture the output of getValueInternal.
// Then move 'val' into 'res.prop' (which is std::optional<VehiclePropValue>).
StatusCode SchuurmanVehicleHardware::getValues(
        std::shared_ptr<const GetValuesCallback> callback,
        const std::vector<GetValueRequest>& requests) const {
    std::vector<GetValueResult> results;
    for (const auto& req : requests) {
        GetValueResult res;
        res.requestId = req.requestId;
        
        // Initialize the temp holder with request ID/AreaID info
        VehiclePropValue val = req.prop;
        
        // Pass pointer to temp variable
        res.status = getValueInternal(req.prop, &val);
        
        if (res.status == StatusCode::OK) {
            // Assign valid result to the optional field in response
            res.prop = std::move(val);
        }
        results.push_back(res);
    }
    (*callback)(std::move(results));
    return StatusCode::OK;
}

StatusCode SchuurmanVehicleHardware::setValues(std::shared_ptr<const SetValuesCallback> callback,
                                               const std::vector<SetValueRequest>& requests) {
    std::vector<SetValueResult> results;
    for (const auto& req : requests) {
        SetValueResult res;
        res.requestId = req.requestId;
        res.status = setValueInternal(req.value, nullptr);
        results.push_back(res);
    }
    (*callback)(std::move(results));
    return StatusCode::OK;
}

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android