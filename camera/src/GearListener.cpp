#include "GearListener.h"
#include "Logger.h"
#include <fstream>
#include <chrono>
#include <aidl/android/hardware/automotive/vehicle/VehicleProperty.h>
#include <aidl/android/hardware/automotive/vehicle/VehicleGear.h>

using ::aidl::android::hardware::automotive::vehicle::VehicleProperty;
using ::aidl::android::hardware::automotive::vehicle::VehicleGear;

GearListener::GearListener(Callback cb) : mCallback(cb) {}

GearListener::~GearListener() { 
    stop(); 
}

bool GearListener::start() {
    TRACE_FUNC();
    mRunning = true;
    
    // 1. Connect to VHAL
    // tryCreate() automatically finds the VHAL AIDL service registered in ServiceManager
    mVhalClient = IVhalClient::tryCreate();
    
    if (mVhalClient) {
        LOGI("Connected to System VHAL");

        // 2. Define Subscription
        auto request = std::make_unique<SubscriptionOptions>();
        request->propId = static_cast<int32_t>(VehicleProperty::GEAR_SELECTION);
        request->areaIds = {0}; // Global
        
        // 3. Register Callback
        auto callback = std::make_shared<SubscriptionCallback>(
            [&](std::shared_ptr<IHalPropValue> val) {
                this->onVhalPropertyChange(val);
            }
        );

        // 4. Execute Subscription
        auto result = mVhalClient->subscribe(std::move(request), callback);
        if (result.ok()) {
            mSubscription = result.value();
            LOGI("Subscribed to GEAR_SELECTION");
        } else {
            LOGE("Failed to subscribe to Gear: %s", result.error().message().c_str());
        }
    } else {
        LOGE("CRITICAL: Could not connect to VHAL Service. Gear info will be unavailable.");
        // We continue anyway to allow the File Override to work even if VHAL is dead
    }

    // 5. Start Override Monitor Thread
    mThread = std::thread(&GearListener::loop, this);
    return true;
}

void GearListener::stop() {
    mRunning = false;
    if (mThread.joinable()) mThread.join();
    
    if (mSubscription) {
        mSubscription->unsubscribe();
        mSubscription = nullptr;
    }
    mVhalClient = nullptr;
}

// REAL VHAL EVENT HANDLER
void GearListener::onVhalPropertyChange(std::shared_ptr<IHalPropValue> value) {
    if (!value || value->getInt32Values().empty()) return;

    int32_t gear = value->getInt32Values()[0];
    bool isReverse = (gear == static_cast<int32_t>(VehicleGear::GEAR_REVERSE));

    // Logic: Only update if override is NOT active.
    // If override is active, we ignore VHAL updates until override is cleared.
    if (!mOverrideState.load()) {
        if (mReverseState.load() != isReverse) {
            mReverseState.store(isReverse);
            LOGI("VHAL Gear Update: %s", isReverse ? "REVERSE" : "DRIVE/PARK");
            if (mCallback) mCallback(isReverse);
        }
    }
}

// File Watcher Loop (High Priority Override)
void GearListener::loop() {
    bool lastOverrideStatus = false;

    while (mRunning) {
        // Check file override
        std::ifstream f("/data/local/tmp/gear_override");
        bool overrideActive = false;
        bool overrideReverse = false;

        if (f.is_open()) {
            std::string line;
            if (std::getline(f, line)) {
                if (line.find("R") != std::string::npos) {
                    overrideActive = true;
                    overrideReverse = true;
                } else if (line.find("D") != std::string::npos) {
                    overrideActive = true;
                    overrideReverse = false;
                }
            }
        }
        
        // State Machine to Handle Override vs VHAL
        if (overrideActive) {
            mOverrideState.store(true);
            if (mReverseState.load() != overrideReverse) {
                mReverseState.store(overrideReverse);
                LOGI("Override Triggered: %s", overrideReverse ? "REVERSE" : "DRIVE");
                if (mCallback) mCallback(overrideReverse);
            }
        } else {
            // Override file removed or empty -> Release lock
            if (mOverrideState.load()) {
                LOGI("Override Removed. Reverting to VHAL state.");
                mOverrideState.store(false);
                // Note: We might want to query get() here to resync immediately, 
                // but the next VHAL event will sync it up.
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }
}