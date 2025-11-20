#ifndef ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SNAP_IMPL_H
#define ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SNAP_IMPL_H

#include <vector>
#include <thread>
#include <atomic>
#include <memory>

#include "IVehicleHardware.h"

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

class SnapVehicleHardware : public IVehicleHardware {
public:
    SnapVehicleHardware();
    ~SnapVehicleHardware();

    // --- IVehicleHardware Interface Implementatie ---
    
    std::vector<VehiclePropConfig> getAllPropertyConfigs() const override;
    
    StatusCode getValue(const VehiclePropValue& request, VehiclePropValue* response) const override;
    
    StatusCode setValue(const VehiclePropValue& request, VehiclePropValue* updatedValue) override;

    // Boilerplate methoden (verplicht door interface)
    StatusCode dump(int fd, const std::vector<std::string>& args) override;
    StatusCode checkHealth() override;
    void registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) override;
    StatusCode subscribe(const SubscribeOptions& options) override;
    StatusCode unsubscribe(int32_t propId) override;

private:
    // Interne state variabelen
    int32_t mCurrentGear;
    int32_t mCurrentBrightness;
    
    // Threading & Callbacks
    std::thread mPollThread;
    std::atomic<bool> mShuttingDown;
    std::unique_ptr<const PropertyChangeCallback> mOnPropChange;

    // Helper functies
    void initPwm();
    void writePwm(int percentage);
    void pollInputs();
    void writeSysFs(const std::string& path, const std::string& val);
};

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android

#endif  // ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SNAP_IMPL_H