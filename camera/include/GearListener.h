#pragma once
#include <functional>
#include <thread>
#include <atomic>
#include <memory>
#include <IVhalClient.h> 

using namespace android::frameworks::automotive::vhal;

class GearListener {
public:
    using Callback = std::function<void(bool isReverse)>;

    GearListener(Callback cb);
    ~GearListener();

    bool start(); // Returns true if VHAL connection succeeded
    void stop();

private:
    void loop(); // Only monitors file override now
    
    // The VHAL callback wrapper
    void onVhalPropertyChange(std::shared_ptr<IHalPropValue> value);

    Callback mCallback;
    std::atomic<bool> mRunning{false};
    std::thread mThread;
    
    // State management
    std::atomic<bool> mReverseState{false};
    std::atomic<bool> mOverrideState{false};

    // VHAL Client Components
    std::shared_ptr<IVhalClient> mVhalClient;
    std::shared_ptr<ISubscriptionClient> mSubscription;
};