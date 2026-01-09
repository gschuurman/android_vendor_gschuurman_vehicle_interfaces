/*
 * Copyright (C) 2021 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

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

    // IVehicleHardware Implementation
    std::vector<VehiclePropConfig> getAllPropertyConfigs() const override;
    StatusCode getValues(std::shared_ptr<const GetValuesCallback> callback,
                         const std::vector<GetValueRequest>& requests) const override;
    StatusCode setValues(std::shared_ptr<const SetValuesCallback> callback,
                         const std::vector<SetValueRequest>& requests) override;
    StatusCode checkHealth() override;
    
    // PropertyChangeCallback and PropertySetErrorCallback are defined in IVehicleHardware
    void registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) override;
    void registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback) override;
    
    StatusCode subscribe(SubscribeOptions options) override;
    StatusCode unsubscribe(int32_t propId, int32_t areaId) override;
    StatusCode updateSampleRate(int32_t propId, int32_t areaId, float sampleRate) override;
    
    // DumpResult is defined in android::hardware::automotive::vehicle namespace (visible here)
    DumpResult dump(const std::vector<std::string>& options) override;

    // Initialization
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

    // State Variables
    int32_t mCurrentGear;
    int32_t mCurrentBrightness;
    std::atomic<bool> mScreenOn;

    // GPIO Configuration
    std::string mGpioChipName;
    int mGearGpioOffset;
    int mBrightnessGpioOffset;
    int mBacklightEnableGpioOffset;

    // GPIO Handles
    int mBacklightEnableFd;

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

    std::unique_ptr<const PropertyChangeCallback> mOnPropChange;
    std::unique_ptr<const PropertySetErrorCallback> mOnSetError;
};

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android

#endif  // ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMANVEHICLEHARDWARE_H