#include "SchuurmanVehicleHardware.h"

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <chrono>
#include <fstream>
#include <thread>
#include <stdio.h>  // Voor popen
#include <stdlib.h>

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
                      mShuttingDown(false)
                {

                    // PWM Config (Sysfs)
                    mPathPwmDuty = android::base::GetProperty("ro.vendor.vehicle.path.pwm.duty", "/sys/class/pwm/pwmchip0/pwm0/duty_cycle");
                    mPathPwmEnable = android::base::GetProperty("ro.vendor.vehicle.path.pwm.enable", "/sys/class/pwm/pwmchip0/pwm0/enable");
                    mPathPwmPeriod = android::base::GetProperty("ro.vendor.vehicle.path.pwm.period", "/sys/class/pwm/pwmchip0/pwm0/period");

                    // GPIO Config voor 'gpioget'
                    // Default: gpiochip0 en lijn 0.
                    mGpioChipName = android::base::GetProperty("ro.vendor.vehicle.gpio.chip", "gpiochip0");
                    mGpioLineOffset = android::base::GetIntProperty("ro.vendor.vehicle.gpio.offset", 0);

                    LOG(INFO) << "SchuurmanVehicleHardware Configured:"
                              << "\n PWM Path: " << mPathPwmDuty
                              << "\n GPIO Command Target: " << mGpioChipName << " line " << mGpioLineOffset;

                    initPwm();
                    // Geen initGpio meer nodig, gpioget regelt dat per call
                    mPollThread = std::thread(&SchuurmanVehicleHardware::pollInputs, this);
                }

                SchuurmanVehicleHardware::~SchuurmanVehicleHardware()
                {
                    mShuttingDown = true;
                    if (mPollThread.joinable())
                        mPollThread.join();
                }

                std::vector<VehiclePropConfig> SchuurmanVehicleHardware::getAllPropertyConfigs() const
                {
                    std::vector<VehiclePropConfig> configs;

                    VehiclePropConfig gearConfig;
                    gearConfig.prop = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
                    gearConfig.access = VehiclePropertyAccess::READ;
                    gearConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
                    configs.push_back(gearConfig);

                    VehiclePropConfig brightConfig;
                    brightConfig.prop = static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS);
                    brightConfig.access = VehiclePropertyAccess::READ_WRITE;
                    brightConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
                    brightConfig.areaConfigs = {{.minInt32Value = 0, .maxInt32Value = 100}};
                    configs.push_back(brightConfig);

                    return configs;
                }

                StatusCode SchuurmanVehicleHardware::getValues(std::shared_ptr<const GetValuesCallback> callback, const std::vector<GetValueRequest> &requests) const
                {
                    std::vector<GetValueResult> results;
                    for (const auto &req : requests)
                    {
                        GetValueResult result;
                        result.requestId = req.requestId;
                        VehiclePropValue responseValue = req.prop;
                        result.status = getValueInternal(req.prop, &responseValue);
                        if (result.status == StatusCode::OK)
                            result.prop = responseValue;
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

                StatusCode SchuurmanVehicleHardware::setValues(std::shared_ptr<const SetValuesCallback> callback, const std::vector<SetValueRequest> &requests)
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

                DumpResult SchuurmanVehicleHardware::dump(const std::vector<std::string> &) { return {}; }
                StatusCode SchuurmanVehicleHardware::checkHealth() { return StatusCode::OK; }
                void SchuurmanVehicleHardware::registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) { mOnPropChange = std::move(callback); }
                void SchuurmanVehicleHardware::registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback) { mOnSetError = std::move(callback); }
                StatusCode SchuurmanVehicleHardware::subscribe(SubscribeOptions) { return StatusCode::OK; }
                StatusCode SchuurmanVehicleHardware::unsubscribe(int32_t, int32_t) { return StatusCode::OK; }
                StatusCode SchuurmanVehicleHardware::updateSampleRate(int32_t, int32_t, float) { return StatusCode::OK; }

                void SchuurmanVehicleHardware::initPwm()
                {
                    writeSysFs(mPathPwmPeriod, "50000");
                    writeSysFs(mPathPwmEnable, "1");
                }

                void SchuurmanVehicleHardware::writePwm(int percentage)
                {
                    int duty = (percentage * 50000) / 100;
                    writeSysFs(mPathPwmDuty, std::to_string(duty));
                }

                // Helper: Voer shell commando uit en lees output
                int SchuurmanVehicleHardware::runCommand(const std::string &cmd)
                {
                    FILE *pipe = popen(cmd.c_str(), "r");
                    if (!pipe)
                    {
                        return -1;
                    }
                    char buffer[128];
                    std::string result = "";
                    if (fgets(buffer, 128, pipe) != NULL)
                    {
                        result = buffer;
                    }
                    pclose(pipe);

                    if (result.empty())
                    {
                        return -1;
                    }

                    // Veiligere conversie zonder exceptions (vervangt try/catch stoi)
                    char *end;
                    long val = strtol(result.c_str(), &end, 10);

                    // Als end == result.c_str() is er niets geconverteerd
                    if (end == result.c_str())
                    {
                        return -1;
                    }

                    return static_cast<int>(val);
                }

                void SchuurmanVehicleHardware::pollInputs()
                {
                    int lastGpioState = -1;
                    // Commando samenstellen: "gpioget gpiochip0 12"
                    // Let op: controleer of 'gpioget' in je $PATH zit op het device, anders '/system/bin/gpioget' gebruiken
                    std::string cmd = "/system/bin/gpioget " + mGpioChipName + " " + std::to_string(mGpioLineOffset);

                    // Voeg eventueel flag toe als hij active-low moet zijn:
                    // cmd += " --active-low";

                    while (!mShuttingDown)
                    {
                        int currentState = runCommand(cmd);

                        if (currentState >= 0 && currentState != lastGpioState)
                        {
                            // Pas dit aan afhankelijk van je hardware (1 = achteruit of 0 = achteruit)
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
                            LOG(INFO) << "Gear changed to: " << (currentState == 1 ? "REVERSE" : "DRIVE") << " (via " << cmd << ")";
                        }

                        // Polling interval iets ruimer nemen omdat popen zwaarder is dan file read
                        std::this_thread::sleep_for(std::chrono::milliseconds(200));
                    }
                }

                void SchuurmanVehicleHardware::writeSysFs(const std::string &path, const std::string &val)
                {
                    std::ofstream file(path);
                    if (file.is_open())
                        file << val;
                    else
                        LOG(WARNING) << "Failed to write to path: " << path;
                }

            } // vehicle
        } // automotive
    } // hardware
} // android