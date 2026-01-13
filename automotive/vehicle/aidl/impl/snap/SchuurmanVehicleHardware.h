#ifndef ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMANVEHICLEHARDWARE_H
#define ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMANVEHICLEHARDWARE_H

#include <IVehicleHardware.h>

#include <aidl/android/hardware/automotive/vehicle/BnVehicle.h>
#include <android-base/thread_annotations.h>

#include <atomic>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

// Only use AIDL types here. Implementation types come from IVehicleHardware.
using ::aidl::android::hardware::automotive::vehicle::GetValueRequest;
using ::aidl::android::hardware::automotive::vehicle::GetValueResult;
using ::aidl::android::hardware::automotive::vehicle::SetValueRequest;
using ::aidl::android::hardware::automotive::vehicle::SetValueResult;
using ::aidl::android::hardware::automotive::vehicle::StatusCode;
using ::aidl::android::hardware::automotive::vehicle::SubscribeOptions;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropConfig;
using ::aidl::android::hardware::automotive::vehicle::VehiclePropValue;

class SchuurmanVehicleHardware : public IVehicleHardware {
  public:
    SchuurmanVehicleHardware();
    ~SchuurmanVehicleHardware();

    std::vector<VehiclePropConfig> getAllPropertyConfigs() const override;
    StatusCode getValues(std::shared_ptr<const GetValuesCallback> callback,
                         const std::vector<GetValueRequest>& requests) const override;
    StatusCode setValues(std::shared_ptr<const SetValuesCallback> callback,
                         const std::vector<SetValueRequest>& requests) override;
    StatusCode checkHealth() override;

    void registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) override;
    void registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback) override;

    StatusCode subscribe(SubscribeOptions options) override;
    StatusCode unsubscribe(int32_t propId, int32_t areaId) override;
    StatusCode updateSampleRate(int32_t propId, int32_t areaId, float sampleRate) override;

    DumpResult dump(const std::vector<std::string>& options) override;

    void initPwm();
    void initGpios();

  private:
    StatusCode getValueInternal(const VehiclePropValue& request, VehiclePropValue* response) const;
    StatusCode setValueInternal(const VehiclePropValue& request, VehiclePropValue* updatedValue);

    void pollInputs();
    void sensorLoop();

    // Hardware Control Helpers
    void writePwm(int percentage);
    void setBacklightEnable(bool on);
    int readGearGpio();

    // Sysfs Helpers
    void writeSysFs(const std::string& path, const std::string& val);
    int readSysFsInt(const std::string& path);
    void ensurePwmExported(const std::string& base);

    // Safe callback emission
    void emitPropChange(const VehiclePropValue& v);
    void emitInitialStatesLocked() REQUIRES(mCallbackMutex);

    // State Variables (thread-safe)
    std::atomic<int32_t> mCurrentGear;
    std::atomic<int32_t> mCurrentBrightness;
    std::atomic<bool> mScreenOn;

    // GPIO Configuration
    std::string mGpioChipName;
    int mGearGpioOffset;
    int mBrightnessGpioOffset;
    int mBacklightEnableGpioOffset;

    // GPIO Handles
    int mBacklightEnableFd;
    int mGearFd; // [ADDED] Persistent handle for gear input

    // PWM Paths
    std::string mPwmChipBase;
    std::string mPathPwmDuty;
    std::string mPathPwmEnable;
    std::string mPathPwmPeriod;

    // Threading
    std::atomic<bool> mShuttingDown;
    std::thread mPollThread;

    std::atomic<bool> mSensorThreadRunning;
    std::thread mSensorThread;
    std::string mLightSensorPath;
    int mSensorRawMax;

    std::atomic<bool> mAutoBrightnessEnabled;
    std::atomic<int> mAutoTargetBrightness;

    // Callbacks (protected)
    mutable std::mutex mCallbackMutex;
    std::unique_ptr<const PropertyChangeCallback> mOnPropChange GUARDED_BY(mCallbackMutex);
    std::unique_ptr<const PropertySetErrorCallback> mOnSetError GUARDED_BY(mCallbackMutex);
};

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android

#endif  // ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMANVEHICLEHARDWARE_H