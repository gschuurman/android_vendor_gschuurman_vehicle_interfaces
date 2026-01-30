#pragma once

#include <memory>

#include <aidl/android/hardware/gnss/BnGnssConfiguration.h>
#include <aidl/android/hardware/gnss/BnGnssMeasurementInterface.h>
#include <aidl/android/hardware/gnss/BnGnssPowerIndication.h>
#include <aidl/android/hardware/gnss/BnGnssDebug.h>
#include <aidl/android/hardware/gnss/BnGnssAntennaInfo.h>

namespace aidl::android::hardware::gnss::usb {

using namespace ::aidl::android::hardware::gnss;

std::shared_ptr<IGnssConfiguration> MakeStubGnssConfiguration();
std::shared_ptr<IGnssMeasurementInterface> MakeStubGnssMeasurement();
std::shared_ptr<IGnssPowerIndication> MakeStubGnssPowerIndication();
std::shared_ptr<IGnssDebug> MakeStubGnssDebug();
std::shared_ptr<IGnssAntennaInfo> MakeStubGnssAntennaInfo();

}
