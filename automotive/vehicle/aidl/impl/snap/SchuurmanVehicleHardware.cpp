#include "SchuurmanVehicleHardware.h"

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <chrono>
#include <fstream>
#include <thread>
#include <gpiod.h>

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

                using ::aidl::android::hardware::automotive::vehicle::VehicleGear;
                using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyAccess;
                using ::aidl::android::hardware::automotive::vehicle::VehiclePropertyChangeMode;

                static int64_t elapsedRealtimeNano()
                {
                    auto now = std::chrono::steady_clock::now();
                    return std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
                }

                SchuurmanVehicleHardware::SchuurmanVehicleHardware()
                    : mCurrentGear(static_cast<int32_t>(VehicleGear::GEAR_PARK)),
                      mCurrentBrightness(50),
                      mShuttingDown(false),
                      mGpioChip(nullptr),
                      mGpioLine(nullptr)
                {
                    // PWM Properties (eventueel ook hernoemen naar ro.vendor.schuurman... in je system.prop)
                    mPathPwmDuty = android::base::GetProperty("ro.vendor.vehicle.path.pwm.duty",
                                                              "/sys/class/pwm/pwmchip0/pwm0/duty_cycle");
                    mPathPwmEnable = android::base::GetProperty("ro.vendor.vehicle.path.pwm.enable",
                                                                "/sys/class/pwm/pwmchip0/pwm0/enable");
                    mPathPwmPeriod = android::base::GetProperty("ro.vendor.vehicle.path.pwm.period",
                                                                "/sys/class/pwm/pwmchip0/pwm0/period");

                    // GPIO Properties
                    mGpioChipPath = android::base::GetProperty("ro.vendor.vehicle.gpio.chip", "/dev/gpiochip0");
                    mGpioLineOffset = android::base::GetIntProperty("ro.vendor.vehicle.gpio.offset", 0);

                    LOG(INFO) << "SchuurmanVehicleHardware Configured:"
                              << "\n PWM Path: " << mPathPwmDuty
                              << "\n GPIO Chip: " << mGpioChipPath
                              << "\n GPIO Line Offset: " << mGpioLineOffset;

                    initPwm();
                    initGpio();
                    mPollThread = std::thread(&SchuurmanVehicleHardware::pollInputs, this);
                }

                SchuurmanVehicleHardware::~SchuurmanVehicleHardware()
                {
                    mShuttingDown = true;
                    if (mPollThread.joinable())
                    {
                        mPollThread.join();
                    }
                    
                    if (mGpioLine) {
                        gpiod_line_release(mGpioLine);
                        mGpioLine = nullptr;
                    }
                    if (mGpioChip) {
                        gpiod_chip_close(mGpioChip);
                        mGpioChip = nullptr;
                    }
                }

                std::vector<VehiclePropConfig> SchuurmanVehicleHardware::getAllPropertyConfigs() const
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

                StatusCode SchuurmanVehicleHardware::getValues(std::shared_ptr<const GetValuesCallback> callback,
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

                StatusCode SchuurmanVehicleHardware::getValueInternal(const VehiclePropValue &request, VehiclePropValue *response) const
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

                StatusCode SchuurmanVehicleHardware::setValues(std::shared_ptr<const SetValuesCallback> callback,
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

                StatusCode SchuurmanVehicleHardware::setValueInternal(const VehiclePropValue &request, VehiclePropValue *updatedValue)
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

                DumpResult SchuurmanVehicleHardware::dump(const std::vector<std::string> & /*options*/)
                {
                    return {};
                }

                StatusCode SchuurmanVehicleHardware::checkHealth()
                {
                    return StatusCode::OK;
                }

                void SchuurmanVehicleHardware::registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback)
                {
                    mOnPropChange = std::move(callback);
                }

                void SchuurmanVehicleHardware::registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback)
                {
                    mOnSetError = std::move(callback);
                }

                // Stubs
                StatusCode SchuurmanVehicleHardware::subscribe(SubscribeOptions /*options*/) { return StatusCode::OK; }
                StatusCode SchuurmanVehicleHardware::unsubscribe(int32_t /*propId*/, int32_t /*areaId*/) { return StatusCode::OK; }
                StatusCode SchuurmanVehicleHardware::updateSampleRate(int32_t /*propId*/, int32_t /*areaId*/, float /*sampleRate*/) { return StatusCode::OK; }

                // Hardware Logica
                void SchuurmanVehicleHardware::initPwm()
                {
                    writeSysFs(mPathPwmPeriod, "50000");
                    writeSysFs(mPathPwmEnable, "1");
                }
                
                void SchuurmanVehicleHardware::initGpio()
                {
                    mGpioChip = gpiod_chip_open(mGpioChipPath.c_str());
                    if (!mGpioChip) {
                        LOG(ERROR) << "Failed to open GPIO chip: " << mGpioChipPath;
                        return;
                    }

                    mGpioLine = gpiod_chip_get_line(mGpioChip, mGpioLineOffset);
                    if (!mGpioLine) {
                        LOG(ERROR) << "Failed to get GPIO line: " << mGpioLineOffset;
                        gpiod_chip_close(mGpioChip);
                        mGpioChip = nullptr;
                        return;
                    }

                    // Request als input met de nieuwe naam als consument
                    int ret = gpiod_line_request_input(mGpioLine, "SchuurmanVehicleHardware");
                    if (ret < 0) {
                        LOG(ERROR) << "Failed to request GPIO line as input";
                        gpiod_line_release(mGpioLine);
                        mGpioLine = nullptr;
                    }
                }

                void SchuurmanVehicleHardware::writePwm(int percentage)
                {
                    int duty = (percentage * 50000) / 100;
                    writeSysFs(mPathPwmDuty, std::to_string(duty));
                }

                void SchuurmanVehicleHardware::pollInputs()
                {
                    int lastGpioState = -1;
                    while (!mShuttingDown)
                    {
                        if (mGpioLine) {
                            int currentState = gpiod_line_get_value(mGpioLine);
                            
                            if (currentState >= 0 && currentState != lastGpioState)
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
                        } else {
                            // Retry mechanisme als init mislukte
                            static int retry = 0;
                            if (++retry > 50) { 
                                initGpio(); 
                                retry = 0; 
                            }
                        }
                        std::this_thread::sleep_for(std::chrono::milliseconds(100));
                    }
                }

                void SchuurmanVehicleHardware::writeSysFs(const std::string &path, const std::string &val)
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