#include "SnapVehicleHardware.h"

#include <android-base/logging.h>
#include <chrono>
#include <fstream>

// Definieer paden (Pas deze aan naar jouw werkelijke VIM3 paden!)
#define PATH_GPIO_REVERSE   "/sys/class/gpio/gpio496/value"
#define PATH_PWM_BRIGHTNESS "/sys/class/pwm/pwmchip0/pwm0/duty_cycle"
#define PATH_PWM_PERIOD     "/sys/class/pwm/pwmchip0/pwm0/period"
#define PATH_PWM_ENABLE     "/sys/class/pwm/pwmchip0/pwm0/enable"

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

// Helper om timestamps te krijgen
static int64_t elapsedRealtimeNano() {
    auto now = std::chrono::steady_clock::now();
    return std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
}

SnapVehicleHardware::SnapVehicleHardware()
    : mCurrentGear(static_cast<int32_t>(VehicleGear::GEAR_PARK)),
      mCurrentBrightness(50),
      mShuttingDown(false) {
    initPwm();
    mPollThread = std::thread(&SnapVehicleHardware::pollInputs, this);
}

SnapVehicleHardware::~SnapVehicleHardware() {
    mShuttingDown = true;
    if (mPollThread.joinable()) mPollThread.join();
}

// 1. Configuraties
std::vector<VehiclePropConfig> SnapVehicleHardware::getAllPropertyConfigs() const {
    std::vector<VehiclePropConfig> configs;

    // GEAR_SELECTION
    VehiclePropConfig gearConfig;
    gearConfig.prop = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
    gearConfig.access = VehiclePropertyAccess::READ;
    gearConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
    configs.push_back(gearConfig);

    // DISPLAY_BRIGHTNESS
    VehiclePropConfig brightConfig;
    brightConfig.prop = static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS);
    brightConfig.access = VehiclePropertyAccess::READ_WRITE;
    brightConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
    brightConfig.areaConfigs = {
        {.minInt32Value = 0, .maxInt32Value = 100}
    };
    configs.push_back(brightConfig);

    return configs;
}

// 2. Batch Get Values (Nieuw in A15)
StatusCode SnapVehicleHardware::getValues(const std::vector<GetValueRequest>& requests,
                                          std::vector<GetValueResult>* results) const {
    // Loop door alle aanvragen heen
    for (const auto& req : requests) {
        GetValueResult result;
        result.requestId = req.requestId;
        result.status = StatusCode::OK;
        
        // Roep onze interne helper aan
        // In A15 zit de 'prop' data in req.prop
        VehiclePropValue responseValue = req.prop; 
        result.status = getValueInternal(req.prop, &responseValue);
        
        if (result.status == StatusCode::OK) {
            result.prop = responseValue;
        }
        results->push_back(result);
    }
    return StatusCode::OK;
}

// Interne helper voor Get (Oude logica)
StatusCode SnapVehicleHardware::getValueInternal(const VehiclePropValue& request, VehiclePropValue* response) const {
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

// 3. Batch Set Values (Nieuw in A15)
StatusCode SnapVehicleHardware::setValues(const std::vector<SetValueRequest>& requests,
                                          std::vector<SetValueResult>* results) {
    for (const auto& req : requests) {
        SetValueResult result;
        result.requestId = req.requestId;
        result.status = StatusCode::OK;

        VehiclePropValue updatedValue = req.value;
        result.status = setValueInternal(req.value, &updatedValue);
        
        results->push_back(result);
    }
    return StatusCode::OK;
}

// Interne helper voor Set (Oude logica)
StatusCode SnapVehicleHardware::setValueInternal(const VehiclePropValue& request, VehiclePropValue* updatedValue) {
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

// 4. Dump
DumpResult SnapVehicleHardware::dump(const std::vector<std::string>& /*options*/) {
    // Voor nu lege dump
    return {};
}

// 5. Health
StatusCode SnapVehicleHardware::checkHealth() {
    return StatusCode::OK;
}

// 6. Callbacks
void SnapVehicleHardware::registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) {
    mOnPropChange = std::move(callback);
}

void SnapVehicleHardware::registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback) {
    mOnSetError = std::move(callback);
}

// 7. Subscriptions (Stubs)
StatusCode SnapVehicleHardware::subscribe(const SubscribeOptions& /*options*/) { return StatusCode::OK; }
StatusCode SnapVehicleHardware::unsubscribe(int32_t /*propId*/) { return StatusCode::OK; }
StatusCode SnapVehicleHardware::updateSampleRate(int32_t /*propId*/, float /*sampleRate*/) { return StatusCode::OK; }

// --- Hardware Logica ---

void SnapVehicleHardware::initPwm() {
    writeSysFs(PATH_PWM_PERIOD, "50000");
    writeSysFs(PATH_PWM_ENABLE, "1");
}

void SnapVehicleHardware::writePwm(int percentage) {
    int duty = (percentage * 50000) / 100;
    writeSysFs(PATH_PWM_BRIGHTNESS, std::to_string(duty));
}

void SnapVehicleHardware::pollInputs() {
    int lastGpioState = -1;
    while (!mShuttingDown) {
        std::ifstream gpioFile(PATH_GPIO_REVERSE);
        int currentState;
        if (gpioFile >> currentState) {
            if (currentState != lastGpioState) {
                mCurrentGear = (currentState == 1) ?
                               static_cast<int32_t>(VehicleGear::GEAR_REVERSE) :
                               static_cast<int32_t>(VehicleGear::GEAR_DRIVE);

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
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
}

void SnapVehicleHardware::writeSysFs(const std::string& path, const std::string& val) {
    std::ofstream file(path);
    if (file.is_open()) file << val;
    else LOG(ERROR) << "Kan niet schrijven naar: " << path;
}

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android