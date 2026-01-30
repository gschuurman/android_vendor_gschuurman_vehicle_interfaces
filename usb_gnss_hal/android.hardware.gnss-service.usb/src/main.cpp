#include <android/binder_manager.h>
#include <android/binder_process.h>
#include <android-base/logging.h>

#include "GnssUsb.h"

using aidl::android::hardware::gnss::usb::GnssUsb;

int main() {
    android::base::InitLogging(nullptr, android::base::LogdLogger(android::base::SYSTEM));
    LOG(INFO) << "GnssUsbHal starting";

    ABinderProcess_setThreadPoolMaxThreadCount(4);
    ABinderProcess_startThreadPool();

    auto service = ndk::SharedRefBase::make<GnssUsb>();
    const std::string instance = std::string() + GnssUsb::descriptor + "/default";

    binder_status_t status = AServiceManager_addService(service->asBinder().get(), instance.c_str());
    if (status != STATUS_OK) {
        LOG(ERROR) << "Failed to register " << instance << " status=" << status;
        return 1;
    }
    LOG(INFO) << "Registered " << instance;

    ABinderProcess_joinThreadPool();
    return 0;
}
