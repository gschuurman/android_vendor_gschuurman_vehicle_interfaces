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
                      mShuttingDown(false)
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

                    // 4. Thread starten
                    mPollThread = std::thread(&SchuurmanVehicleHardware::pollInputs, this);
                }

                SchuurmanVehicleHardware::~SchuurmanVehicleHardware()
                {
                    mShuttingDown = true;
                    if (mPollThread.joinable())
                        mPollThread.join();
                }

                // --- SETUP FUNCTIE (Draait 1x bij boot) ---
                void SchuurmanVehicleHardware::initPwm()
                {
                    LOG(INFO) << "Initializing PWM Hardware (safe mode, do not write period) ...";

                    // Ensure pwm1 exists (try export if necessary)
                    std::string chipBase = findPwmChipPath();
                    ensurePwmExported(chipBase);

                    // Read kernel period (do NOT overwrite it)
                    int kernelPeriod = readSysFsInt(mPathPwmPeriod);
                    if (kernelPeriod <= 0)
                    {
                        LOG(ERROR) << "Could not read kernel PWM period from " << mPathPwmPeriod << ". Retrying...";
                        // Retry a few times
                        kernelPeriod = readSysFsInt(mPathPwmPeriod);
                    }

                    if (kernelPeriod > 0)
                    {
                        mPwmPeriodNs = kernelPeriod;
                        LOG(INFO) << "Kernel reports PWM period: " << mPwmPeriodNs << " ns. We will not change it.";
                    }
                    else
                    {
                        // Last resort: use a safe default but log that it's a guess
                        mPwmPeriodNs = 30518; // fallback but we document it's a fallback
                        LOG(ERROR) << "Failed to read PWM period. Using fallback: " << mPwmPeriodNs << " ns (unsafe).";
                    }

                    // Make sure PWM is disabled initially
                    writeSysFs(mPathPwmEnable, "0");

                    // Initialize duty to 0 (safe)
                    writeSysFs(mPathPwmDuty, "0");

                    // Do NOT write period.
                    // Finally enable if needed (we can leave it disabled until first writePwm if preferred)
                    writeSysFs(mPathPwmEnable, "1");
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
                    if (kernelPeriod <= 0)
                    {
                        LOG(WARNING) << "writePwm: invalid kernel period read; skipping duty write to avoid flicker";
                        return; // do not attempt to write with invalid period (prevents flicker)
                    }

                    mPwmPeriodNs = kernelPeriod;

                    long long dutyCalc = ((long long)inverted * (long long)mPwmPeriodNs) / 100;
                    if (dutyCalc < 0)
                        dutyCalc = 0;
                    if (dutyCalc > mPwmPeriodNs)
                        dutyCalc = mPwmPeriodNs;

                    // debounce: only write if duty actually changed
                    static std::atomic<long long> s_lastDuty(-1);
                    long long last = s_lastDuty.load(std::memory_order_relaxed);
                    if (last == dutyCalc) {
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
                                // trim spaces/newline
                                auto start = s.find_first_not_of(" \t\r\n");
                                auto end = s.find_last_not_of(" \t\r\n");
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
                    std::string pwm1Path = chipBase + "/pwm1";
                    if (fileExists(pwm1Path))
                        return;
                    std::string exportPath = chipBase + "/export";
                    if (!fileExists(exportPath))
                    {
                        LOG(ERROR) << "PWM export not available at " << exportPath;
                        return;
                    }
                    // Write '1' to export and wait a bit for the sysfs node to appear
                    writeSysFs(exportPath, "1");
                    for (int i = 0; i < 10; ++i)
                    {
                        if (fileExists(pwm1Path))
                            return;
                        std::this_thread::sleep_for(std::chrono::milliseconds(30));
                    }
                    LOG(ERROR) << "pwm1 did not appear under " << chipBase << " after export";
                }

                // --- STANDAARD VHAL BOILERPLATE (Niets veranderd) ---

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
                        if (!request.value.int32Values.empty())
                        {
                            int brightness = request.value.int32Values[0];
                            // Update PWM
                            writePwm(brightness);
                            mCurrentBrightness = brightness;
                        }
                        if (updatedValue)
                        {
                            *updatedValue = request;
                            updatedValue->timestamp = elapsedRealtimeNano();
                        }
                        return StatusCode::OK;
                    }
                    return StatusCode::ACCESS_DENIED;
                }

                // GPIO boilerplate
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
