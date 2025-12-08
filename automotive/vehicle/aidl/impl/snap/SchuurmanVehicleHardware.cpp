#include "SchuurmanVehicleHardware.h"

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <chrono>
#include <fstream>
#include <thread>
#include <vector>

#include <filesystem>
#include <regex>
#include <iostream>

// Linux Kernel Headers
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/gpio.h> 
#include <string.h>
#include <errno.h> // <--- TOEGEVOEGD VOOR FOUTCODES

#include <aidl/android/hardware/automotive/vehicle/VehicleGear.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyAccess.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyChangeMode.h>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

using ::aidl::android::hardware::automotive::vehicle::VehicleGear;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyAccess;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyChangeMode;

static int64_t elapsedRealtimeNano() {
    auto now = std::chrono::steady_clock::now();
    return std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
}

std::string findPwmChipPath() {
    // We zoeken naar een map in /sys/class/pwm/pwmchipX
    // waarvan de symlink 'device/of_node' de tekst '19000' bevat.

    std::string baseDir = "/sys/class/pwm/";
    for (int i = 0; i < 10; i++) {
        std::string chipName = "pwmchip" + std::to_string(i);
        std::string fullPath = baseDir + chipName;
        std::string linkPath = fullPath + "/device/of_node";

        // Check of symlink bestaat
        char buf[1024];
        ssize_t len = readlink(linkPath.c_str(), buf, sizeof(buf)-1);
        if (len != -1) {
            buf[len] = '\0';
            std::string target(buf);

            // BINGO CHECK
            if (target.find("19000") != std::string::npos) {
                LOG(INFO) << "Auto-detected PWM Chip: " << chipName << " (Matches 19000)";
                return fullPath; // Geeft "/sys/class/pwm/pwmchipX" terug
            }
        }
    }
    LOG(ERROR) << "Could not auto-detect PWM chip 19000! Fallback to pwmchip0.";
    return baseDir + "pwmchip0";
}


SchuurmanVehicleHardware::SchuurmanVehicleHardware()
    : mCurrentGear(static_cast<int32_t>(VehicleGear::GEAR_PARK)),
      mCurrentBrightness(50),
      mShuttingDown(false) {

    LOG(INFO) << ">>> DETECTING HARDWARE <<<";
    std::string chipBase = findPwmChipPath();

    LOG(INFO) << ">>> STARTING SchuurmanVehicleHardware INITIALIZATION <<<";

    // We nemen aan dat kanaal 1 (pwm1) altijd correct is voor VIM3 pin 35
    mPathPwmDuty = chipBase + "/pwm1/duty_cycle";
    mPathPwmEnable = chipBase + "/pwm1/enable";
    mPathPwmPeriod = chipBase + "/pwm1/period";

    LOG(INFO) << "Resolved Paths:";
    LOG(INFO) << "  Duty: " << mPathPwmDuty;
    
    // Default 30518 (32kHz)
    mPwmPeriodNs = android::base::GetIntProperty("ro.vendor.vehicle.pwm.period_ns", 30518);
    bool forceWritePeriod = android::base::GetBoolProperty("ro.vendor.vehicle.pwm.force_write_period", false);

    LOG(INFO) << "CONFIG - Duty Path:   " << mPathPwmDuty;
    LOG(INFO) << "CONFIG - Enable Path: " << mPathPwmEnable;
    LOG(INFO) << "CONFIG - Period Path: " << mPathPwmPeriod;
    LOG(INFO) << "CONFIG - Target Period: " << mPwmPeriodNs << " ns";
    LOG(INFO) << "CONFIG - Force Write: " << (forceWritePeriod ? "YES" : "NO");

    // GPIO Config
    std::string chipName = android::base::GetProperty("ro.vendor.vehicle.gpio.chip", "gpiochip0");
    if (chipName.find("/dev/") == std::string::npos) {
        mGpioChipName = "/dev/" + chipName;
    } else {
        mGpioChipName = chipName;
    }
    mGpioLineOffset = android::base::GetIntProperty("ro.vendor.vehicle.gpio.offset", 16);
    
    LOG(INFO) << "CONFIG - GPIO Chip: " << mGpioChipName << ", Line: " << mGpioLineOffset;

    // 2. Initialiseer Hardware
    initPwm(forceWritePeriod);

    // 3. Start Poll Thread
    mPollThread = std::thread(&SchuurmanVehicleHardware::pollInputs, this);
    
    LOG(INFO) << ">>> SchuurmanVehicleHardware INITIALIZATION DONE <<<";
}

