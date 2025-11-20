#ifndef ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SNAP_IMPL_H
#define ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SNAP_IMPL_H

#include <vector>
#include <thread>
#include <atomic>
#include <memory>

// C++ Helper Interface
#include <IVehicleHardware.h>

// AIDL Interfaces
#include <aidl/android/hardware/automotive/vehicle/IVehicle.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleProperty.h>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

// --- Namespace Aliassen ---

// C++ Types
using ::android::hardware::automotive::vehicle::IVehicleHardware;
using ::android::hardware::automotive::vehicle::DumpResult;

// AIDL Types
using ::aidl::android::hardware::automotive::vehicle::VehiclePropConfig;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropValue;
using ::aidl::android::hardware::automotive::vehicle::StatusCode;
using ::aidl::android::hardware::automotive::vehicle::GetValueRequest;
using ::aidl::android::hardware::automotive::vehicle::GetValueResult;
using ::aidl::android::hardware::automotive::vehicle::SetValueRequest;
using ::aidl::android::hardware::automotive::vehicle::SetValueResult;
using ::aidl::android::hardware::automotive::vehicle::VehicleProperty;
using ::aidl::android::hardware::automotive::vehicle::SubscribeOptions;

class SnapVehicleHardware : public IVehicleHardware {
public:
    SnapVehicleHardware();
    ~SnapVehicleHardware();

    std::vector<VehiclePropConfig> getAllPropertyConfigs() const override;

    StatusCode getValues(std::shared_ptr<const GetValuesCallback> callback,
                         const std::vector<GetValueRequest>& requests) const override;

    StatusCode setValues(std::shared_ptr<const SetValuesCallback> callback,
                         const std::vector<SetValueRequest>& requests) override;

    DumpResult dump(const std::vector<std::string>& options) override;
    StatusCode checkHealth() override;
    void registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) override;
    void registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback) override;

    StatusCode subscribe(SubscribeOptions options) override;
    StatusCode unsubscribe(int32_t propId, int32_t areaId) override;
    StatusCode updateSampleRate(int32_t propId, int32_t areaId, float sampleRate) override;

private:
    int32_t mCurrentGear;
    int32_t mCurrentBrightness;

    std::thread mPollThread;
    std::atomic<bool> mShuttingDown;
    
    std::string mPathPwmDuty;
    std::string mPathPwmEnable;
    std::string mPathPwmPeriod;
    std::string mPathGpioReverse;

    // Callbacks
    std::unique_ptr<const PropertyChangeCallback> mOnPropChange;
    std::unique_ptr<const PropertySetErrorCallback> mOnSetError;

    void initPwm();
    void writePwm(int percentage);
    void pollInputs();
    void writeSysFs(const std::string& path, const std::string& val);
    
    StatusCode getValueInternal(const VehiclePropValue& request, VehiclePropValue* response) const;
    StatusCode setValueInternal(const VehiclePropValue& request, VehiclePropValue* updatedValue);
};

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android

#endif  // ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SNAP_IMPL_H