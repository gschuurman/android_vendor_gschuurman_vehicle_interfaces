#include "CameraSystem.h"
#include "Logger.h"
#include <vector>
#include <cstring>
#include <algorithm>
#include <android/native_window.h>

CameraSystem::CameraSystem() {
    mManager = ACameraManager_create();
}

CameraSystem::~CameraSystem() {
    stopPreview();
    if (mManager) ACameraManager_delete(mManager);
}

// Helper to handle Camera Device state
void CameraSystem::onDisconnected(void* ctx, ACameraDevice* dev) {
    LOGE("Camera Disconnected");
    reinterpret_cast<CameraSystem*>(ctx)->stopPreview();
}

void CameraSystem::onError(void* ctx, ACameraDevice* dev, int err) {
    LOGE("Camera Error: %d", err);
}

bool CameraSystem::initialize() {
    TRACE_FUNC();
    ACameraIdList* idList = nullptr;
    if (ACameraManager_getCameraIdList(mManager, &idList) != ACAMERA_OK) return false;

    // Logic: Find first camera (usually 0 or external). 
    // In a real AAOS car, this is often explicitly defined by ID "0" or "100".
    if (idList->numCameras > 0) {
        mActiveCameraId = idList->cameraIds[0];
        LOGI("Selected Camera: %s", mActiveCameraId.c_str());
        
        // Log supported resolutions
        findBestResolution(mActiveCameraId.c_str(), mWidth, mHeight);
    }

    ACameraManager_deleteCameraIdList(idList);
    return !mActiveCameraId.empty();
}

void CameraSystem::findBestResolution(const char* id, int& w, int& h) {
    ACameraMetadata* meta;
    ACameraManager_getCameraCharacteristics(mManager, id, &meta);
    
    ACameraMetadata_const_entry entry;
    ACameraMetadata_getConstEntry(meta, ACAMERA_SCALER_AVAILABLE_STREAM_CONFIGURATIONS, &entry);
    
    LOGI("Supported Resolutions for %s:", id);
    for (uint32_t i = 0; i < entry.count; i += 4) {
        int32_t fmt = entry.data.i32[i];
        int32_t width = entry.data.i32[i+1];
        int32_t height = entry.data.i32[i+2];
        int32_t isInput = entry.data.i32[i+3];

        if (!isInput) {
            LOGI(" - %dx%d (Fmt: %d)", width, height, fmt);
            // Naive logic: Pick 1080p if available, else keep last valid
            if (width == 1920 && height == 1080) {
                w = 1920; h = 1080;
            }
        }
    }
    ACameraMetadata_free(meta);
}

bool CameraSystem::startPreview(const Config& config) {
    TRACE_FUNC();
    if (mActiveCameraId.empty()) return false;

    // 1. Open Camera
    ACameraDevice_StateCallbacks devCb = { this, onDisconnected, onError };
    if (ACameraManager_openCamera(mManager, mActiveCameraId.c_str(), &devCb, &mDevice) != ACAMERA_OK) {
        LOGE("Failed to open camera");
        return false;
    }

    std::vector<ACaptureSessionOutput*> sessionOutputs;
    std::vector<ANativeWindow*> windows;

    // 2. Configure Display Output (With Native Window Scaling)
    if (config.displayWindow) {
        // SCALING LOGIC:
        // If the window size != camera resolution, we set the buffer geometry.
        // This forces the display scaler to handle the mismatch cleanly.
        ANativeWindow_setBuffersGeometry(config.displayWindow, mWidth, mHeight, AHARDWAREBUFFER_FORMAT_R8G8B8A8_UNORM);
        
        ACameraOutputTarget_create(config.displayWindow, &mDisplayTarget);
        ACaptureSessionOutput* out;
        ACaptureSessionOutput_create(config.displayWindow, &out);
        sessionOutputs.push_back(out);
        windows.push_back(config.displayWindow);
    }

    // 3. Configure Recorder Output (If needed)
    ANativeWindow* recWindow = nullptr;
    if (config.recordMode) {
        recWindow = mRecorder.start(config.recordPath, mWidth, mHeight);
        if (recWindow) {
            ACameraOutputTarget_create(recWindow, &mRecordTarget);
            ACaptureSessionOutput* out;
            ACaptureSessionOutput_create(recWindow, &out);
            sessionOutputs.push_back(out);
            windows.push_back(recWindow);
        }
    }

    // 4. Create Session
    ACaptureSessionOutputContainer* container;
    ACaptureSessionOutputContainer_create(&container);
    for (auto* out : sessionOutputs) ACaptureSessionOutputContainer_add(container, out);

    ACameraCaptureSession_StateCallbacks sessionCb = {this, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr, nullptr};
    ACameraDevice_createCaptureSession(mDevice, container, &sessionCb, &mSession);

    // 5. Create Request
    ACameraDevice_createCaptureRequest(mDevice, TEMPLATE_PREVIEW, &mRequest);
    if (mDisplayTarget) ACaptureRequest_addTarget(mRequest, mDisplayTarget);
    if (mRecordTarget) ACaptureRequest_addTarget(mRequest, mRecordTarget);

    // 6. Apply Test Pattern (If requested)
    if (config.enableTestPattern) {
        int32_t pattern = ACAMERA_SENSOR_TEST_PATTERN_MODE_COLOR_BARS;
        ACaptureRequest_setEntry_i32(mRequest, ACAMERA_SENSOR_TEST_PATTERN_MODE, 1, &pattern);
        LOGI("Test Pattern: ENABLED");
    }

    // 7. Start Streaming
    ACameraCaptureSession_setRepeatingRequest(mSession, nullptr, 1, &mRequest, nullptr);
    
    // Cleanup container wrappers (implementation omitted for brevity, usually manual free required for session outputs)
    return true;
}

void CameraSystem::stopPreview() {
    TRACE_FUNC();
    if (mSession) {
        ACameraCaptureSession_stopRepeating(mSession);
        ACameraCaptureSession_close(mSession);
        mSession = nullptr;
    }
    if (mDevice) {
        ACameraDevice_close(mDevice);
        mDevice = nullptr;
    }
    mRecorder.stop();
    if (mDisplayTarget) { ACameraOutputTarget_free(mDisplayTarget); mDisplayTarget = nullptr; }
    if (mRecordTarget) { ACameraOutputTarget_free(mRecordTarget); mRecordTarget = nullptr; }
}