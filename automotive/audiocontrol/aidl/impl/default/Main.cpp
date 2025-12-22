#include <android-base/logging.h>
#include <android/binder_manager.h>
#include <android/binder_process.h>

#include "GschuurmanAudioControl.h"

using aidl::android::hardware::automotive::audiocontrol::IAudioControl;

int main() {
    ABinderProcess_setThreadPoolMaxThreadCount(0);
    ABinderProcess_startThreadPool();

    auto service = ndk::SharedRefBase::make<GschuurmanAudioControl>();

    const std::string instance =
            std::string(IAudioControl::descriptor) + "/default";

    if (AServiceManager_addService(service->asBinder().get(),
                                   instance.c_str()) != STATUS_OK) {
        LOG(FATAL) << "Failed to register AudioControl service";
    }

    LOG(INFO) << "AudioControl service registered: " << instance;
    ABinderProcess_joinThreadPool();
    return 0;
}
