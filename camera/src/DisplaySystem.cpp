#include "DisplaySystem.h"
#include "Logger.h"
#include <android/native_window_jni.h>

DisplaySystem::DisplaySystem() {}

DisplaySystem::~DisplaySystem() {
    destroyWindow();
}

ANativeWindow* DisplaySystem::createFullscreenWindow() {
    TRACE_FUNC();

    // 1. Create a Surface Control on the default display
    // "RearViewCam" is the name visible in SurfaceFlinger/WinScope
    mSurfaceControl = ASurfaceControl_create(nullptr, "RearViewCam");
    
    if (!mSurfaceControl) {
        LOGE("Failed to create ASurfaceControl. Check permissions?");
        return nullptr;
    }

    // 2. Configure the Surface
    // We do not set a fixed W/H here to allow it to fill the parent/display bounds
    // but usually, for a root surface, you need explicit bounds if not parented.
    // For simplicity in a native tool, we often assume 1920x1080 or read display props.
    // However, ASurfaceControl allows us to acquire the window directly.
    
    // Set Z-Order to Top so it overlays the Launcher/Maps
    mTransaction = ASurfaceTransaction_create();
    ASurfaceTransaction_setZOrder(mTransaction, mSurfaceControl, 100000); 
    ASurfaceTransaction_setVisibility(mTransaction, mSurfaceControl, ASURFACE_TRANSACTION_VISIBILITY_SHOW);
    ASurfaceTransaction_apply(mTransaction);
    
    // 3. Get the Native Window (Surface)
    mNativeWindow = ASurfaceControl_acquireANativeWindow(mSurfaceControl);
    
    if (!mNativeWindow) {
        LOGE("Failed to acquire ANativeWindow from SurfaceControl");
        return nullptr;
    }

    LOGI("Successfully created SurfaceFlinger Surface");
    return mNativeWindow;
}

void DisplaySystem::destroyWindow() {
    TRACE_FUNC();
    if (mNativeWindow) {
        ANativeWindow_release(mNativeWindow);
        mNativeWindow = nullptr;
    }
    if (mTransaction) {
        ASurfaceTransaction_delete(mTransaction);
        mTransaction = nullptr;
    }
    if (mSurfaceControl) {
        ASurfaceControl_release(mSurfaceControl);
        mSurfaceControl = nullptr;
    }
}

void DisplaySystem::drawTestPattern() {
    TRACE_FUNC();
    if (!mNativeWindow) return;

    ANativeWindow_Buffer buffer;
    // Lock the window buffer for CPU writing
    if (ANativeWindow_lock(mNativeWindow, &buffer, nullptr) == 0) {
        LOGI("Drawing Software Test Pattern (1920x1080)");
        
        uint32_t* pixels = static_cast<uint32_t*>(buffer.bits);
        int width = buffer.width;
        int height = buffer.height;
        int stride = buffer.stride;

        // Draw basic color bars (Red, Green, Blue, White)
        for (int y = 0; y < height; ++y) {
            for (int x = 0; x < width; ++x) {
                uint32_t color = 0xFF000000; // Black
                if (x < width / 4) color = 0xFF0000FF;      // Red (ABGR)
                else if (x < width / 2) color = 0xFF00FF00; // Green
                else if (x < 3 * width / 4) color = 0xFFFF0000; // Blue
                else color = 0xFFFFFFFF; // White

                pixels[y * stride + x] = color;
            }
        }
        ANativeWindow_unlockAndPost(mNativeWindow);
    } else {
        LOGE("Failed to lock NativeWindow for SW drawing");
    }
}