#pragma once
#include <camera/NdkCameraManager.h>
#include <camera/NdkCameraDevice.h>
#include <camera/NdkCameraCaptureSession.h>
#include <android/native_window.h>
#include "RecorderSystem.h"

class CameraSystem {
public:
    struct Config {
        ANativeWindow* displayWindow;
        bool enableTestPattern;
        bool recordMode;
        std::string recordPath;
    };

    CameraSystem();
    ~CameraSystem();

    // Initialize and pick the best camera
    bool initialize(); 
    
    // Start streaming to display (and recorder if config set)
    bool startPreview(const Config& config);
    
    // Stop all streams
    void stopPreview();

private:
    void findBestResolution(const char* cameraId, int& w, int& h);
    
    // NDK Callbacks
    static void onDisconnected(void* context, ACameraDevice* device);
    static void onError(void* context, ACameraDevice* device, int error);

    ACameraManager* mManager = nullptr;
    ACameraDevice* mDevice = nullptr;
    ACameraCaptureSession* mSession = nullptr;
    ACaptureRequest* mRequest = nullptr;
    ACameraOutputTarget* mDisplayTarget = nullptr;
    ACameraOutputTarget* mRecordTarget = nullptr;

    RecorderSystem mRecorder;
    std::string mActiveCameraId;
    int mWidth = 1920;
    int mHeight = 1080;
};