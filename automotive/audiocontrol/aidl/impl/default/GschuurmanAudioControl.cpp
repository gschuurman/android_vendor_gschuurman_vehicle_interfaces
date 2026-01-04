/*
 * Copyright (C) 2023 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "GschuurmanAudioControl.h"

#include <android-base/logging.h>
#include <media/AudioSystem.h>
#include <utils/String8.h>

namespace aidl::android::hardware::automotive::audiocontrol::impl {

// Automotive Volume Curve Configuration
// These should roughly match what is defined in audio_policy_configuration.xml or valid ranges
static constexpr int32_t kStepValueMB = 100;   // 100 Millibels = 1 dB per step
static constexpr int32_t kMinValueMB = -6000;  // -6000 Millibels = -60 dB (Min Volume)

// Helper to convert index to dB
static float indexToDb(int32_t index) {
    int32_t valueMB = kMinValueMB + (index * kStepValueMB);
    return valueMB / 100.0f;
}

// Balance: -1.0 (Left) to 1.0 (Right)
::ndk::ScopedAStatus GschuurmanAudioControl::setBalanceTowardRight(float value) {
    LOG(DEBUG) << "AudioControl: setBalanceTowardRight " << value;
    sendParameter("car.balance", value);
    return ::ndk::ScopedAStatus::ok();
}

// Fader: -1.0 (Rear) to 1.0 (Front)
::ndk::ScopedAStatus GschuurmanAudioControl::setFadeTowardFront(float value) {
    LOG(DEBUG) << "AudioControl: setFadeTowardFront " << value;
    sendParameter("car.fader", value);
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::onAudioFocusChange(
        const std::string& in_usage,
        int32_t in_zoneId,
        AudioFocusChange in_focusChange) {
    LOG(VERBOSE) << "AudioControl: onAudioFocusChange usage=" << in_usage 
                 << " zone=" << in_zoneId 
                 << " change=" << toString(in_focusChange);
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::onDevicesToDuckChange(
        const std::vector<DuckingInfo>& in_duckingInfos) {
    LOG(VERBOSE) << "AudioControl: onDevicesToDuckChange " << in_duckingInfos.size();
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::onDevicesToMuteChange(
        const std::vector<MutingInfo>& in_mutingInfos) {
    LOG(VERBOSE) << "AudioControl: onDevicesToMuteChange " << in_mutingInfos.size();
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::registerFocusListener(
        const std::shared_ptr<IFocusListener>& in_listener) {
    LOG(DEBUG) << "AudioControl: registerFocusListener " << (in_listener ? "ok" : "null");
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::onAudioFocusChangeWithMetaData(
        const ::aidl::android::hardware::audio::common::PlaybackTrackMetadata& in_playbackMetaData,
        int32_t in_zoneId,
        AudioFocusChange in_focusChange) {
    LOG(VERBOSE) << "AudioControl: onAudioFocusChangeWithMetaData zone=" << in_zoneId 
                 << " change=" << toString(in_focusChange);
    (void)in_playbackMetaData;
    return ::ndk::ScopedAStatus::ok();
}

// VOLUME CONTROL LOGIC
::ndk::ScopedAStatus GschuurmanAudioControl::setAudioDeviceGainsChanged(
        const std::vector<Reasons>& in_reasons,
        const std::vector<AudioGainConfigInfo>& in_gains) {
    
    (void)in_reasons; // Unused for now

    for (const auto& gainInfo : in_gains) {
        const std::string& address = gainInfo.devicePortAddress;
        int32_t index = gainInfo.volumeIndex;

        // Convert the UI Index (0..Max) to dB (-60..0)
        float valueDB = indexToDb(index);

        LOG(INFO) << "AudioControl: Setting gain for port '" << address 
                  << "' index=" << index 
                  << " to " << valueDB << "dB";

        // Send to Audio HAL via AudioSystem
        // Key: "bus0_media_out", Value: "-20.0"
        sendParameter(address.c_str(), valueDB);
    }
    return ::ndk::ScopedAStatus::ok();
}

::ndk::ScopedAStatus GschuurmanAudioControl::registerGainCallback(
        const std::shared_ptr<IAudioGainCallback>& in_callback) {
    LOG(DEBUG) << "AudioControl: registerGainCallback " << (in_callback ? "ok" : "null");
    return ::ndk::ScopedAStatus::ok();
}

// PRIVATE HELPER to talk to AudioFlinger/AudioHAL
void GschuurmanAudioControl::sendParameter(const char* key, float value) {
    // Construct "key=value" string
    // FIX: Explicitly refer to the root android namespace using ::android
    ::android::String8 param;
    param.appendFormat("%s=%f", key, value);

    // Send global parameter (ioHandle 0)
    ::android::status_t status = ::android::AudioSystem::setParameters(0, param);
    
    if (status != ::android::OK) {
        LOG(ERROR) << "AudioControl: Failed to set parameter '" << param.c_str() 
                   << "' error=" << status;
    } else {
        LOG(DEBUG) << "AudioControl: Sent '" << param.c_str() << "'";
    }
}

}  // namespace aidl::android::hardware::automotive::audiocontrol::impl