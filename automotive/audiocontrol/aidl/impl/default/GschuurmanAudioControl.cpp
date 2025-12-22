#include "GschuurmanAudioControl.h"

#include <android-base/logging.h>
#include <android/binder_manager.h>
#include <algorithm>

using aidl::android::hardware::audio::core::IModule;
using aidl::android::media::audio::common::Float;
using aidl::android::media::audio::common::VendorParameter;

GschuurmanAudioControl::GschuurmanAudioControl() {
    const char* candidates[] = {
        "android.hardware.audio.core.IModule/primary",
        "android.hardware.audio.core.IModule/default",
    };

    for (const char* name : candidates) {
        if (AServiceManager_isDeclared(name)) {
            ndk::SpAIBinder binder(AServiceManager_waitForService(name));
            mPrimary = IModule::fromBinder(binder);
            if (mPrimary) {
                LOG(INFO) << "Connected to Audio HAL module: " << name;
                break;
            }
        }
    }

    if (!mPrimary) {
        LOG(ERROR) << "Failed to connect to Audio HAL module";
    }
}

void GschuurmanAudioControl::sendToAudioHal(
        const std::string& key, float value) {
    if (!mPrimary) return;

    VendorParameter param;
    param.id = key;
    param.ext.set<Float>(Float{value});

    std::vector<VendorParameter> params{param};
    mPrimary->setVendorParameters(params, false);
}

ndk::ScopedAStatus
GschuurmanAudioControl::setBalanceTowardRight(float value) {
    value = std::clamp(value, -1.0f, 1.0f);
    sendToAudioHal("car.balance", value);
    return ndk::ScopedAStatus::ok();
}

ndk::ScopedAStatus
GschuurmanAudioControl::setFadeTowardFront(float value) {
    value = std::clamp(value, -1.0f, 1.0f);
    sendToAudioHal("car.fader", value);
    return ndk::ScopedAStatus::ok();
}
