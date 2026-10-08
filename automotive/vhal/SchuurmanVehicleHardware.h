#ifndef ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMANVEHICLEHARDWARE_H
#define ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMANVEHICLEHARDWARE_H

#include <IVehicleHardware.h>
#include <aidl/android/hardware/automotive/vehicle/BnVehicle.h>
#include <android-base/thread_annotations.h>

#include <atomic>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "McuLink.h"

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

// Vehicle HAL for the car radio. The peripheral board MCU (RP2350B) owns the car-side
// inputs, the backlight, the amplifier and the VIM3's power; this class bridges it to
// Android over the USB HID link in McuLink (protocol: mcu/protocol/mcu_protocol.h).
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

  private:
    StatusCode getValueInternal(const VehiclePropValue& request,
                                VehiclePropValue* response) const;
    StatusCode setValueInternal(const VehiclePropValue& request,
                                VehiclePropValue* updatedValue);

    // MCU link callbacks (McuLink thread)
    void onMcuProps(const std::vector<mcu_prop_t>& props, bool snapshot);
    void onMcuInfo(const mcu_info_msg_t& info);
    void onMcuConnect(bool connected);
    void pushSettingsToMcu();

    void housekeepingLoop();
    void updateParkingBrake(bool force);
    void displayStateLoop();
    std::string findDisplayDpmsPath();

    void touchWakeLoop();
    static int findInputDeviceByVidPid(uint16_t vendor, uint16_t product);
    static int findInputDeviceWithKey(uint16_t keyCode);
    void injectMediaKey(uint16_t keyCode);

    void sendBrightness(int percentage);

    void emitPropChange(const VehiclePropValue& v);
    void emitInt(int32_t propId, int32_t value);
    void emitInts(int32_t propId, const std::vector<int32_t>& values);
    void emitInitialStatesLocked() REQUIRES(mCallbackMutex);

    void publishCurrentBrightness();
    void publishVendorScreenPower();
    void publishApPowerStateReq(int32_t reqState, int32_t param = 0);

    void applyScreenPower(bool on, bool restoreBrightness);
    void handleApPowerStateReport(const VehiclePropValue& request);
    StatusCode setDisplayUnits(const VehiclePropValue& request, const std::vector<int32_t>& supported,
                               const char* persistProp, std::atomic<int32_t>* current,
                               VehiclePropValue* updatedValue);
    StatusCode setMcuSetting(const VehiclePropValue& request, int32_t minValue, int32_t maxValue,
                             const char* persistProp);

    McuLink mMcu;

    std::atomic<int32_t> mCurrentGear;
    std::atomic<int32_t> mCurrentBrightness;
    std::atomic<int32_t> mLastNonZeroBrightness;
    std::atomic<bool> mScreenOn;

    std::atomic<int32_t> mIgnitionState;
    std::atomic<int32_t> mParkingBrakeOn;
    std::atomic<int32_t> mNightMode;
    std::atomic<float> mSpeed;
    std::atomic<int32_t> mLux;

    // Handbrake: the MG F wire may not reach the radio (ISO A2 left open reads "released").
    // persist.vendor.vehicle.handbrake = auto (default) | wired | gnss. In auto mode the
    // wire counts as connected once it has been seen engaged; until then "parked" comes
    // from GNSS speed.
    std::atomic<bool> mHandbrakeRaw;
    std::atomic<bool> mHandbrakeSeen;
    std::atomic<bool> mGnssStationary;
    std::atomic<int64_t> mSlowSinceNs{0};

    // Display units (distance, temperature, fuel volume), chosen in Car Settings or the setup wizard and
    // kept across reboots in persist.vendor.vehicle.*_units.
    std::atomic<int32_t> mDistanceUnits;
    std::atomic<int32_t> mTemperatureUnits;
    std::atomic<int32_t> mFuelVolumeUnits;

    // Last values of the MCU's vendor properties (MCU_PROP_* in mcu_protocol.h).
    mutable std::mutex mMcuMutex;
    std::map<int32_t, std::pair<int32_t, int32_t>> mMcuValues GUARDED_BY(mMcuMutex);
    std::string mMcuVersion GUARDED_BY(mMcuMutex);
    bool mMcuEnPullup GUARDED_BY(mMcuMutex) = false;

    std::atomic<bool> mShuttingDown;

    std::atomic<bool> mAutoBrightnessEnabled;
    std::atomic<int> mAutoTargetBrightness;

    std::thread mHousekeepingThread;

    std::atomic<bool> mDisplayThreadRunning;
    std::thread mDisplayThread;
    std::string mDisplayDpmsPath;

    std::atomic<bool> mTouchWakeThreadRunning;
    std::thread mTouchWakeThread;
    // Set when the MCU asks Android to sleep (ACC off), so a stray touch while parked
    // does not wake the screen.
    std::atomic<bool> mTapToWakeSuppressed;
    std::atomic<bool> mPausedForPower;

    // Track AAOS power properties explicitly.
    std::atomic<int32_t> mLastApPowerStateReq;
    std::atomic<int32_t> mLastApPowerStateReqParam;
    std::atomic<int32_t> mLastApPowerStateReport;
    std::atomic<int32_t> mLastApPowerStateReportParam;
    std::atomic<bool> mReportPending;      // report not yet delivered to the MCU
    std::atomic<int64_t> mFallbackOnAtNs;  // publish ON ourselves if the MCU stays away

    std::string mCurrentPolicyGroup;
    std::string mCurrentPolicyReq;

    mutable std::mutex mCallbackMutex;
    std::unique_ptr<const PropertyChangeCallback> mOnPropChange GUARDED_BY(mCallbackMutex);
    std::unique_ptr<const PropertySetErrorCallback> mOnSetError GUARDED_BY(mCallbackMutex);
};

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android

#endif  // ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMANVEHICLEHARDWARE_H
