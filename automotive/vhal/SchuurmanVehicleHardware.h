#ifndef ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMANVEHICLEHARDWARE_H
#define ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMANVEHICLEHARDWARE_H

#include <IVehicleHardware.h>
#include <aidl/android/hardware/automotive/vehicle/BnVehicle.h>
#include <android-base/thread_annotations.h>

#include <atomic>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

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

    void registerOnPropertyChangeEvent(
            std::unique_ptr<const PropertyChangeCallback> callback) override;
    void registerOnPropertySetErrorEvent(
            std::unique_ptr<const PropertySetErrorCallback> callback) override;

    StatusCode subscribe(SubscribeOptions options) override;
    StatusCode unsubscribe(int32_t propId, int32_t areaId) override;
    StatusCode updateSampleRate(int32_t propId, int32_t areaId, float sampleRate) override;

    DumpResult dump(const std::vector<std::string>& options) override;

    void initPwm();
    void initGpios();

  private:
    StatusCode getValueInternal(const VehiclePropValue& request,
                                VehiclePropValue* response) const;
    StatusCode setValueInternal(const VehiclePropValue& request,
                                VehiclePropValue* updatedValue);

    void pollInputs();
    void sensorLoop();
    void displayStateLoop();
    std::string findDisplayDpmsPath();

    void writePwm(int percentage);
    void setBacklightEnable(bool on);
    int readGearGpio();

    void writeSysFs(const std::string& path, const std::string& val);
    int readSysFsInt(const std::string& path);
    void ensurePwmExported(const std::string& base);

    void emitPropChange(const VehiclePropValue& v);
    void emitInitialStatesLocked() REQUIRES(mCallbackMutex);

    void publishCurrentBrightness();
    void publishVendorScreenPower();
    void publishApPowerStateReq(int32_t reqState, int32_t param = 0);

    void applyScreenPower(bool on, bool restoreBrightness);
    void handleApPowerStateReport(const VehiclePropValue& request);

    std::atomic<int32_t> mCurrentGear;
    std::atomic<int32_t> mCurrentBrightness;
    std::atomic<int32_t> mLastNonZeroBrightness;
    std::atomic<bool> mScreenOn;

    std::atomic<int32_t> mIgnitionState;
    std::atomic<int32_t> mParkingBrakeOn;

    std::string mBacklightGpioChipName;
    std::string mGearGpioChipName;
    int mGearGpioOffset;
    int mBacklightEnableGpioOffset;

    int mBacklightEnableFd;
    int mGearFd;

    std::string mPwmChipBase;
    std::string mPathPwmDuty;
    std::string mPathPwmEnable;
    std::string mPathPwmPeriod;

    std::atomic<bool> mShuttingDown;
    std::thread mPollThread;

    std::atomic<bool> mSensorThreadRunning;
    std::thread mSensorThread;
    std::string mLightSensorPath;
    int mSensorRawMax;

    std::atomic<bool> mDisplayThreadRunning;
    std::thread mDisplayThread;
    std::string mDisplayDpmsPath;

    std::atomic<bool> mAutoBrightnessEnabled;
    std::atomic<int> mAutoTargetBrightness;

    // Track AAOS power properties explicitly.
    std::atomic<int32_t> mLastApPowerStateReq;
    std::atomic<int32_t> mLastApPowerStateReqParam;
    std::atomic<int32_t> mLastApPowerStateReport;
    std::atomic<int32_t> mLastApPowerStateReportParam;

    mutable std::mutex mCallbackMutex;
    std::unique_ptr<const PropertyChangeCallback> mOnPropChange GUARDED_BY(mCallbackMutex);
    std::unique_ptr<const PropertySetErrorCallback> mOnSetError GUARDED_BY(mCallbackMutex);
};

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android

#endif  // ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMANVEHICLEHARDWARE_H