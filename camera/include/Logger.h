#pragma once
#include <android/log.h>
#include <string>

// Global log level control
extern int g_LogLevel; // 0=None, 1=Error, 2=Info, 3=Trace

#define LOG_TAG "RearViewCam"

#define LOGE(...) if(g_LogLevel >= 1) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)
#define LOGI(...) if(g_LogLevel >= 2) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGT(...) if(g_LogLevel >= 3) __android_log_print(ANDROID_LOG_VERBOSE, LOG_TAG, __VA_ARGS__)

class ScopedTrace {
    std::string mName;
public:
    ScopedTrace(const char* name) : mName(name) { LOGT("ENTER: %s", mName.c_str()); }
    ~ScopedTrace() { LOGT("EXIT: %s", mName.c_str()); }
};
#define TRACE_FUNC() ScopedTrace _t(__func__)