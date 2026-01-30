#pragma once

#include <aidl/android/hardware/gnss/BnGnss.h>
#include <aidl/android/hardware/gnss/IGnssCallback.h>

#include <atomic>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace aidl::android::hardware::gnss::usb {

class GnssUsb : public ::aidl::android::hardware::gnss::BnGnss {
public:
    GnssUsb();
    ~GnssUsb() override;

    // IGnss
    ::ndk::ScopedAStatus setCallback(
        const std::shared_ptr<::aidl::android::hardware::gnss::IGnssCallback>& callback) override;
    ::ndk::ScopedAStatus close() override;

    ::ndk::ScopedAStatus start() override;
    ::ndk::ScopedAStatus stop() override;

    ::ndk::ScopedAStatus injectTime(int64_t timeMs, int64_t timeReferenceMs,
                                    int32_t uncertaintyMs) override;
    ::ndk::ScopedAStatus injectLocation(
        const ::aidl::android::hardware::gnss::GnssLocation& location) override;
    ::ndk::ScopedAStatus injectBestLocation(
        const ::aidl::android::hardware::gnss::GnssLocation& location) override;
    ::ndk::ScopedAStatus deleteAidingData(
        ::aidl::android::hardware::gnss::IGnss::GnssAidingData aidingDataFlags) override;

    ::ndk::ScopedAStatus setPositionMode(
        const ::aidl::android::hardware::gnss::IGnss::PositionModeOptions& options) override;

    ::ndk::ScopedAStatus startSvStatus() override;
    ::ndk::ScopedAStatus stopSvStatus() override;
    ::ndk::ScopedAStatus startNmea() override;
    ::ndk::ScopedAStatus stopNmea() override;

    // Extensions (many are stubs)
    ::ndk::ScopedAStatus getExtensionPsds(
        std::shared_ptr<::aidl::android::hardware::gnss::IGnssPsds>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionGnssConfiguration(
        std::shared_ptr<::aidl::android::hardware::gnss::IGnssConfiguration>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionGnssMeasurement(
        std::shared_ptr<::aidl::android::hardware::gnss::IGnssMeasurementInterface>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionGnssPowerIndication(
        std::shared_ptr<::aidl::android::hardware::gnss::IGnssPowerIndication>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionGnssBatching(
        std::shared_ptr<::aidl::android::hardware::gnss::IGnssBatching>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionGnssGeofence(
        std::shared_ptr<::aidl::android::hardware::gnss::IGnssGeofence>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionGnssNavigationMessage(
        std::shared_ptr<::aidl::android::hardware::gnss::IGnssNavigationMessageInterface>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionAGnss(
        std::shared_ptr<::aidl::android::hardware::gnss::IAGnss>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionAGnssRil(
        std::shared_ptr<::aidl::android::hardware::gnss::IAGnssRil>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionGnssDebug(
        std::shared_ptr<::aidl::android::hardware::gnss::IGnssDebug>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionGnssVisibilityControl(
        std::shared_ptr<::aidl::android::hardware::gnss::visibility_control::IGnssVisibilityControl>* _aidl_return)
        override;
    ::ndk::ScopedAStatus getExtensionGnssAntennaInfo(
        std::shared_ptr<::aidl::android::hardware::gnss::IGnssAntennaInfo>* _aidl_return) override;
    ::ndk::ScopedAStatus getExtensionMeasurementCorrections(
        std::shared_ptr<::aidl::android::hardware::gnss::measurement_corrections::IMeasurementCorrectionsInterface>*
            _aidl_return) override;

private:
    void ReaderThreadMain();
    void StopReaderLocked();

    std::mutex mutex_;
    std::shared_ptr<::aidl::android::hardware::gnss::IGnssCallback> callback_;

    std::atomic<bool> running_{false};
    std::atomic<bool> nmeaEnabled_{false};

    std::string devicePath_;
    int baudrate_ = 9600;

    int serialFd_ = -1;
    std::thread readerThread_;

    ::aidl::android::hardware::gnss::IGnss::PositionModeOptions positionMode_{};

    // Stub extension objects
    std::shared_ptr<::aidl::android::hardware::gnss::IGnssConfiguration> cfg_;
    std::shared_ptr<::aidl::android::hardware::gnss::IGnssMeasurementInterface> meas_;
    std::shared_ptr<::aidl::android::hardware::gnss::IGnssPowerIndication> power_;
    std::shared_ptr<::aidl::android::hardware::gnss::IGnssDebug> debug_;
    std::shared_ptr<::aidl::android::hardware::gnss::IGnssAntennaInfo> antenna_;
};

}  // namespace aidl::android::hardware::gnss::usb
