#include "GSchuurmanVehicleHardware.h"
#include <android-base/logging.h>
#include <VehicleUtils.h>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {
namespace gschuurman {

using ::aidl::android::hardware::automotive::vehicle::SetValueRequest;
using ::aidl::android::hardware::automotive::vehicle::GetValueRequest;
using ::aidl::android::hardware::automotive::vehicle::StatusCode;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropConfig;
using ::aidl::android::hardware::automotive::vehicle::VehicleProperty;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyAccess;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyChangeMode;
using ::aidl::android::hardware::automotive::vehicle::VehicleAreaConfig;
using ::aidl::android::hardware::automotive::vehicle::VehicleGear;

// Internal state storage (since we have no CAN bus to ask)
// Default to PARK to be safe
int32_t currentGear = toInt(VehicleGear::GEAR_PARK);
float currentSpeed = 0.0f;

GSchuurmanVehicleHardware::GSchuurmanVehicleHardware() {
    LOG(INFO) << "GSchuurman VHAL Hardware initialized (No-CAN Mode)";
}

std::vector<VehiclePropConfig> GSchuurmanVehicleHardware::getAllPropertyConfigs() const {
    std::vector<VehiclePropConfig> configs;

    // 1. Vehicle Speed (Required for many apps)
    VehiclePropConfig speedConfig;
    speedConfig.prop = toInt(VehicleProperty::PERF_VEHICLE_SPEED);
    speedConfig.access = VehiclePropertyAccess::READ;
    speedConfig.changeMode = VehiclePropertyChangeMode::CONTINUOUS;
    speedConfig.minSampleRate = 1.0f;
    speedConfig.maxSampleRate = 100.0f;
    configs.push_back(speedConfig);

    // 2. Gear Selection (CRITICAL FOR REVERSE CAMERA)
    // We make this READ_WRITE so you can toggle it via ADB or a future GPIO script
    VehiclePropConfig gearConfig;
    gearConfig.prop = toInt(VehicleProperty::GEAR_SELECTION);
    gearConfig.access = VehiclePropertyAccess::READ_WRITE;
    gearConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
    configs.push_back(gearConfig);

    LOG(INFO) << "Providing " << configs.size() << " property configs";
    return configs;
}

StatusCode GSchuurmanVehicleHardware::getValues(
        std::shared_ptr<const GetValuesCallback> callback,
        const std::vector<GetValueRequest>& requests) const {
    
    for (const auto& request : requests) {
        auto result = ::aidl::android::hardware::automotive::vehicle::GetValueResult();
        result.requestId = request.requestId;
        result.prop = request.prop;
        result.prop.timestamp = (int64_t)systemTime(SYSTEM_TIME_MONOTONIC);
        
        if (request.prop.prop == toInt(VehicleProperty::PERF_VEHICLE_SPEED)) {
            result.status = StatusCode::OK;
            result.prop.value.floatValues = {currentSpeed};
        } 
        else if (request.prop.prop == toInt(VehicleProperty::GEAR_SELECTION)) {
            result.status = StatusCode::OK;
            result.prop.value.int32Values = {currentGear};
        } 
        else {
            result.status = StatusCode::INVALID_ARG;
        }
        
        (*callback)({result});
    }
    return StatusCode::OK;
}

StatusCode GSchuurmanVehicleHardware::setValues(
        std::shared_ptr<const SetValuesCallback> callback,
        const std::vector<SetValueRequest>& requests) {
    
    for (const auto& request : requests) {
        auto result = ::aidl::android::hardware::automotive::vehicle::SetValueResult();
        result.requestId = request.requestId;
        
        if (request.value.prop == toInt(VehicleProperty::GEAR_SELECTION)) {
            // Allow changing gears via software (ADB)
            // Example: cmd car_service put-value 289408000 4 (Shift to Reverse)
            if (request.value.value.int32Values.size() > 0) {
                currentGear = request.value.value.int32Values[0];
                result.status = StatusCode::OK;
                
                // Notify Android that property changed (Triggers Camera if Reverse)
                if (mOnPropertyChange) {
                    std::vector<aidl::android::hardware::automotive::vehicle::VehiclePropValue> updatedValues;
                    updatedValues.push_back(request.value);
                    mOnPropertyChange->onPropertyEvent(updatedValues);
                }
            } else {
                result.status = StatusCode::INVALID_ARG;
            }
        } else {
            result.status = StatusCode::ACCESS_DENIED;
        }

        (*callback)({result});
    }
    return StatusCode::OK;
}

StatusCode GSchuurmanVehicleHardware::subscribe(
        std::shared_ptr<const SubscribeCallback> callback,
        const std::vector<aidl::android::hardware::automotive::vehicle::SubscribeOptions>& options) {
    return StatusCode::OK;
}

StatusCode GSchuurmanVehicleHardware::unsubscribe(
        std::shared_ptr<const SubscribeCallback> callback,
        const std::vector<int32_t>& propIds) {
    return StatusCode::OK;
}

void GSchuurmanVehicleHardware::registerOnPropertyChangeEvent(
        std::unique_ptr<const PropertyChangeCallback> callback) {
    mOnPropertyChange = std::move(callback);
}

}  // namespace gschuurman
}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android