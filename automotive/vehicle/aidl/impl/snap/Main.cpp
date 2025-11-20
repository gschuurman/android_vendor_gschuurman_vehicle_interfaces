#include "SnapVehicleHardware.h"
#include <android-base/logging.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <DefaultVehicleHal.h>

// Belangrijk: De DefaultVehicleHal interface verwacht de hardware in de automotive namespace
using ::android::hardware::automotive::vehicle::SnapVehicleHardware;
using ::android::hardware::automotive::vehicle::DefaultVehicleHal;
// IVehicle is een AIDL interface
using ::aidl::android::hardware::automotive::vehicle::IVehicle;

int main(int /* argc */, char* /* argv */ []) {
    android::base::InitLogging(nullptr, android::base::LogdLogger());
    LOG(INFO) << "Starten van Snap Automotive VHAL Service...";

    auto hardware = std::make_unique<SnapVehicleHardware>();
    auto vhal = ::ndk::SharedRefBase::make<DefaultVehicleHal>(std::move(hardware));

    const std::string instanceName = std::string(IVehicle::descriptor) + "/default";
    binder_status_t status = AServiceManager_addService(vhal->asBinder().get(), instanceName.c_str());

    if (status != STATUS_OK) {
        LOG(FATAL) << "Kon VHAL service niet registreren. Status: " << status;
    }

    ABinderProcess_setThreadPoolMaxThreadCount(1);
    ABinderProcess_startThreadPool();
    ABinderProcess_joinThreadPool();

    return EXIT_FAILURE;
}