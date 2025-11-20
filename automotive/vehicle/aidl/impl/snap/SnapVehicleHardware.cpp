#include "SnapVehicleHardware.h"

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <chrono>
#include <fstream>
#include <thread> // Toegevoegd voor std::this_thread::sleep_for

#include <aidl/android/hardware/automotive/vehicle/VehicleGear.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyAccess.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyChangeMode.h>

namespace android
{
    namespace hardware
    {
        namespace automotive
        {
            namespace vehicle
            {

                // --- NAMESPACE ALIASSEN ---
                using ::aidl::android::hardware::automotive::vehicle::VehicleGear;
                using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyAccess;
                using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyChangeMode;

                static int64_t elapsedRealtimeNano()
                {
                    auto now = std::chrono::steady_clock::now();
                    return std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
                }

                SnapVehicleHardware::SnapVehicleHardware()
                    : mCurrentGear(static_cast<int32_t>(VehicleGear::GEAR_PARK)),
                      mCurrentBrightness(50),
                      mShuttingDown(false)
                {

                    mPathPwmDuty = android::base::GetProperty("ro.vendor.vehicle.path.pwm.duty",
                                                              "/sys/class/pwm/pwmchip0/pwm0/duty_cycle");
                    mPathPwmEnable = android::base::GetProperty("ro.vendor.vehicle.path.pwm.enable",
                                                                "/sys/class/pwm/pwmchip0/pwm0/enable");
                    mPathPwmPeriod = android::base::GetProperty("ro.vendor.vehicle.path.pwm.period",
                                                                "/sys/class/pwm/pwmchip0/pwm0/period");
                    mPathGpioReverse = android::base::GetProperty("ro.vendor.vehicle.path.gpio.reverse",
                                                                  "/sys/class/gpio/gpio496/value");

                    LOG(INFO) << "SnapVehicleHardware Configured:"
                              << "\n PWM Path: " << mPathPwmDuty
                              << "\n GPIO Path: " << mPathGpioReverse;

                    initPwm();
                    mPollThread = std::thread(&SnapVehicleHardware::pollInputs, this);
                }

                SnapVehicleHardware::~SnapVehicleHardware()
                {
                    mShuttingDown = true;
                    if (mPollThread.joinable())
                    {
                        mPollThread.join();
                    }
                }

                std::vector<VehiclePropConfig> SnapVehicleHardware::getAllPropertyConfigs() const
                {
                    std::vector<VehiclePropConfig> configs;

                    // GEAR_SELECTION
                    VehiclePropConfig gearConfig;
                    gearConfig.prop = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
                    gearConfig.access = VehiclePropertyAccess::READ;
                    gearConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
                    configs.push_back(gearConfig);

                    // DISPLAY_BRIGHTNESS
                    VehiclePropConfig brightConfig;
                    brightConfig.prop = static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS);
                    brightConfig.access = VehiclePropertyAccess::READ_WRITE;
                    brightConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
                    brightConfig.areaConfigs = {{.minInt32Value = 0, .maxInt32Value = 100}};
                    configs.push_back(brightConfig);

                    return configs;
                }

                StatusCode SnapVehicleHardware::getValues(std::shared_ptr<const GetValuesCallback> callback,
                                                          const std::vector<GetValueRequest> &requests) const
                {
                    std::vector<GetValueResult> results;
                    for (const auto &req : requests)
                    {
                        GetValueResult result;
                        result.requestId = req.requestId;
                        VehiclePropValue responseValue = req.prop;
                        result.status = getValueInternal(req.prop, &responseValue);
                        if (result.status == StatusCode::OK)
                        {
                            result.prop = responseValue;
                        }
                        results.push_back(result);
                    }
                    (*callback)(std::move(results));
                    return StatusCode::OK;
                }

                StatusCode SnapVehicleHardware::getValueInternal(const VehiclePropValue &request, VehiclePropValue *response) const
                {
                    int32_t propId = request.prop;
                    response->timestamp = elapsedRealtimeNano();

                    if (propId == static_cast<int32_t>(VehicleProperty::GEAR_SELECTION))
                    {
                        response->value.int32Values = {mCurrentGear};
                        return StatusCode::OK;
                    }
                    else if (propId == static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS))
                    {
                        response->value.int32Values = {mCurrentBrightness};
                        return StatusCode::OK;
                    }
                    return StatusCode::INVALID_ARG;
                }

