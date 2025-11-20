#include "SnapVehicleHardware.h"

#include <android-base/logging.h>
#include <android-base/properties.h>
#include <fstream>
#include <thread>
#include <chrono>
#include <vector>

#include "IVehicleHardware.h"
#include "VehicleUtils.h"

// Definieer hardware paden (Check dit op je VIM3 met 'ls /sys/class/...')
#define PATH_GPIO_REVERSE   "/sys/class/gpio/gpio496/value" // Voorbeeld GPIO
#define PATH_PWM_BRIGHTNESS "/sys/class/pwm/pwmchip0/pwm0/duty_cycle"
#define PATH_PWM_PERIOD     "/sys/class/pwm/pwmchip0/pwm0/period"
#define PATH_PWM_ENABLE     "/sys/class/pwm/pwmchip0/pwm0/enable"

using namespace android::hardware::automotive::vehicle;
using namespace android::hardware::automotive::vehicle::aidl_utils;

class SnapVehicleHardware : public IVehicleHardware {
public:
    SnapVehicleHardware() {
        // Initialiseer hardware bij opstarten
        initPwm();
        // Start de polling thread voor input (Reverse gear)
        mPollThread = std::thread(&SnapVehicleHardware::pollInputs, this);
    }

    ~SnapVehicleHardware() {
        mShuttingDown = true;
        if (mPollThread.joinable()) mPollThread.join();
    }

    // 1. Definieer welke properties wij ondersteunen
    std::vector<VehiclePropConfig> getAllPropertyConfigs() const override {
        std::vector<VehiclePropConfig> configs;

        // Config: GEAR_SELECTION (Alleen Lezen)
        VehiclePropConfig gearConfig;
        gearConfig.prop = toInt(VehicleProperty::GEAR_SELECTION);
        gearConfig.access = VehiclePropertyAccess::READ;
        gearConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        configs.push_back(gearConfig);

        // Config: DISPLAY_BRIGHTNESS (Lezen en Schrijven)
        VehiclePropConfig brightConfig;
        brightConfig.prop = toInt(VehicleProperty::DISPLAY_BRIGHTNESS);
        brightConfig.access = VehiclePropertyAccess::READ_WRITE;
        brightConfig.changeMode = VehiclePropertyChangeMode::ON_CHANGE;
        brightConfig.areaConfigs = {
            {.minInt32Value = 0, .maxInt32Value = 100} // 0% tot 100%
        };
        configs.push_back(brightConfig);

        return configs;
    }

    // 2. Android vraagt om een waarde (Get)
    StatusCode getValue(const VehiclePropValue& request, VehiclePropValue* response) const override {
        int propId = request.prop;
        response->prop = propId;
        response->timestamp = elapsedRealtimeNano();

        switch (propId) {
            case toInt(VehicleProperty::GEAR_SELECTION):
                // Lees de opgeslagen status (geupdate door polling thread)
                response->value.int32Values = {mCurrentGear};
                return StatusCode::OK;

            case toInt(VehicleProperty::DISPLAY_BRIGHTNESS):
                response->value.int32Values = {mCurrentBrightness};
                return StatusCode::OK;

            default:
                return StatusCode::INVALID_ARG;
        }
    }

    // 3. Android stuurt een waarde (Set)
    StatusCode setValue(const VehiclePropValue& request, VehiclePropValue* updatedValue) override {
        int propId = request.prop;

        switch (propId) {
            case toInt(VehicleProperty::DISPLAY_BRIGHTNESS): {
                int brightness = request.value.int32Values[0];
                if (brightness < 0 || brightness > 100) return StatusCode::INVALID_ARG;
                
                // Hardware Actie: Schrijf naar PWM
                writePwm(brightness);
                
                // Update interne status
                mCurrentBrightness = brightness;
                
                // Stuur de update terug (voor bevestiging)
                if (updatedValue) {
                    updatedValue->prop = propId;
                    updatedValue->timestamp = elapsedRealtimeNano();
                    updatedValue->value.int32Values = {brightness};
                }
                return StatusCode::OK;
            }
            default:
                // Gear selection is read-only, dus mag niet ge-set worden
                return StatusCode::ACCESS_DENIED;
        }
    }

    // Boilerplate (vereist door interface, leeg laten voor dunne implementatie)
    StatusCode dump(int fd, const std::vector<std::string>& args) override { return StatusCode::OK; }
    StatusCode checkHealth() override { return StatusCode::OK; }
    void registerOnPropertyChangeEvent(std::unique_ptr<const PropertyChangeCallback> callback) override {
        // Sla de callback op om events naar Android te sturen (bv. Gear change)
        mOnPropChange = std::move(callback);
    }
    StatusCode subscribe(const SubscribeOptions& options) override { return StatusCode::OK; }
    StatusCode unsubscribe(int32_t propId) override { return StatusCode::OK; }

private:
    // Interne variabelen
    int32_t mCurrentGear = toInt(VehicleGear::GEAR_PARK);
    int32_t mCurrentBrightness = 50;
    
    std::thread mPollThread;
    std::atomic<bool> mShuttingDown{false};
    std::unique_ptr<const PropertyChangeCallback> mOnPropChange;

    // --- Hardware Helpers ---

    void initPwm() {
        // Zet PWM period (bv. 50000ns = 20kHz) en enable
        writeSysFs(PATH_PWM_PERIOD, "50000"); 
        writeSysFs(PATH_PWM_ENABLE, "1");
    }

    void writePwm(int percentage) {
        // Converteer 0-100% naar duty cycle (0 - 50000)
        int duty = (percentage * 50000) / 100;
        writeSysFs(PATH_PWM_BRIGHTNESS, std::to_string(duty));
    }

    void pollInputs() {
        int lastGpioState = -1;

        while (!mShuttingDown) {
            // Lees GPIO (Simpele file read, in productie gebruik je epoll)
            std::ifstream gpioFile(PATH_GPIO_REVERSE);
            int currentState;
            if (gpioFile >> currentState) {
                
                if (currentState != lastGpioState) {
                    // Status is veranderd!
                    mCurrentGear = (currentState == 1) ? 
                                   toInt(VehicleGear::GEAR_REVERSE) : 
                                   toInt(VehicleGear::GEAR_DRIVE);

                    // Informeer Android DIRECT (Event driven)
                    if (mOnPropChange) {
                        std::vector<VehiclePropValue> events;
                        VehiclePropValue v;
                        v.prop = toInt(VehicleProperty::GEAR_SELECTION);
                        v.timestamp = elapsedRealtimeNano();
                        v.value.int32Values = {mCurrentGear};
                        events.push_back(v);
                        (*mOnPropChange)(events);
                    }
                    lastGpioState = currentState;
                }
            }
            // Slaap even om CPU te sparen (100ms)
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }

    void writeSysFs(const std::string& path, const std::string& val) {
        std::ofstream file(path);
        if (file.is_open()) {
            file << val;
        } else {
            LOG(ERROR) << "Kan niet schrijven naar: " << path;
        }
    }
};