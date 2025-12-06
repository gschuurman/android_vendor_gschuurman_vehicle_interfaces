#include "SchuurmanVehicleHardware.h" // Aangepaste include
#include <android-base/logging.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <DefaultVehicleHal.h>

using ::android::hardware::automotive::vehicle::DefaultVehicleHal;
using ::android::hardware::automotive::vehicle::SchuurmanVehicleHardware; // Aangepaste namespace/class
using ::aidl::android::hardware::automotive::vehicle::IVehicle;

int main(int /* argc */, char * /* argv */[])
{
    android::base::InitLogging(nullptr, android::base::LogdLogger());
    LOG(INFO) << "Starting Schuurman IT Automotive VHAL Service...";

    auto hardware = std::make_unique<SchuurmanVehicleHardware>(); // Aangepaste class
    auto vhal = ::ndk::SharedRefBase::make<DefaultVehicleHal>(std::move(hardware));

    const std::string instanceName = std::string(IVehicle::descriptor) + "/default";
    binder_status_t status = AServiceManager_addService(vhal->asBinder().get(), instanceName.c_str());

    if (status != STATUS_OK)
    {
        LOG(FATAL) << "Failed to register VHAL service. Status: " << status;
    }

    ABinderProcess_setThreadPoolMaxThreadCount(1);
    ABinderProcess_startThreadPool();
    ABinderProcess_joinThreadPool();

    return EXIT_FAILURE;
}