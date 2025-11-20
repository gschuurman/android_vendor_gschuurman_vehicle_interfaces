#ifndef ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SNAP_IMPL_H
#define ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SNAP_IMPL_H

#include <vector>
#include <thread>
#include <atomic>
#include <memory>

// In Android 15 moeten we de AIDL headers gebruiken
#include <aidl/android/hardware/automotive/vehicle/IVehicle.h>
#include <aidl/android/hardware/automotive/vehicle/IVehicleHardware.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleProperty.h>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

// Gebruik aliassen om de code leesbaar te houden
using ::aidl::android::hardware::automotive::vehicle::IVehicleHardware;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropConfig;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropValue;
using ::aidl::android::hardware::automotive::vehicle::StatusCode;
using ::aidl::android::hardware::automotive::vehicle::GetValueRequest;
using ::aidl::android::hardware::automotive::vehicle::GetValueResult;
using ::aidl::android::hardware::automotive::vehicle::SetValueRequest;
using ::aidl::android::hardware::automotive::vehicle::SetValueResult;
using ::aidl::android::hardware::automotive::vehicle::DumpResult; // Nieuw in A15
using ::aidl::android::hardware::automotive::vehicle::VehicleGear;
using ::aidl::android::hardware::automotive::vehicle::VehicleProperty;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyAccess;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyChangeMode;
using ::aidl::android::hardware::automotive::vehicle::SubscribeOptions;

class SnapVehicleHardware : public IVehicleHardware {
public:
    SnapVehicleHardware();
    ~SnapVehicleHardware();

    // --- IVehicleHardware Interface Implementatie (Android 15 V3) ---

    // 1. Configuraties ophalen
    std::vector<VehiclePropConfig> getAllPropertyConfigs() const override;

    // 2. Waarden ophalen (Batch)
    // Let op: Android 15 gebruikt getValues (meervoud) met requests en results pointers
    StatusCode getValues(const std::vector<GetValueRequest>& requests,
                         std::vector<GetValueResult>* results) const override;

    // 3. Waarden instellen (Batch)
    StatusCode setValues(const std::vector<SetValueRequest>& requests,
                         std::vector<SetValueResult>* results) override;

    // 4. Dump (Nieuwe return type DumpResult)
    DumpResult dump(const std::vector<std::string>& options) override;

    // 5. Health Check
    StatusCode checkHealth() override;

    // 6. Callbacks registreren
    void registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) override;
    
    // 7. Error Events (Nieuw verplicht in A15)
    void registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback) override;

    // 8. Subscription methods (Niet gebruikt in default impl, maar moeten bestaan)
    StatusCode subscribe(const SubscribeOptions& options) override;
    StatusCode unsubscribe(int32_t propId) override;
    
    // 9. Update Sample Rate (Nieuw verplicht in A15, soms optioneel afhankelijk van base class, we voegen hem toe voor zekerheid)
    StatusCode updateSampleRate(int32_t propId, float sampleRate) override;

private:
    // Interne state
    int32_t mCurrentGear;
    int32_t mCurrentBrightness;

    std::thread mPollThread;
    std::atomic<bool> mShuttingDown;
    std::unique_ptr<const PropertyChangeCallback> mOnPropChange;
    // Error callback opslaan is optioneel als we geen async errors sturen, maar netjes om te hebben
    std::unique_ptr<const PropertySetErrorCallback> mOnSetError;

    // Helpers
    void initPwm();
    void writePwm(int percentage);
    void pollInputs();
    void writeSysFs(const std::string& path, const std::string& val);
    
    // Helper voor enkele requests (om de batch loop schoon te houden)
    StatusCode getValueInternal(const VehiclePropValue& request, VehiclePropValue* response) const;
    StatusCode setValueInternal(const VehiclePropValue& request, VehiclePropValue* updatedValue);
};

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android

#endif  // ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SNAP_IMPL_H