SchuurmanVehicleHardware::~SchuurmanVehicleHardware() {
    mShuttingDown = true;
    if (mPollThread.joinable()) mPollThread.join();
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

    return configs;
}

StatusCode SchuurmanVehicleHardware::getValues(std::shared_ptr<const GetValuesCallback> callback, const std::vector<GetValueRequest> &requests) const {
    std::vector<GetValueResult> results;
    for (const auto &req : requests) {
        GetValueResult result;
        result.requestId = req.requestId;
        VehiclePropValue responseValue = req.prop;
        result.status = getValueInternal(req.prop, &responseValue);
        if (result.status == StatusCode::OK) result.prop = responseValue;
        results.push_back(result);
    }
    (*callback)(std::move(results));
    return StatusCode::OK;
}

StatusCode SchuurmanVehicleHardware::getValueInternal(const VehiclePropValue &request, VehiclePropValue *response) const {
    int32_t propId = request.prop;
    response->timestamp = elapsedRealtimeNano();
    if (propId == static_cast<int32_t>(VehicleProperty::GEAR_SELECTION)) {
        response->value.int32Values = {mCurrentGear};
        return StatusCode::OK;
    } else if (propId == static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS)) {
        response->value.int32Values = {mCurrentBrightness};
        return StatusCode::OK;
    }
    return StatusCode::INVALID_ARG;
}

StatusCode SchuurmanVehicleHardware::setValues(std::shared_ptr<const SetValuesCallback> callback, const std::vector<SetValueRequest> &requests) {
    std::vector<SetValueResult> results;
    for (const auto &req : requests) {
        SetValueResult result;
        result.requestId = req.requestId;
        VehiclePropValue updatedValue = req.value;
        result.status = setValueInternal(req.value, &updatedValue);
        results.push_back(result);
    }
    (*callback)(std::move(results));
    return StatusCode::OK;
}

StatusCode SchuurmanVehicleHardware::setValueInternal(const VehiclePropValue &request, VehiclePropValue *updatedValue) {
    int32_t propId = request.prop;
    
    if (propId == static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS)) {
        if (request.value.int32Values.empty()) {
            LOG(ERROR) << "SET Request received but value list is empty!";
            return StatusCode::INVALID_ARG;
        }

        int brightness = request.value.int32Values[0];
        LOG(INFO) << "SET Request: Display Brightness -> " << brightness << "%";

        if (brightness < 0 || brightness > 100) {
             LOG(ERROR) << "Brightness value out of range (0-100): " << brightness;
             return StatusCode::INVALID_ARG;
        }
        
        writePwm(brightness);
        mCurrentBrightness = brightness;
        
        if (updatedValue) {
            *updatedValue = request;
            updatedValue->timestamp = elapsedRealtimeNano();
        }
        return StatusCode::OK;
    }
    return StatusCode::ACCESS_DENIED;
}

DumpResult SchuurmanVehicleHardware::dump(const std::vector<std::string> &) { return {}; }
StatusCode SchuurmanVehicleHardware::checkHealth() { return StatusCode::OK; }
void SchuurmanVehicleHardware::registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) { mOnPropChange = std::move(callback); }
void SchuurmanVehicleHardware::registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback) { mOnSetError = std::move(callback); }
StatusCode SchuurmanVehicleHardware::subscribe(SubscribeOptions) { return StatusCode::OK; }
StatusCode SchuurmanVehicleHardware::unsubscribe(int32_t, int32_t) { return StatusCode::OK; }
StatusCode SchuurmanVehicleHardware::updateSampleRate(int32_t, int32_t, float) { return StatusCode::OK; }

void SchuurmanVehicleHardware::initPwm(bool forceWrite) {
    LOG(INFO) << "--- initPwm() START ---";

    // 1. Probeer huidige periode te lezen
    int currentSysPeriod = readSysFsInt(mPathPwmPeriod);
    LOG(INFO) << "Current Kernel PWM Period: " << currentSysPeriod;

    // 2. Periode instellen (indien nodig)
    if (forceWrite) {
        LOG(INFO) << "Force Write Period is TRUE. Writing " << mPwmPeriodNs << " to " << mPathPwmPeriod;
        writeSysFs(mPathPwmPeriod, std::to_string(mPwmPeriodNs));
    } else {
        LOG(INFO) << "Force Write Period is FALSE. Skipping period write (WiFi safety).";
    }

    // 3. PWM Enable aanzetten
    LOG(INFO) << "Enabling PWM chip...";
    writeSysFs(mPathPwmEnable, "1");
    
    LOG(INFO) << "--- initPwm() END ---";
}

