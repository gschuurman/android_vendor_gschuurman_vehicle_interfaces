#include <iostream>
#include <thread>
#include <vector>
#include <cstring>
#include "Logger.h"
#include "CameraSystem.h"
#include "GearListener.h"

// Initialize global log level
int g_LogLevel = 2; // Default INFO

struct Arguments {
    bool testCamera = false;
    bool testDisplay = false;
    std::string recordPath;
};

Arguments parseArgs(int argc, char** argv) {
    Arguments args;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--test-camera") == 0) args.testCamera = true;
        if (strcmp(argv[i], "--test-display") == 0) args.testDisplay = true;
        if (strcmp(argv[i], "--trace") == 0) g_LogLevel = 3;
        if (strcmp(argv[i], "--record-to") == 0 && i + 1 < argc) {
            args.recordPath = argv[++i];
        }
    }
    return args;
}

int main(int argc, char** argv) {
    Arguments args = parseArgs(argc, argv);
    
    LOGI("=== Rear Camera Service Started ===");

    DisplaySystem displaySys;
    CameraSystem camSys;

    // 1. Try Initialize Camera, but DO NOT EXIT if it fails.
    bool cameraAvailable = camSys.initialize();
    if (!cameraAvailable) {
        LOGE("WARNING: No physical camera found. Camera features will be disabled.");
    }

    // Define the sequence to start the "View"
    auto startSequence = [&](bool recordOnly) {
        // A. Setup Display
        ANativeWindow* window = nullptr;
        if (!recordOnly) {
            window = displaySys.createFullscreenWindow();
            if (!window) {
                LOGE("Critical: Failed to create Display Surface.");
                return;
            }
        }

        // B. Decide Source (Camera vs Software Fallback)
        if (cameraAvailable) {
            CameraSystem::Config cfg;
            cfg.displayWindow = window;
            cfg.recordMode = !args.recordPath.empty();
            cfg.recordPath = args.recordPath;
            cfg.enableTestPattern = args.testDisplay; // Use ISP Test Pattern

            if (!camSys.startPreview(cfg)) {
                LOGE("Camera failed to start preview.");
            }
        } else {
            // C. Camera Missing Logic
            if (args.testDisplay && window) {
                LOGI("Camera missing. Using Software Test Pattern for Display Test.");
                // Draw a static pattern once (or loop if animation needed)
                displaySys.drawTestPattern();
            } else if (!recordOnly) {
                 LOGE("No Camera and not in Test Mode. Screen will be black.");
            }
        }
    };

    auto stopSequence = [&]() {
        if (cameraAvailable) {
            camSys.stopPreview();
        }
        displaySys.destroyWindow();
    };

    // --- EXECUTION MODES ---

    // Mode 1: CLI Camera Test (Requires Camera)
    if (args.testCamera) {
        if (!cameraAvailable) {
            LOGE("Cannot run Camera Test: No Camera Connected.");
            return 1;
        }
        LOGI("Running CLI Camera Test...");
        startSequence(false); // Using false to ensure window logic checks out (or pass true if headless)
        std::this_thread::sleep_for(std::chrono::seconds(5));
        stopSequence();
        return 0;
    }

    // Mode 2: CLI Display Test (Works with OR without Camera)
    if (args.testDisplay && args.recordPath.empty()) {
        LOGI("Running Display Test...");
        startSequence(false);
        // Keep display alive for 10s for visual inspection
        std::this_thread::sleep_for(std::chrono::seconds(10));
        stopSequence();
        return 0;
    }

    // Mode 3: Service Mode (Gear Listener)
    GearListener gear([&](bool isReverse) {
        if (isReverse) {
            LOGI("Gear R -> Start");
            startSequence(false);
        } else {
            LOGI("Gear D -> Stop");
            stopSequence();
        }
    });

    gear.start();

    // Keep service alive
    while(true) std::this_thread::sleep_for(std::chrono::seconds(1));

    return 0;
}