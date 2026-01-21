#pragma once
#include <android/native_window.h>
#include <android/surface_control.h>

class DisplaySystem {
public:
    DisplaySystem();
    ~DisplaySystem();

    // Creates a full-screen surface on the default display
    ANativeWindow* createFullscreenWindow();
    void destroyWindow();
    void drawTestPattern();

private:
    ASurfaceControl* mSurfaceControl = nullptr;
    ASurfaceTransaction* mTransaction = nullptr;
    ANativeWindow* mNativeWindow = nullptr;
};