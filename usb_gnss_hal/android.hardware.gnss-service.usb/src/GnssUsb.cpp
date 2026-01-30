#include "GnssUsb.h"

#include <android-base/logging.h>
#include <aidl/android/hardware/gnss/GnssLocation.h>

#include <fcntl.h>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

#include <chrono>
#include <cstring>

#include "NmeaParser.h"
#include "SerialGpsProbe.h"
#include "GnssStubs.h"

#define LOG_TAG "GnssUsbHal"

namespace aidl::android::hardware::gnss::usb {

using ::aidl::android::hardware::gnss::GnssLocation;
using ::aidl::android::hardware::gnss::IGnssCallback;
using ndk::ScopedAStatus;

// ------------------------------------------------
// Time helpers
// ------------------------------------------------

static int64_t NowMillis() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(
        system_clock::now().time_since_epoch()).count();
}

// ------------------------------------------------
// Serial helpers
// ------------------------------------------------

static speed_t ToSpeed(int baud) {
    switch (baud) {
        case 4800: return B4800;
        case 9600: return B9600;
        case 19200: return B19200;
        case 38400: return B38400;
        case 57600: return B57600;
        case 115200: return B115200;
        default: return B9600;
    }
}

static bool ConfigureSerial(int fd, int baud) {
    termios tio{};
    if (tcgetattr(fd, &tio) != 0) return false;

    cfmakeraw(&tio);
    cfsetispeed(&tio, ToSpeed(baud));
    cfsetospeed(&tio, ToSpeed(baud));

    tio.c_cflag |= (CLOCAL | CREAD);
    tio.c_cflag &= ~CSTOPB;
    tio.c_cflag &= ~PARENB;
    tio.c_cflag &= ~CSIZE;
    tio.c_cflag |= CS8;

    tio.c_cc[VMIN] = 0;
    tio.c_cc[VTIME] = 0;

    if (tcsetattr(fd, TCSANOW, &tio) != 0) return false;
    tcflush(fd, TCIFLUSH);
    return true;
}

// ------------------------------------------------
// Constructor / Destructor
// ------------------------------------------------

GnssUsb::GnssUsb() {
    positionMode_.mode = IGnss::GnssPositionMode::STANDALONE;
    positionMode_.recurrence = IGnss::GnssPositionRecurrence::RECURRENCE_PERIODIC;
    positionMode_.minIntervalMs = 1000;
    positionMode_.preferredAccuracyMeters = 50;
    positionMode_.preferredTimeMs = 1000;
    positionMode_.lowPowerMode = false;

    // These extensions are supported via stubs 
    cfg_     = MakeStubGnssConfiguration();
    meas_    = MakeStubGnssMeasurement();
    power_   = MakeStubGnssPowerIndication();
    debug_   = MakeStubGnssDebug();
    antenna_ = MakeStubGnssAntennaInfo();
}

GnssUsb::~GnssUsb() {
    std::lock_guard<std::mutex> lk(mutex_);
    StopReaderLocked();
}

// ------------------------------------------------
// IGnss Core
// ------------------------------------------------

