#ifndef ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMAN_IMPL_H
#define ANDROID_HARDWARE_AUTOMOTIVE_VEHICLE_SCHUURMAN_IMPL_H

#include <vector>
#include <thread>
#include <string>
#include <atomic>
#include <memory>

#include <IVehicleHardware.h>
#include <aidl/android/hardware/automotive/vehicle/IVehicle.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleProperty.h>

namespace android
{
    namespace hardware
    {
        namespace automotive
        {
            namespace vehicle
            {

                using ::aidl::android::hardware::automotive::vehicle::GetValueRequest;
                using ::aidl::android::hardware::automotive::vehicle::GetValueResult;
                using ::aidl::android::hardware::automotive::vehicle::SetValueRequest;
                using ::aidl::android::hardware::automotive::vehicle::SetValueResult;
                using ::aidl::android::hardware::automotive::vehicle::StatusCode;
                using ::aidl::android::hardware::automotive::vehicle::SubscribeOptions;
                using ::aidl::android::hardware::automotive::vehicle::VehiclePropConfig;
                using ::aidl::android::hardware::automotive::vehicle::VehicleProperty;
                using ::aidl::android::hardware::automotive::vehicle::VehiclePropValue;
                using ::android::hardware::automotive::vehicle::DumpResult;
                using ::android::hardware::automotive::vehicle::IVehicleHardware;

                class SchuurmanVehicleHardware : public IVehicleHardware
                {
                public:
                    SchuurmanVehicleHardware();
                    ~SchuurmanVehicleHardware();

                    std::vector<VehiclePropConfig> getAllPropertyConfigs() const override;
                    StatusCode getValues(std::shared_ptr<const GetValuesCallback> callback, const std::vector<GetValueRequest> &requests) const override;
                    StatusCode setValues(std::shared_ptr<const SetValuesCallback> callback, const std::vector<SetValueRequest> &requests) override;
                    DumpResult dump(const std::vector<std::string> &options) override;
                    StatusCode checkHealth() override;
                    void registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) override;
                    void registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback) override;
                    StatusCode subscribe(SubscribeOptions options) override;
                    StatusCode unsubscribe(int32_t propId, int32_t areaId) override;
                    StatusCode updateSampleRate(int32_t propId, int32_t areaId, float sampleRate) override;

                private:
                    int32_t mCurrentGear;
                    int32_t mCurrentBrightness;

                    // De opgeslagen periode (uitgelezen uit kernel)
                    int mPwmPeriodNs;

                    // Threads & State
                    std::thread mPollThread;
                    std::atomic<bool> mShuttingDown;

                    // Sensor Threading
                    std::thread mSensorThread;
                    std::atomic<bool> mSensorThreadRunning;
                    std::string mLightSensorPath;
                    int mSensorRawMax;
                    
                    // Auto Brightness Logic
                    std::atomic<bool> mAutoBrightnessEnabled;
                    std::atomic<int> mAutoTargetBrightness;

                    // PWM Paden
                    std::string mPathPwmDuty;
                    std::string mPathPwmEnable;
                    std::string mPathPwmPeriod;

                    // GPIO
                    std::string mGpioChipName;
                    int mGpioLineOffset;

                    std::unique_ptr<const PropertyChangeCallback> mOnPropChange;
                    std::unique_ptr<const PropertySetErrorCallback> mOnSetError;

                    void initPwm();
                    void writePwm(int percentage);
                    int readGpio();
                    void pollInputs();
                    
                    // Nieuwe functie toegevoegd voor sensor logic
                    void sensorLoop();

                    // Helpers
                    void ensurePwmExported(const std::string &chipBase);
                    void writeSysFs(const std::string &path, const std::string &val);
                    int readSysFsInt(const std::string &path);

                    StatusCode getValueInternal(const VehiclePropValue &request, VehiclePropValue *response) const;
                    StatusCode setValueInternal(const VehiclePropValue &request, VehiclePropValue *updatedValue);
                };

            } // vehicle
        } // automotive
    } // hardware
} // android

#endif