void SchuurmanVehicleHardware::writePwm(int percentage) {
    LOG(INFO) << "--- writePwm(" << percentage << "%) START ---";
    writeSysFs(mPathPwmEnable, "1");
    int invertedPercentage = 100 - percentage;
    int duty = (invertedPercentage * mPwmPeriodNs) / 100;
    
    LOG(INFO) << "Calculation: (100 - " << percentage << ") * " << mPwmPeriodNs << " / 100 = " << duty;
    
    // 3. Schrijf Duty
    LOG(INFO) << "Writing Duty Cycle: " << duty;
    writeSysFs(mPathPwmDuty, std::to_string(duty));
    
    LOG(INFO) << "--- writePwm() END ---";
}

int SchuurmanVehicleHardware::readGpio() {
    int fd = open(mGpioChipName.c_str(), O_RDWR);
    if (fd < 0) {
        static bool loggedError = false;
        if (!loggedError) {
            LOG(ERROR) << "Could not open GPIO chip: " << mGpioChipName << " " << strerror(errno);
            loggedError = true;
        }
        return -1;
    }

    struct gpiohandle_request req;
    memset(&req, 0, sizeof(req));
    req.lineoffsets[0] = mGpioLineOffset;
    req.lines = 1;
    req.flags = GPIOHANDLE_REQUEST_INPUT;
    
    int ret = ioctl(fd, GPIO_GET_LINEHANDLE_IOCTL, &req);
    if (ret < 0) {
        LOG(ERROR) << "Failed to get GPIO line handle (offset " << mGpioLineOffset << ")";
        close(fd);
        return -1;
    }

    struct gpiohandle_data data;
    memset(&data, 0, sizeof(data));
    ret = ioctl(req.fd, GPIOHANDLE_GET_LINE_VALUES_IOCTL, &data);
    
    close(req.fd);
    close(fd);

    if (ret < 0) return -1;
    return data.values[0];
}

void SchuurmanVehicleHardware::pollInputs() {
    int lastGpioState = -1;
    while (!mShuttingDown) {
        int currentState = readGpio();
        if (currentState >= 0 && currentState != lastGpioState) {
            mCurrentGear = (currentState == 1) ? static_cast<int32_t>(VehicleGear::GEAR_REVERSE) : static_cast<int32_t>(VehicleGear::GEAR_DRIVE);
            if (mOnPropChange) {
                std::vector<VehiclePropValue> events;
                VehiclePropValue v;
                v.prop = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
                v.timestamp = elapsedRealtimeNano();
                v.value.int32Values = {mCurrentGear};
                events.push_back(v);
                (*mOnPropChange)(events);
            }
            lastGpioState = currentState;
            LOG(INFO) << "Gear changed to: " << (currentState == 1 ? "REVERSE" : "DRIVE");
        } 
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
}

void SchuurmanVehicleHardware::writeSysFs(const std::string &path, const std::string &val) {
    LOG(INFO) << "SYSFS: Opening " << path << " to write '" << val << "'";

    // Gebruik low-level open() voor betere foutcodes (errno)
    int fd = open(path.c_str(), O_WRONLY | O_TRUNC);
    
    if (fd < 0) {
        // NU ZIEN WE WAAROM HET FAALT (Permission Denied / No such file / etc)
        LOG(ERROR) << "SYSFS FATAL: Failed to open " << path 
                   << ". Error: " << strerror(errno) << " (" << errno << ")";
        return;
    }

    int len = val.length();
    int written = write(fd, val.c_str(), len);

    if (written != len) {
        LOG(ERROR) << "SYSFS ERROR: Failed to write content. Error: " << strerror(errno);
    } else {
        LOG(INFO) << "SYSFS SUCCESS: Wrote '" << val << "'";
    }

    close(fd);
}

int SchuurmanVehicleHardware::readSysFsInt(const std::string &path) {
    LOG(INFO) << "SYSFS: Reading from " << path;
    std::ifstream file(path);
    int value = -1;
    if (file.is_open()) {
        file >> value;
        LOG(INFO) << "SYSFS READ RESULT: " << value;
    } else {
        LOG(WARNING) << "SYSFS WARN: Failed to read from path: " << path;
    }
    return value;
}

} // vehicle
} // automotive
} // hardware
} // android