                StatusCode SnapVehicleHardware::setValues(std::shared_ptr<const SetValuesCallback> callback,
                                                          const std::vector<SetValueRequest> &requests)
                {
                    std::vector<SetValueResult> results;
                    for (const auto &req : requests)
                    {
                        SetValueResult result;
                        result.requestId = req.requestId;
                        VehiclePropValue updatedValue = req.value;
                        result.status = setValueInternal(req.value, &updatedValue);
                        results.push_back(result);
                    }
                    (*callback)(std::move(results));
                    return StatusCode::OK;
                }

                StatusCode SnapVehicleHardware::setValueInternal(const VehiclePropValue &request, VehiclePropValue *updatedValue)
                {
                    int32_t propId = request.prop;

                    if (propId == static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS))
                    {
                        if (request.value.int32Values.empty())
                            return StatusCode::INVALID_ARG;
                        int brightness = request.value.int32Values[0];
                        if (brightness < 0 || brightness > 100)
                            return StatusCode::INVALID_ARG;

                        writePwm(brightness);
                        mCurrentBrightness = brightness;

                        if (updatedValue)
                        {
                            *updatedValue = request;
                            updatedValue->timestamp = elapsedRealtimeNano();
                        }
                        return StatusCode::OK;
                    }
                    return StatusCode::ACCESS_DENIED;
                }

                DumpResult SnapVehicleHardware::dump(const std::vector<std::string> & /*options*/)
                {
                    return {};
                }

                StatusCode SnapVehicleHardware::checkHealth()
                {
                    return StatusCode::OK;
                }

                void SnapVehicleHardware::registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback)
                {
                    mOnPropChange = std::move(callback);
                }

                void SnapVehicleHardware::registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback)
                {
                    mOnSetError = std::move(callback);
                }

                // Stubs
                StatusCode SnapVehicleHardware::subscribe(SubscribeOptions /*options*/) { return StatusCode::OK; }
                StatusCode SnapVehicleHardware::unsubscribe(int32_t /*propId*/, int32_t /*areaId*/) { return StatusCode::OK; }
                StatusCode SnapVehicleHardware::updateSampleRate(int32_t /*propId*/, int32_t /*areaId*/, float /*sampleRate*/) { return StatusCode::OK; }

                // Hardware Logica
                void SnapVehicleHardware::initPwm()
                {
                    writeSysFs(mPathPwmPeriod, "50000");
                    writeSysFs(mPathPwmEnable, "1");
                }

                void SnapVehicleHardware::writePwm(int percentage)
                {
                    int duty = (percentage * 50000) / 100;
                    writeSysFs(mPathPwmDuty, std::to_string(duty));
                }

                void SnapVehicleHardware::pollInputs()
                {
                    int lastGpioState = -1;
                    while (!mShuttingDown)
                    {
                        std::ifstream gpioFile(mPathGpioReverse);
                        int currentState;
                        if (gpioFile >> currentState)
                        {
                            if (currentState != lastGpioState)
                            {
                                mCurrentGear = (currentState == 1) ? static_cast<int32_t>(VehicleGear::GEAR_REVERSE) : static_cast<int32_t>(VehicleGear::GEAR_DRIVE);

                                if (mOnPropChange)
                                {
                                    std::vector<VehiclePropValue> events;
                                    VehiclePropValue v;
                                    v.prop = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
                                    v.timestamp = elapsedRealtimeNano();
                                    v.value.int32Values = {mCurrentGear};
                                    events.push_back(v);
                                    (*mOnPropChange)(events);
                                }
                                lastGpioState = currentState;
                            }
                        }
                        std::this_thread::sleep_for(std::chrono::milliseconds(100));
                    }
                }

                void SnapVehicleHardware::writeSysFs(const std::string &path, const std::string &val)
                {
                    std::ofstream file(path);
                    if (file.is_open())
                    {
                        file << val;
                    }
                    else
                    {
                        LOG(WARNING) << "Failed to write to path: " << path;
                    }
                }

            }
        }
    }
}