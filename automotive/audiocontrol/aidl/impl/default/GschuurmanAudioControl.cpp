#include "GschuurmanAudioControl.h"

#include <android-base/logging.h>
#include <media/AudioSystem.h>
#include <utils/String8.h>

#include <algorithm>

using ::android::AudioSystem;
using ::android::String8;
using ::android::status_t;

namespace aidl::android::hardware::automotive::audiocontrol::impl {

void GschuurmanAudioControl::sendParameter(const char* key, float value) {
    // [FIX] AudioSystem expects "key=value" format.
    String8 params;
    params.appendFormat("%s=%f", key, value); // Removed .3 precision to ensure raw float is passed if needed, or keep %.3f

    // [FIX] Call setParameters. 
    // Note: This blocks until AudioFlinger processes it.
    status_t st = AudioSystem::setParameters(0, params); // 0 = ioHandle (default)
    
    if (st != ::android::OK) {
        LOG(ERROR) << "AudioSystem::setParameters failed: " << params.c_str() << " status=" << st;
    } else {
        LOG(INFO) << "AudioSystem::setParameters success: " << params.c_str();
    }
}

::ndk::ScopedAStatus GschuurmanAudioControl::setBalanceTowardRight(float value) {
    LOG(INFO) << "setBalanceTowardRight: " << value;
    float clamped = std::clamp(value, -1.0f, 1.0f);
    sendParameter("car.balance", clamped);
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::setFadeTowardFront(float value) {
    LOG(INFO) << "setFadeTowardFront: " << value;
    float clamped = std::clamp(value, -1.0f, 1.0f);
    sendParameter("car.fader", clamped);
    return ::ndk::ScopedAStatus::ok();
}

// ... Keep the rest of the file (callbacks) as is ...
// Just ensure you include the necessary headers for the types used in callbacks.

::ndk::ScopedAStatus GschuurmanAudioControl::onAudioFocusChange(
        const std::string&, int32_t, AudioFocusChange) {
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::onDevicesToDuckChange(
        const std::vector<DuckingInfo>&) {
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::onDevicesToMuteChange(
        const std::vector<MutingInfo>&) {
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::registerFocusListener(
        const std::shared_ptr<IFocusListener>&) {
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::onAudioFocusChangeWithMetaData(
        const ::aidl::android::hardware::audio::common::PlaybackTrackMetadata&,
        int32_t,
        AudioFocusChange) {
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::setAudioDeviceGainsChanged(
        const std::vector<Reasons>&,
        const std::vector<AudioGainConfigInfo>&) {
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::registerGainCallback(
        const std::shared_ptr<IAudioGainCallback>&) {
    return ::ndk::ScopedAStatus::ok();
}

}  // namespace aidl::android::hardware::automotive::audiocontrol::impl