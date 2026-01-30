#include "GnssStubs.h"

#include <android-base/logging.h>
#include <aidl/android/hardware/gnss/IGnssMeasurementCallback.h>

namespace aidl::android::hardware::gnss::usb {

using ndk::ScopedAStatus;

// ------------------------------------------------
// GnssConfiguration
// ------------------------------------------------
class StubGnssConfiguration : public BnGnssConfiguration {
public:
    ScopedAStatus setSuplVersion(int) override { return ScopedAStatus::ok(); }
    ScopedAStatus setSuplMode(int) override { return ScopedAStatus::ok(); }
    ScopedAStatus setLppProfile(int) override { return ScopedAStatus::ok(); }
    ScopedAStatus setGlonassPositioningProtocol(int) override { return ScopedAStatus::ok(); }
    ScopedAStatus setEmergencySuplPdn(bool) override { return ScopedAStatus::ok(); }
    ScopedAStatus setEsExtensionSec(int) override { return ScopedAStatus::ok(); }

    // DO NOT override (not virtual in your tree)
    ScopedAStatus setSuplEs(bool) { return ScopedAStatus::ok(); }

    // DO NOT override (not virtual in your tree)
    ScopedAStatus getBlocklist(std::vector<BlocklistedSource>* r) {
        r->clear();
        return ScopedAStatus::ok();
    }

    ScopedAStatus setBlocklist(const std::vector<BlocklistedSource>&) override {
        return ScopedAStatus::ok();
    }
};

// ------------------------------------------------
// GnssMeasurement
// ------------------------------------------------
class StubGnssMeasurement : public BnGnssMeasurementInterface {
public:

    ScopedAStatus setCallback(
        const std::shared_ptr<IGnssMeasurementCallback>&,
        bool,
        bool) override {
        return ScopedAStatus::ok();
    }

    ScopedAStatus setCallbackWithOptions(
        const std::shared_ptr<IGnssMeasurementCallback>&,
        const IGnssMeasurementInterface::Options&) override {
        return ScopedAStatus::ok();
    }

    // Some trees have close virtual, some don't → no override
    ScopedAStatus close() { return ScopedAStatus::ok(); }
};

// ------------------------------------------------
// GnssPowerIndication
// ------------------------------------------------
class StubGnssPowerIndication : public BnGnssPowerIndication {
public:
    ScopedAStatus setCallback(
        const std::shared_ptr<IGnssPowerIndicationCallback>&) override {
        return ScopedAStatus::ok();
    }

    ScopedAStatus requestGnssPowerStats() override {
        return ScopedAStatus::ok();
    }

    ScopedAStatus close() { return ScopedAStatus::ok(); }
};

// ------------------------------------------------
// GnssDebug
// ------------------------------------------------
class StubGnssDebug : public BnGnssDebug {
public:
    ScopedAStatus getDebugData(DebugData* r) override {
        *r = DebugData{};
        return ScopedAStatus::ok();
    }
};

// ------------------------------------------------
// GnssAntennaInfo
// ------------------------------------------------
class StubGnssAntennaInfo : public BnGnssAntennaInfo {
public:
    ScopedAStatus setCallback(
        const std::shared_ptr<IGnssAntennaInfoCallback>&) override {
        return ScopedAStatus::ok();
    }

    ScopedAStatus close() { return ScopedAStatus::ok(); }
};

// ------------------------------------------------
// Factories
// ------------------------------------------------
std::shared_ptr<IGnssConfiguration> MakeStubGnssConfiguration() {
    return ndk::SharedRefBase::make<StubGnssConfiguration>();
}

std::shared_ptr<IGnssMeasurementInterface> MakeStubGnssMeasurement() {
    return ndk::SharedRefBase::make<StubGnssMeasurement>();
}

std::shared_ptr<IGnssPowerIndication> MakeStubGnssPowerIndication() {
    return ndk::SharedRefBase::make<StubGnssPowerIndication>();
}

std::shared_ptr<IGnssDebug> MakeStubGnssDebug() {
    return ndk::SharedRefBase::make<StubGnssDebug>();
}

std::shared_ptr<IGnssAntennaInfo> MakeStubGnssAntennaInfo() {
    return ndk::SharedRefBase::make<StubGnssAntennaInfo>();
}

}
