#include "RecorderSystem.h"
#include "Logger.h"
#include <media/NdkMediaFormat.h>
#include <unistd.h>

RecorderSystem::RecorderSystem() {}

RecorderSystem::~RecorderSystem() {
    stop();
}

ANativeWindow* RecorderSystem::start(const std::string& filePath, int width, int height) {
    TRACE_FUNC();
    LOGI("Starting recording to: %s [%dx%d]", filePath.c_str(), width, height);

    // 1. Setup Muxer
    FILE* f = fopen(filePath.c_str(), "wb");
    if (!f) { LOGE("Failed to open file %s", filePath.c_str()); return nullptr; }
    mMuxer = AMediaMuxer_new(fileno(f), AMEDIAMUXER_OUTPUT_FORMAT_MPEG_4);

    // 2. Setup Encoder (H.264)
    mCodec = AMediaCodec_createEncoderByType("video/avc");
    AMediaFormat* format = AMediaFormat_new();
    AMediaFormat_setString(format, AMEDIAFORMAT_KEY_MIME, "video/avc");
    AMediaFormat_setInt32(format, AMEDIAFORMAT_KEY_WIDTH, width);
    AMediaFormat_setInt32(format, AMEDIAFORMAT_KEY_HEIGHT, height);
    AMediaFormat_setInt32(format, AMEDIAFORMAT_KEY_BIT_RATE, 8000000); // 8Mbps
    AMediaFormat_setInt32(format, AMEDIAFORMAT_KEY_FRAME_RATE, 30);
    AMediaFormat_setInt32(format, AMEDIAFORMAT_KEY_I_FRAME_INTERVAL, 1);
    AMediaFormat_setInt32(format, AMEDIAFORMAT_KEY_COLOR_FORMAT, 0x7F000789); // COLOR_FormatSurface

    media_status_t status = AMediaCodec_configure(mCodec, format, nullptr, nullptr, AMEDIACODEC_CONFIGURE_FLAG_ENCODE);
    AMediaFormat_delete(format);

    if (status != AMEDIA_OK) { LOGE("Codec configure failed"); return nullptr; }

    // 3. Get Surface
    AMediaCodec_createInputSurface(mCodec, &mInputSurface);
    AMediaCodec_start(mCodec);

    mIsRecording = true;
    mEncoderThread = std::thread(&RecorderSystem::encoderThreadLoop, this);

    return mInputSurface;
}

void RecorderSystem::stop() {
    TRACE_FUNC();
    if (!mIsRecording) return;
    mIsRecording = false;

    if (mEncoderThread.joinable()) mEncoderThread.join();

    if (mCodec) {
        AMediaCodec_stop(mCodec);
        AMediaCodec_delete(mCodec);
        mCodec = nullptr;
    }
    if (mMuxer) {
        AMediaMuxer_stop(mMuxer);
        AMediaMuxer_delete(mMuxer);
        mMuxer = nullptr;
    }
}

void RecorderSystem::encoderThreadLoop() {
    while (mIsRecording) {
        AMediaCodecBufferInfo info;
        ssize_t index = AMediaCodec_dequeueOutputBuffer(mCodec, &info, 10000); // 10ms timeout

        if (index >= 0) {
            size_t outSize;
            uint8_t* buffer = AMediaCodec_getOutputBuffer(mCodec, index, &outSize);
            
            if (info.flags & AMEDIACODEC_BUFFER_FLAG_CODEC_CONFIG) {
                // Config data, handled automatically by Muxer usually
            } else if (mTrackIndex >= 0) {
                AMediaMuxer_writeSampleData(mMuxer, mTrackIndex, buffer, &info);
            }
            AMediaCodec_releaseOutputBuffer(mCodec, index, false);
        } else if (index == AMEDIACODEC_INFO_OUTPUT_FORMAT_CHANGED) {
            AMediaFormat* newFormat = AMediaCodec_getOutputFormat(mCodec);
            mTrackIndex = AMediaMuxer_addTrack(mMuxer, newFormat);
            AMediaMuxer_start(mMuxer);
            LOGI("Muxer track started");
        }
    }
}