ScopedAStatus GnssUsb::setCallback(
    const std::shared_ptr<IGnssCallback>& callback) {

    std::lock_guard<std::mutex> lk(mutex_);
    callback_ = callback;

    if (callback_) {
        // Essential: Inform framework of what this HAL can do [cite: 1]
        callback_->gnssSetCapabilitiesCb(
            IGnssCallback::CAPABILITY_SCHEDULING |
            IGnssCallback::CAPABILITY_MEASUREMENTS
        );
    }

    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::close() {
    std::lock_guard<std::mutex> lk(mutex_);
    callback_.reset();
    StopReaderLocked();
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::start() {
    std::lock_guard<std::mutex> lk(mutex_);

    if (!callback_) {
        return ScopedAStatus::fromServiceSpecificError(IGnss::ERROR_INVALID_ARGUMENT);
    }

    if (running_) return ScopedAStatus::ok();

    const std::vector<int> baudCandidates = {9600, 115200, 38400, 57600, 4800};
    auto dev = SerialGpsProbe::FindFirstNmeaDevice(baudCandidates, 2);

    if (!dev) {
        LOG(ERROR) << "No GNSS serial device found";
        return ScopedAStatus::fromServiceSpecificError(IGnss::ERROR_GENERIC);
    }

    devicePath_ = dev->path;
    baudrate_   = dev->baudrate;

    serialFd_ = open(devicePath_.c_str(), O_RDONLY | O_NOCTTY | O_NONBLOCK);
    if (serialFd_ < 0) {
        PLOG(ERROR) << "open failed";
        return ScopedAStatus::fromServiceSpecificError(IGnss::ERROR_GENERIC);
    }

    if (!ConfigureSerial(serialFd_, baudrate_)) {
        LOG(ERROR) << "Serial configure failed";
        ::close(serialFd_);
        serialFd_ = -1;
        return ScopedAStatus::fromServiceSpecificError(IGnss::ERROR_GENERIC);
    }

    running_ = true;
    readerThread_ = std::thread(&GnssUsb::ReaderThreadMain, this);

    LOG(INFO) << "GNSS started " << devicePath_ << " @ " << baudrate_;
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::stop() {
    std::lock_guard<std::mutex> lk(mutex_);
    StopReaderLocked();
    return ScopedAStatus::ok();
}

void GnssUsb::StopReaderLocked() {
    if (!running_) return;
    running_ = false;
    if (serialFd_ >= 0) {
        ::close(serialFd_);
        serialFd_ = -1;
    }
    if (readerThread_.joinable())
        readerThread_.join();
}

// ------------------------------------------------
// Injection / Mode (USB ignores these)
// ------------------------------------------------

ScopedAStatus GnssUsb::injectTime(int64_t, int64_t, int32_t) { return ScopedAStatus::ok(); }
ScopedAStatus GnssUsb::injectLocation(const GnssLocation&) { return ScopedAStatus::ok(); }
ScopedAStatus GnssUsb::injectBestLocation(const GnssLocation&) { return ScopedAStatus::ok(); }
ScopedAStatus GnssUsb::deleteAidingData(IGnss::GnssAidingData) { return ScopedAStatus::ok(); }

ScopedAStatus GnssUsb::setPositionMode(const IGnss::PositionModeOptions& options) {
    std::lock_guard<std::mutex> lk(mutex_);
    positionMode_ = options;
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::startSvStatus() { return ScopedAStatus::ok(); }
ScopedAStatus GnssUsb::stopSvStatus()  { return ScopedAStatus::ok(); }
ScopedAStatus GnssUsb::startNmea() { nmeaEnabled_ = true; return ScopedAStatus::ok(); }
ScopedAStatus GnssUsb::stopNmea()  { nmeaEnabled_ = false; return ScopedAStatus::ok(); }

// ------------------------------------------------
// Extensions (The Critical Fixes) 
// ------------------------------------------------

ScopedAStatus GnssUsb::getExtensionPsds(std::shared_ptr<IGnssPsds>* r) {
    *r = nullptr;
    // CRITICAL: Returning an error stops the framework from calling methods on a null pointer 
    return ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ScopedAStatus GnssUsb::getExtensionGnssConfiguration(std::shared_ptr<IGnssConfiguration>* r) {
    *r = cfg_;
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::getExtensionGnssMeasurement(std::shared_ptr<IGnssMeasurementInterface>* r) {
    *r = meas_;
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::getExtensionGnssPowerIndication(std::shared_ptr<IGnssPowerIndication>* r) {
    *r = power_;
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::getExtensionGnssDebug(std::shared_ptr<IGnssDebug>* r) {
    *r = debug_;
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::getExtensionGnssAntennaInfo(std::shared_ptr<IGnssAntennaInfo>* r) {
    *r = antenna_;
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::getExtensionAGnss(std::shared_ptr<IAGnss>* r) {
    *r = nullptr;
    return ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ScopedAStatus GnssUsb::getExtensionAGnssRil(std::shared_ptr<IAGnssRil>* r) {
    *r = nullptr;
    return ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ScopedAStatus GnssUsb::getExtensionGnssVisibilityControl(
    std::shared_ptr<::aidl::android::hardware::gnss::visibility_control::IGnssVisibilityControl>* r) {
    *r = nullptr;
    return ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ScopedAStatus GnssUsb::getExtensionGnssBatching(std::shared_ptr<IGnssBatching>* r) {
    *r = nullptr;
    return ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ScopedAStatus GnssUsb::getExtensionGnssGeofence(std::shared_ptr<IGnssGeofence>* r) {
    *r = nullptr;
    return ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ScopedAStatus GnssUsb::getExtensionGnssNavigationMessage(std::shared_ptr<IGnssNavigationMessageInterface>* r) {
    *r = nullptr;
    return ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

ScopedAStatus GnssUsb::getExtensionMeasurementCorrections(
    std::shared_ptr<::aidl::android::hardware::gnss::measurement_corrections::IMeasurementCorrectionsInterface>* r) {
    *r = nullptr;
    return ScopedAStatus::fromExceptionCode(EX_UNSUPPORTED_OPERATION);
}

// ------------------------------------------------
// Reader thread
// ------------------------------------------------

void GnssUsb::ReaderThreadMain() {
    NmeaParser parser;
    std::string line;
    char buf[256];

    while (running_) {
        int fd = serialFd_;
        if (fd < 0) break;

        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(fd, &rfds);

        timeval tv{};
        tv.tv_usec = 200000;

        if (select(fd + 1, &rfds, nullptr, nullptr, &tv) <= 0)
            continue;

        ssize_t n = read(fd, buf, sizeof(buf));
        if (n <= 0) continue;

        for (ssize_t i = 0; i < n; i++) {
            char c = buf[i];
            if (c == '\n') {
                std::shared_ptr<IGnssCallback> cb;
                {
                    std::lock_guard<std::mutex> lk(mutex_);
                    cb = callback_;
                }

                if (cb && !line.empty()) {
                    if (nmeaEnabled_)
                        cb->gnssNmeaCb(NowMillis(), line);

                    auto fix = parser.ConsumeSentence(line);
                    if (fix && fix->valid) {
                        GnssLocation loc{};
                        loc.latitudeDegrees = fix->latDeg;
                        loc.longitudeDegrees = fix->lonDeg;
                        loc.altitudeMeters = fix->altMeters;
                        loc.speedMetersPerSec = fix->speedMps;
                        loc.bearingDegrees = fix->bearingDeg;
                        loc.horizontalAccuracyMeters = 50.0f;
                        loc.timestampMillis = NowMillis();
                        cb->gnssLocationCb(loc);
                    }
                }
                line.clear();
            } else if (c != '\r') {
                if (line.size() < 200)
                    line.push_back(c);
            }
        }
    }
}

} // namespace aidl::android::hardware::gnss::usb