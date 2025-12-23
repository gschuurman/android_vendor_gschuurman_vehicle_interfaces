#include "GschuurmanAudioControl.h"

#include <android-base/logging.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>

#include <aidl/android/hardware/automotive/audiocontrol/IAudioControl.h>

using ::aidl::android::hardware::automotive::audiocontrol::IAudioControl;
using ::aidl::android::hardware::automotive::audiocontrol::impl::GschuurmanAudioControl;

int main() {
    ABinderProcess_setThreadPoolMaxThreadCount(0);
    ABinderProcess_startThreadPool();

    auto svc = ndk::SharedRefBase::make<GschuurmanAudioControl>();

    const std::string instance = std::string(IAudioControl::descriptor) + "/default";
    binder_status_t st = AServiceManager_addService(svc->asBinder().get(), instance.c_str());
    if (st != STATUS_OK) {
        LOG(FATAL) << "Failed to register AudioControl service: " << instance << " status=" << st;
    }

    LOG(INFO) << "Registered AudioControl service: " << instance;
    ABinderProcess_joinThreadPool();
    return 0;
}
