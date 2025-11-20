#include "SnapVehicleHardware.h"
#include <android-base/logging.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <IVehicleHardware.h>
#include <DefaultVehicleHal.h>

using ::android::hardware::automotive::vehicle::SnapVehicleHardware;
using ::android::hardware::automotive::vehicle::DefaultVehicleHal;
using ::aidl::android::hardware::automotive::vehicle::IVehicle;

int main(int /* argc */, char* /* argv */ []) {
    // Initialiseer logging
    android::base::InitLogging(nullptr, android::base::LogdLogger());
    LOG(INFO) << "Starten van Snap Automotive VHAL Service...";

    // 1. Maak jouw hardware object aan
    auto hardware = std::make_unique<SnapVehicleHardware>();

    // 2. Wikkel het in de standaard Android VHAL logica
    auto vhal = ::ndk::SharedRefBase::make<DefaultVehicleHal>(std::move(hardware));

    // 3. Registreer de service bij de Binder Manager
    const std::string instanceName = std::string(IVehicle::descriptor) + "/default";
    binder_status_t status = AServiceManager_addService(vhal->asBinder().get(), instanceName.c_str());

    if (status != STATUS_OK) {
        LOG(FATAL) << "Kon VHAL service niet registreren. Status: " << status;
    }

    LOG(INFO) << "Snap VHAL is geregistreerd en klaar voor actie.";

    // 4. Start de thread pool en wacht op verzoeken van Android
    ABinderProcess_setThreadPoolMaxThreadCount(1);
    ABinderProcess_startThreadPool();
    ABinderProcess_joinThreadPool();

    return EXIT_FAILURE; // Zou hier nooit moeten komen
}