#pragma once

#include <aidl/android/hardware/automotive/audiocontrol/BnAudioControl.h>
#include <aidl/android/hardware/audio/core/IModule.h>

class GschuurmanAudioControl
    : public aidl::android::hardware::automotive::audiocontrol::BnAudioControl {
public:
    GschuurmanAudioControl();

    ndk::ScopedAStatus setBalanceTowardRight(float value) override;
    ndk::ScopedAStatus setFadeTowardFront(float value) override;

private:
    std::shared_ptr<aidl::android::hardware::audio::core::IModule> mPrimary;

    void sendToAudioHal(const std::string& key, float value);
};
