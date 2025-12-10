#include "SchuurmanVehicleHardware.h"

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <chrono>
#include <fstream>
#include <thread>
#include <vector>
#include <filesystem>
#include <regex>
#include <iostream>
#include <atomic>
#include <cmath>

#include <linux/gpio.h>

// Linux Kernel Headers
#include <fcntl.h>
#include <unistd.h>
#include <string.h>
#include <errno.h>
#include <sys/ioctl.h>

#include <aidl/android/hardware/automotive/vehicle/VehicleGear.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyAccess.h>
#include <aidl/android/hardware/automotive/vehicle/VehiclePropertyChangeMode.h>

static constexpr int32_t PWM_PERIOD_NS = 30518;

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

                // Vendor property id: adjust if you use a centralized property map
                static const int32_t VENDOR_AUTO_BRIGHTNESS = 0x12000001;

                static int64_t elapsedRealtimeNano()
                {
                    auto now = std::chrono::steady_clock::now();
                    return std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
                }

                // Helper om de juiste chip te vinden op basis van adres 19000
                std::string findPwmChipPath()
                {
                    std::string baseDir = "/sys/class/pwm/";
                    for (int i = 0; i < 10; i++)
                    {
                        std::string chipName = "pwmchip" + std::to_string(i);
                        std::string fullPath = baseDir + chipName;
                        std::string linkPath = fullPath + "/device/of_node";

                        char buf[1024];
                        ssize_t len = readlink(linkPath.c_str(), buf, sizeof(buf) - 1);
                        if (len != -1)
                        {
                            // FIX: Hier stond een vreemd teken, moet null terminator zijn
                            buf[len] = '\0';
                            if (std::string(buf).find("19000") != std::string::npos)
                            {
                                LOG(INFO) << "Found PWM Chip: " << chipName << " (Address 19000)";
                                return fullPath;
                            }
                        }
                    }
                    LOG(ERROR) << "PWM Chip 19000 not found! Fallback to pwmchip0";
                    return baseDir + "pwmchip0";
                }

                SchuurmanVehicleHardware::SchuurmanVehicleHardware()
                    : mCurrentGear(static_cast<int32_t>(VehicleGear::GEAR_PARK)),
                      mCurrentBrightness(50),
                      mShuttingDown(false),
                      mSensorThreadRunning(false),
                      mLightSensorPath("/data/vendor/sensors/bh1750_lux"),
                      mSensorRawMax(100000),
                      mAutoBrightnessEnabled(false)
                {

                    LOG(INFO) << ">>> INIT START <<<";

                    // 1. Paden bepalen
                    std::string chipBase = findPwmChipPath();
                    mPathPwmDuty = chipBase + "/pwm1/duty_cycle";
                    mPathPwmEnable = chipBase + "/pwm1/enable";
                    mPathPwmPeriod = chipBase + "/pwm1/period";

                    // 2. Hardware één keer goed instellen
                    initPwm();

                    // 3. GPIO config
                    mGpioChipName = "/dev/" + android::base::GetProperty("ro.vendor.vehicle.gpio.chip", "gpiochip0");
                    mGpioLineOffset = android::base::GetIntProperty("ro.vendor.vehicle.gpio.offset", 16);

                    // Start sensor thread (reads from daemon-provided file)
                    mSensorThreadRunning.store(true);
                    mSensorThread = std::thread(&SchuurmanVehicleHardware::sensorLoop, this);

                    // 4. Thread starten
                    mPollThread = std::thread(&SchuurmanVehicleHardware::pollInputs, this);
                }

                SchuurmanVehicleHardware::~SchuurmanVehicleHardware()
                {
                    mShuttingDown = true;
                    if (mPollThread.joinable())
                        mPollThread.join();

                    mSensorThreadRunning.store(false);
                    if (mSensorThread.joinable())
                        mSensorThread.join();
                }

                // --- SETUP FUNCTIE (Draait 1x bij boot) ---
                void SchuurmanVehicleHardware::initPwm()
                {
                    LOG(INFO) << ">>> Initializing PWM Hardware <<<";

                    // 1. Zorg dat de export er is én dat we permissies hebben
                    std::string chipBase = findPwmChipPath();
                    ensurePwmExported(chipBase);

                    // 2. Lees huidige kernel settings
                    writeSysFs(mPathPwmPeriod, std::to_string(PWM_PERIOD_NS));

                    // 3. Reset state
                    // Eerst disablen om glitches te voorkomen
                    writeSysFs(mPathPwmEnable, "0");

                    long long bootDuty = PWM_PERIOD_NS / 2;

                    // Duty cycle op 0 zetten (veilig)
                    writeSysFs(mPathPwmDuty, std::to_string(bootDuty));

                    // 4. Enable
                    // Dit zou nu moeten werken omdat de file schrijfbaar is (fix 1) en de period > 0 is (fix 2)
                    writeSysFs(mPathPwmEnable, "1");

                    int enabled = readSysFsInt(mPathPwmEnable);
                    if (enabled != 1) {
                        LOG(ERROR) << "PWM Failed to enable";
                    }
                    else {
                        LOG(INFO) << "PWM Initialized and Enabled.";
                    }
                }

                // --- WRITE FUNCTIE (Draait bij elke slider move) ---
                void SchuurmanVehicleHardware::writePwm(int percentage)
                {
                    // Sanitize
                    if (percentage < 0)
                        percentage = 0;
                    if (percentage > 100)
                        percentage = 100;

                    // Inverted UI logic if needed
                    int inverted = 100 - percentage;

                    // ALWAYS read the current kernel period before computing duty
                    int kernelPeriod = readSysFsInt(mPathPwmPeriod);
                    if (kernelPeriod != PWM_PERIOD_NS)
                    {
                        LOG(WARNING) << "writePwm: unexpected kernel period, skipping duty update to avoid flicker";
                        return;
                    }

                    long long dutyCalc = ((long long)inverted * (long long)PWM_PERIOD_NS) / 100;
                    if (dutyCalc < 0)
                        dutyCalc = 0;
                    if (dutyCalc > PWM_PERIOD_NS)
                        dutyCalc = PWM_PERIOD_NS;

                    // debounce: only write if duty actually changed
                    static std::atomic<long long> s_lastDuty(-1);
                    long long last = s_lastDuty.load(std::memory_order_relaxed);
                    if (last == dutyCalc)
                    {
                        return;
                    }
                    s_lastDuty.store(dutyCalc, std::memory_order_relaxed);

                    std::string dutyStr = std::to_string(static_cast<long long>(dutyCalc));

                    // IMPORTANT: Do NOT toggle enable here. Writing duty while enabled avoids visible flicker.
                    // Simply write the new duty value.
                    writeSysFs(mPathPwmDuty, dutyStr);
                }

                void SchuurmanVehicleHardware::writeSysFs(const std::string &path, const std::string &val)
                {
                    int fd = open(path.c_str(), O_WRONLY | O_TRUNC);
                    if (fd < 0)
                    {
                        LOG(ERROR) << "Failed to open " << path << ": " << strerror(errno);
                        return;
                    }
                    ssize_t wrote = write(fd, val.c_str(), val.size());
                    if (wrote < 0 || static_cast<size_t>(wrote) != val.size())
                    {
                        LOG(ERROR) << "Failed to write '" << val << "' to " << path << ": " << strerror(errno);
                    }
                    // Ensure it is flushed to kernel
                    fsync(fd);
                    close(fd);
                }

                static std::string readSysFsString(const std::string &path, int retries = 3, int delayMs = 50)
                {
                    for (int i = 0; i < retries; ++i)
                    {
                        std::ifstream file(path);
                        if (file)
                        {
                            std::string s;
                            if (std::getline(file, s))
                            {
                                auto start = s.find_first_not_of(" \t\n\r");
                                auto end = s.find_last_not_of(" \t\n\r");
                                if (start == std::string::npos)
                                    return std::string();
                                return s.substr(start, end - start + 1);
                            }
                        }
                        std::this_thread::sleep_for(std::chrono::milliseconds(delayMs));
                    }
                    return std::string();
                }

                int SchuurmanVehicleHardware::readSysFsInt(const std::string &path)
                {
                    std::string s = readSysFsString(path, 5, 40);
                    if (s.empty())
                        return -1;

                    const char *start = s.c_str();
                    char *endPtr = nullptr;

                    errno = 0;
                    long val = strtoll(start, &endPtr, 10);

                    // Check for conversion errors
                    if (endPtr == start || errno != 0)
                    {
                        return -1;
                    }

                    return static_cast<int>(val);
                }

                bool fileExists(const std::string &p)
                {
                    return std::filesystem::exists(p);
                }

                void SchuurmanVehicleHardware::ensurePwmExported(const std::string &chipBase)
                {
                    // We gaan controleren op de 'enable' file, want daar moeten we straks in schrijven.
                    std::string pwmEnablePath = chipBase + "/pwm1/enable";
                    std::string exportPath = chipBase + "/export";

                    // 1. Check of hij al bestaat EN schrijfbaar is
                    if (access(pwmEnablePath.c_str(), W_OK) == 0)
                    {
                        return; // Alles is al klaar
                    }

                    // 2. Als de map /pwm1 nog helemaal niet bestaat, moeten we exporteren
                    std::string pwmDir = chipBase + "/pwm1";
                    if (!std::filesystem::exists(pwmDir))
                    {
                        LOG(INFO) << "Exporting PWM1 on " << chipBase;
                        writeSysFs(exportPath, "1");
                    }

                    // 3. Wachtlus: Wacht tot het bestand bestaat EN schrijfbaar is.
                    // Dit lost het probleem op dat je te snel probeert te schrijven na export.
                    for (int i = 0; i < 20; ++i) // Max 1 seconde wachten (20 * 50ms)
                    {
                        if (access(pwmEnablePath.c_str(), W_OK) == 0)
                        {
                            LOG(INFO) << "PWM1 sysfs node is writable.";
                            return;
                        }
                        std::this_thread::sleep_for(std::chrono::milliseconds(50));
                    }

                    LOG(ERROR) << "PWM1 export time-out! File not writable or not created: " << pwmEnablePath;
                }

                static int readIntFileNoExcept(const std::string &path)
                {
                    std::ifstream f(path);
                    if (!f)
                        return -1;
                    long v = -1;
                    if (!(f >> v))
                        return -1;
                    return static_cast<int>(v);
                }

                void SchuurmanVehicleHardware::sensorLoop()
                {
                    double ema = -1.0;
                    const double alpha = 0.25; // smoothing
                    const int pollMs = 250;    // sensor poll interval

                    while (mSensorThreadRunning.load())
                    {
                        int raw = readIntFileNoExcept(mLightSensorPath);
                        if (raw >= 0)
                        {
                            if (ema < 0)
                                ema = (double)raw;
                            else
                                ema = alpha * (double)raw + (1.0 - alpha) * ema;

                            double maxLux = (double)mSensorRawMax;
                            if (maxLux < 1.0)
                                maxLux = 1.0;
                            double percent = (log(1.0 + ema) / log(1.0 + maxLux)) * 100.0;
                            if (percent < 0.0)
                                percent = 0.0;
                            if (percent > 100.0)
                                percent = 100.0;

                            int intPercent = static_cast<int>(percent + 0.5);

                            if (mAutoBrightnessEnabled.load())
                            {
                                int last = mAutoTargetBrightness.load();
                                if (last < 0 || abs(intPercent - last) >= 2)
                                {
                                    mAutoTargetBrightness.store(intPercent);

                                    // apply to HW
                                    writePwm(intPercent);

                                    // update state & notify
                                    mCurrentBrightness = intPercent;
                                    if (mOnPropChange)
                                    {
                                        std::vector<VehiclePropValue> events;
                                        VehiclePropValue v;
                                        v.prop = static_cast<int32_t>(VehicleProperty::DISPLAY_BRIGHTNESS);
                                        v.timestamp = elapsedRealtimeNano();
                                        v.value.int32Values = {mCurrentBrightness};
                                        events.push_back(v);
                                        (*mOnPropChange)(events);
                                    }
                                }
                            }
                        }
                        std::this_thread::sleep_for(std::chrono::milliseconds(pollMs));
                    }
                }

                // --- STANDAARD VHAL BOILERPLATE (Aangepast voor auto-brightness property) ---

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

                    VehiclePropConfig autoConfig;
                    autoConfig.prop = VENDOR_AUTO_BRIGHTNESS;
                    autoConfig.access = VehiclePropertyAccess::READ_WRITE;
                    autoConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
                    autoConfig.areaConfigs = {{.minInt32Value = 0, .maxInt32Value = 1}};
                    configs.push_back(autoConfig);

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
                    else if (propId == VENDOR_AUTO_BRIGHTNESS)
                    {
                        response->value.int32Values = {mAutoBrightnessEnabled.load() ? 1 : 0};
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
                        if (!request.value.int32Values.empty())
                        {
                            int brightness = request.value.int32Values[0];
                            // If auto mode enabled, ignore direct UI set to avoid fighting sensor
                            if (mAutoBrightnessEnabled.load())
                            {
                                LOG(INFO) << "Ignoring manual brightness set because auto-brightness is enabled";
                            }
                            else
                            {
                                writePwm(brightness);
                                mCurrentBrightness = brightness;
                            }
                        }
                        if (updatedValue)
                        {
                            *updatedValue = request;
                            updatedValue->timestamp = elapsedRealtimeNano();
                        }
                        return StatusCode::OK;
                    }
                    else if (propId == VENDOR_AUTO_BRIGHTNESS)
                    {
                        if (!request.value.int32Values.empty())
                        {
                            int val = request.value.int32Values[0];
                            bool enabled = (val != 0);
                            bool prev = mAutoBrightnessEnabled.exchange(enabled);
                            if (enabled && !prev)
                            {
                                LOG(INFO) << "Auto brightness enabled";
                                mAutoTargetBrightness.store(mCurrentBrightness);
                            }
                            else if (!enabled && prev)
                            {
                                LOG(INFO) << "Auto brightness disabled";
                            }
                            if (updatedValue)
                            {
                                *updatedValue = request;
                                updatedValue->timestamp = elapsedRealtimeNano();
                            }
                            if (mOnPropChange)
                            {
                                std::vector<VehiclePropValue> events;
                                VehiclePropValue v;
                                v.prop = VENDOR_AUTO_BRIGHTNESS;
                                v.timestamp = elapsedRealtimeNano();
                                v.value.int32Values = {enabled ? 1 : 0};
                                events.push_back(v);
                                (*mOnPropChange)(events);
                            }
                        }
                        return StatusCode::OK;
                    }
                    return StatusCode::ACCESS_DENIED;
                }

                // GPIO boilerplate unchanged
                int SchuurmanVehicleHardware::readGpio()
                {
                    int fd = open(mGpioChipName.c_str(), O_RDWR);
                    if (fd < 0)
                    {
                        static bool loggedError = false;
                        if (!loggedError)
                        {
                            LOG(ERROR) << "Could not open GPIO chip: " << mGpioChipName << " " << strerror(errno);
                            loggedError = true;
                        }
                        return -1;
                    }

                    struct gpiohandle_request req;
                    memset(&req, 0, sizeof(req));
                    req.lineoffsets[0] = mGpioLineOffset;
                    req.lines = 1;
                    req.flags = GPIOHANDLE_REQUEST_INPUT;

                    int ret = ioctl(fd, GPIO_GET_LINEHANDLE_IOCTL, &req);
                    if (ret < 0)
                    {
                        LOG(ERROR) << "Failed to get GPIO line handle (offset " << mGpioLineOffset << ")";
                        close(fd);
                        return -1;
                    }

                    struct gpiohandle_data data;
                    memset(&data, 0, sizeof(data));
                    ret = ioctl(req.fd, GPIOHANDLE_GET_LINE_VALUES_IOCTL, &data);

                    close(req.fd);
                    close(fd);

                    if (ret < 0)
                        return -1;
                    return data.values[0];
                }

                void SchuurmanVehicleHardware::pollInputs()
                {
                    int lastGpioState = -1;
                    while (!mShuttingDown)
                    {
                        int currentState = readGpio();
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
                        std::this_thread::sleep_for(std::chrono::milliseconds(200));
                    }
                }

                DumpResult SchuurmanVehicleHardware::dump(const std::vector<std::string> &) { return {}; }
                StatusCode SchuurmanVehicleHardware::checkHealth() { return StatusCode::OK; }
                void SchuurmanVehicleHardware::registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) { mOnPropChange = std::move(callback); }
                void SchuurmanVehicleHardware::registerOnPropertySetErrorEvent(std::unique_ptr<const PropertySetErrorCallback> callback) { mOnSetError = std::move(callback); }
                StatusCode SchuurmanVehicleHardware::subscribe(SubscribeOptions) { return StatusCode::OK; }
                StatusCode SchuurmanVehicleHardware::unsubscribe(int32_t, int32_t) { return StatusCode::OK; }
                StatusCode SchuurmanVehicleHardware::updateSampleRate(int32_t, int32_t, float) { return StatusCode::OK; }

            } // vehicle
        } // automotive
    } // hardware
} // android