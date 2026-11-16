#pragma once

#include <aidl/android/hardware/automotive/audiocontrol/BnAudioControl.h>

#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <vector>

#include <IVhalClient.h>

namespace aidl::android::hardware::automotive::audiocontrol::impl {

class GschuurmanAudioControl : public BnAudioControl {
public:
    GschuurmanAudioControl() = default;

    // Balance / Fader
    ::ndk::ScopedAStatus setBalanceTowardRight(float value) override;
    ::ndk::ScopedAStatus setFadeTowardFront(float value) override;

    // Required AudioControl V2 methods (safe no-ops for now)
    ::ndk::ScopedAStatus onAudioFocusChange(
            const std::string& in_usage,
            int32_t in_zoneId,
            AudioFocusChange in_focusChange) override;

    ::ndk::ScopedAStatus onDevicesToDuckChange(
            const std::vector<DuckingInfo>& in_duckingInfos) override;

    ::ndk::ScopedAStatus onDevicesToMuteChange(
            const std::vector<MutingInfo>& in_mutingInfos) override;

    ::ndk::ScopedAStatus registerFocusListener(
            const std::shared_ptr<IFocusListener>& in_listener) override;

    ::ndk::ScopedAStatus onAudioFocusChangeWithMetaData(
            const ::aidl::android::hardware::audio::common::PlaybackTrackMetadata& in_playbackMetaData,
            int32_t in_zoneId,
            AudioFocusChange in_focusChange) override;

    ::ndk::ScopedAStatus setAudioDeviceGainsChanged(
            const std::vector<Reasons>& in_reasons,
            const std::vector<AudioGainConfigInfo>& in_gains) override;

    ::ndk::ScopedAStatus registerGainCallback(
            const std::shared_ptr<IAudioGainCallback>& in_callback) override;

private:
    void sendParameter(const char* key, float value);
    // Hard-mutes (or releases) the DACs on the car audio module through the VHAL
    // (MCU_PROP_AUDIO_MUTE). Returns false if the VHAL isn't reachable yet.
    bool setHardwareMute(bool mute);
    void updateHardwareMuteLocked();

    std::mutex mLock;
    // Primary zone output buses CarAudioService told us about, and the muted ones.
    std::set<std::string> mKnownDevices;
    std::set<std::string> mMutedDevices;
    bool mHwMuteSent = false;  // mHwMute reflects what the MCU was last told
    bool mHwMute = false;
    std::shared_ptr<::android::frameworks::automotive::vhal::IVhalClient> mVhal;
};

}  // namespace aidl::android::hardware::automotive::audiocontrol::impl
