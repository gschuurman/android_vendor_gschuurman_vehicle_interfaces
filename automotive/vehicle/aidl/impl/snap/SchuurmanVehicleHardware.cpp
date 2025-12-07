#include "SchuurmanVehicleHardware.h"

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <chrono>
#include <fstream>
#include <thread>
#include <vector>

// Linux Kernel Headers
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <linux/gpio.h> 
#include <string.h>

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

SchuurmanVehicleHardware::SchuurmanVehicleHardware()
    : mCurrentGear(static_cast<int32_t>(VehicleGear::GEAR_PARK)),
      mCurrentBrightness(50),
      mShuttingDown(false) {

    // 1. PWM Paden (String Properties)
    mPathPwmDuty = android::base::GetProperty("ro.vendor.vehicle.path.pwm.duty", "/sys/class/pwm/pwmchip1/pwm1/duty_cycle");
    mPathPwmEnable = android::base::GetProperty("ro.vendor.vehicle.path.pwm.enable", "/sys/class/pwm/pwmchip1/pwm1/enable");
    mPathPwmPeriod = android::base::GetProperty("ro.vendor.vehicle.path.pwm.period", "/sys/class/pwm/pwmchip1/pwm1/period");

    // 2. PWM Configuratie (Int/Bool Properties)
    // Lees de gewenste periode uit property. Default 30518 (32kHz) voor VIM3.
    mPwmPeriodNs = android::base::GetIntProperty("ro.vendor.vehicle.pwm.period_ns", 30518);
    
    // Lees of we de periode moeten overschrijven (Default false/0 voor VIM3 WiFi veiligheid)
    bool forceWritePeriod = android::base::GetBoolProperty("ro.vendor.vehicle.pwm.force_write_period", false);

    // 3. GPIO Config
    std::string chipName = android::base::GetProperty("ro.vendor.vehicle.gpio.chip", "gpiochip0");
    if (chipName.find("/dev/") == std::string::npos) {
        mGpioChipName = "/dev/" + chipName;
    } else {
        mGpioChipName = chipName;
    }
    mGpioLineOffset = android::base::GetIntProperty("ro.vendor.vehicle.gpio.offset", 0);

    LOG(INFO) << "SchuurmanVehicleHardware Configured:"
              << "\n PWM Path: " << mPathPwmDuty
              << "\n PWM Period Config: " << mPwmPeriodNs << " ns"
              << "\n Force Write Period: " << (forceWritePeriod ? "YES" : "NO");

    initPwm(forceWritePeriod); // Geef de setting mee
    mPollThread = std::thread(&SchuurmanVehicleHardware::pollInputs, this);
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
        if (request.value.int32Values.empty()) return StatusCode::INVALID_ARG;
        int brightness = request.value.int32Values[0];
        if (brightness < 0 || brightness > 100) return StatusCode::INVALID_ARG;
        
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
    // Probeer eerst de huidige waarde uit sysfs te lezen ter controle
    int currentSysPeriod = readSysFsInt(mPathPwmPeriod);
    if (currentSysPeriod > 0) {
        LOG(INFO) << "System reports current PWM period: " << currentSysPeriod;
    }

    if (forceWrite) {
        // Alleen schrijven als de property dit toestaat!
        LOG(INFO) << "Forcing PWM period to " << mPwmPeriodNs;
        writeSysFs(mPathPwmPeriod, std::to_string(mPwmPeriodNs));
    } else {
        LOG(INFO) << "Skipping PWM period write (safety mode)";
        mPwmPeriodNs = currentSysPeriod;
    }
    writeSysFs(mPathPwmEnable, "1");
}

void SchuurmanVehicleHardware::writePwm(int percentage) {
    // 1. Inverted logic: 100% helderheid = 0% duty (0V)
    int invertedPercentage = 100 - percentage;
    
    // 2. Duty cycle berekenen met de UITGELEZEN periode
    int duty = (invertedPercentage * mPwmPeriodNs) / 100;
    
    // 3. Schrijf de waarde
    writeSysFs(mPathPwmDuty, std::to_string(duty));
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
    std::ofstream file(path);
    if (file.is_open()) file << val;
    else LOG(WARNING) << "Failed to write to path: " << path;
}

int SchuurmanVehicleHardware::readSysFsInt(const std::string &path) {
    std::ifstream file(path);
    int value = -1;
    if (file.is_open()) {
        file >> value;
    } else {
        LOG(WARNING) << "Failed to read from path: " << path;
    }
    return value;
}

} // vehicle
} // automotive
} // hardware
} // android