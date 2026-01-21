#pragma once
#include <string>
#include <media/NdkMediaCodec.h>
#include <media/NdkMediaMuxer.h>
#include <android/native_window.h>

class RecorderSystem {
public:
    RecorderSystem();
    ~RecorderSystem();

    // Setup recorder and return the Input Surface for Camera2
    ANativeWindow* start(const std::string& filePath, int width, int height);
    void stop();

private:
    void encoderThreadLoop();

    AMediaCodec* mCodec = nullptr;
    AMediaMuxer* mMuxer = nullptr;
    ANativeWindow* mInputSurface = nullptr;
    
    bool mIsRecording = false;
    std::thread mEncoderThread;
    int mTrackIndex = -1;
};