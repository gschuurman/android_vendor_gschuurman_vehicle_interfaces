#include "GSchuurmanVehicleHardware.h"
#include <DefaultVehicleHal.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <android-base/logging.h>
#include <utils/Log.h>

using ::android::hardware::automotive::vehicle::gschuurman::GSchuurmanVehicleHardware;
using ::android::hardware::automotive::vehicle::DefaultVehicleHal;
using ::aidl::android::hardware::automotive::vehicle::IVehicle;

int main(int /* argc */, char* /* argv */ []) {
    // Initialiseer logging
    android::base::InitLogging(nullptr, android::base::LogdLogger(android::base::SYSTEM));
    LOG(INFO) << "Starting GSchuurman Vehicle HAL...";

    // 1. Maak instantie van jouw Hardware interface
    auto hardware = std::make_unique<GSchuurmanVehicleHardware>();

    // 2. Maak de DefaultVehicleHal wrapper (Google's logica)
    // Deze wrapper beheert permissies, event batches, etc.
    auto vhal = ::ndk::SharedRefBase::make<DefaultVehicleHal>(std::move(hardware));

    // 3. Start Binder thread pool
    ABinderProcess_setThreadPoolMaxThreadCount(4);
    ABinderProcess_startThreadPool();

    // 4. Registreer de service
    // De naam moet matchen met wat in de VINTF manifest staat (later)
    const std::string instance = std::string(IVehicle::descriptor) + "/default";
    binder_status_t status = AServiceManager_addService(vhal->asBinder().get(), instance.c_str());

    if (status != STATUS_OK) {
        LOG(FATAL) << "Could not register service " << instance << " status: " << status;
        return 1;
    }

    LOG(INFO) << "GSchuurman VHAL Ready!";
    
    // 5. Houd de process in leven
    ABinderProcess_joinThreadPool();

    return 0;
}