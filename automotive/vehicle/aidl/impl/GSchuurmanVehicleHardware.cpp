#ifndef ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_AIDL_IMPL_GSCHUURMANVEHICLEHARDWARE_H
#define ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_AIDL_IMPL_GSCHUURMANVEHICLEHARDWARE_H

#include <IVehicleHardware.h>
#include <android-base/thread_annotations.h>
#include <memory>
#include <vector>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {
namespace gschuurman {

// We erven van IVehicleHardware. Dit is de interface die DefaultVehicleHal verwacht.
class GSchuurmanVehicleHardware : public IVehicleHardware {
  public:
    GSchuurmanVehicleHardware();
    virtual ~GSchuurmanVehicleHardware() = default;

    // Initialisatie van de hardware (Connectie maken met CAN interface)
    std::vector<aidl::android::hardware::automotive::vehicle::VehiclePropConfig> getAllPropertyConfigs() const override;
    
    // Property opvragen (Get)
    aidl::android::hardware::automotive::vehicle::StatusCode getValues(
            std::shared_ptr<const GetValuesCallback> callback,
            const std::vector<aidl::android::hardware::automotive::vehicle::GetValueRequest>& requests) const override;

    // Property instellen (Set)
    aidl::android::hardware::automotive::vehicle::StatusCode setValues(
            std::shared_ptr<const SetValuesCallback> callback,
            const std::vector<aidl::android::hardware::automotive::vehicle::SetValueRequest>& requests) override;

    // Abonnementen beheren (voor async events zoals snelheidswijzigingen)
    aidl::android::hardware::automotive::vehicle::StatusCode subscribe(
            std::shared_ptr<const SubscribeCallback> callback,
            const std::vector<aidl::android::hardware::automotive::vehicle::SubscribeOptions>& options) override;

    aidl::android::hardware::automotive::vehicle::StatusCode unsubscribe(
            std::shared_ptr<const SubscribeCallback> callback,
            const std::vector<int32_t>& propIds) override;

    // Optioneel: Health checks
    aidl::android::hardware::automotive::vehicle::StatusCode checkHealth() const override {
        return aidl::android::hardware::automotive::vehicle::StatusCode::OK;
    }
    
    void registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) override;
    
    // Dummy functie om updates te triggeren (voor later)
    void updateSpeed(float speed);

  private:
    std::unique_ptr<const PropertyChangeCallback> mOnPropertyChange;
};

}  // namespace gschuurman
}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android

#endif  // ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_AIDL_IMPL_GSCHUURMANVEHICLEHARDWARE_H