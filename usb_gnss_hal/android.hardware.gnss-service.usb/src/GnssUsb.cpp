// Drop-in replacement for GnssUsb.cpp
//
// Goals:
//  - HARD-CODE UART GNSS: /dev/ttyAML6 @ 9600 (Amlogic)
//  - Robustly read/parse NMEA from UART and emit debug logs even without fixes
//  - Speed up TTFF using u-blox UBX (no paid AssistNow):
//      * UBX-MGA-INI-TIME_UTC
//      * UBX-MGA-INI-POS_LLH
//      * Receiver configuration best practices (NAV5 automotive, RATE 1Hz, GNSS constellations, SBAS)
//  - Provide UBX ACK/NAK + MON-VER logging to validate that injected/config messages are accepted.

#include "GnssUsb.h"

#include <android-base/logging.h>

#include <fcntl.h>
#include <termios.h>
#include <unistd.h>

#include <aidl/android/hardware/gnss/GnssLocation.h>

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <iomanip>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include "GnssStubs.h"
#include "NmeaParser.h"

#define LOG_TAG "GnssUsbHal"

namespace aidl::android::hardware::gnss::usb {

using ::aidl::android::hardware::gnss::GnssLocation;
using ::aidl::android::hardware::gnss::IGnssCallback;
using ndk::ScopedAStatus;

// -----------------------------------------------------------------------------
// Hardcoded device
// -----------------------------------------------------------------------------
static constexpr const char* kDevicePath = "/dev/ttyAML6";
static constexpr int kBaudrate = 9600;

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------
static int64_t NowMillis() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(system_clock::now().time_since_epoch()).count();
}

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

static bool ConfigureSerialRaw(int fd, int baud) {
    termios tio{};
    if (tcgetattr(fd, &tio) != 0) return false;

    // Raw mode. Do NOT translate CR/LF; do NOT echo.
    cfmakeraw(&tio);
    cfsetispeed(&tio, ToSpeed(baud));
    cfsetospeed(&tio, ToSpeed(baud));

    tio.c_cflag |= (CLOCAL | CREAD);
    tio.c_cflag &= ~CSTOPB;
    tio.c_cflag &= ~PARENB;
    tio.c_cflag &= ~CSIZE;
    tio.c_cflag |= CS8;

    // Non-blocking reads
    tio.c_cc[VMIN] = 0;
    tio.c_cc[VTIME] = 0;

    if (tcsetattr(fd, TCSANOW, &tio) != 0) return false;
    tcflush(fd, TCIOFLUSH);
    return true;
}

static bool WriteAll(int fd, const uint8_t* data, size_t len) {
    while (len > 0) {
        ssize_t n = ::write(fd, data, len);
        if (n < 0) {
            if (errno == EINTR) continue;
            return false;
        }
        data += static_cast<size_t>(n);
        len -= static_cast<size_t>(n);
    }
    return true;
}

static std::string HexPreview(const uint8_t* data, size_t len, size_t maxBytes = 16) {
    std::ostringstream oss;
    oss << std::hex << std::setfill('0');
    size_t n = std::min(len, maxBytes);
    for (size_t i = 0; i < n; i++) {
        oss << std::setw(2) << static_cast<int>(data[i]);
        if (i + 1 < n) oss << " ";
    }
    if (len > maxBytes) oss << " …";
    return oss.str();
}

// -----------------------------------------------------------------------------
// UBX builder/parsers
// -----------------------------------------------------------------------------

static void UbxChecksum(const uint8_t* data, size_t len, uint8_t* ckA, uint8_t* ckB) {
    uint8_t a = 0, b = 0;
    for (size_t i = 0; i < len; i++) {
        a = static_cast<uint8_t>(a + data[i]);
        b = static_cast<uint8_t>(b + a);
    }
    *ckA = a;
    *ckB = b;
}

static bool SendUbx(int fd, uint8_t cls, uint8_t id, const std::vector<uint8_t>& payload) {
    const uint16_t plen = static_cast<uint16_t>(payload.size());
    std::vector<uint8_t> frame;
    frame.reserve(8 + payload.size());
    frame.push_back(0xB5);
    frame.push_back(0x62);
    frame.push_back(cls);
    frame.push_back(id);
    frame.push_back(static_cast<uint8_t>(plen & 0xFF));
    frame.push_back(static_cast<uint8_t>((plen >> 8) & 0xFF));
    frame.insert(frame.end(), payload.begin(), payload.end());
    uint8_t ckA = 0, ckB = 0;
    UbxChecksum(&frame[2], 4 + payload.size(), &ckA, &ckB);
    frame.push_back(ckA);
    frame.push_back(ckB);
    return WriteAll(fd, frame.data(), frame.size());
}

static void SendMonVerPoll(int fd) {
    (void)SendUbx(fd, 0x0A, 0x04, {});
}

static void SendCfgRate(int fd, uint16_t measRateMs) {
    std::vector<uint8_t> p(6, 0);
    p[0] = static_cast<uint8_t>(measRateMs & 0xFF);
    p[1] = static_cast<uint8_t>((measRateMs >> 8) & 0xFF);
    p[2] = 0x01; p[3] = 0x00;   // navRate = 1
    p[4] = 0x00; p[5] = 0x00;   // timeRef = UTC
    (void)SendUbx(fd, 0x06, 0x08, p);
}

static void SendCfgNav5Automotive(int fd) {
    std::vector<uint8_t> p(36, 0);
    p[0] = 0x05; p[1] = 0x00;   // mask: dyn + fixMode
    p[2] = 0x04;               // dynModel: automotive
    p[3] = 0x02;               // fixMode: auto 2D/3D
    (void)SendUbx(fd, 0x06, 0x24, p);
}

static void SendCfgSbasEnable(int fd) {
    std::vector<uint8_t> p(8, 0);
    p[0] = 0x01; // enabled
    p[1] = 0x07; // ranging+correction+integrity
    (void)SendUbx(fd, 0x06, 0x16, p);
}

static void SendCfgGnssMulti(int fd) {
    // Best-effort UBX-CFG-GNSS. Some clones may NAK this.
    struct Block { uint8_t gnssId, resTrkCh, maxTrkCh, reserved1; uint32_t flags; };
    auto flagsEnable = [](bool en) {
        uint32_t f = 0;
        if (en) f |= 0x01;
        return f;
    };

    std::vector<Block> blocks;
    blocks.push_back({0, 8, 16, 0, flagsEnable(true)}); // GPS
    blocks.push_back({6, 8, 14, 0, flagsEnable(true)}); // GLONASS
    blocks.push_back({2, 4, 8,  0, flagsEnable(true)}); // Galileo
    blocks.push_back({3, 4, 8,  0, flagsEnable(true)}); // BeiDou
    blocks.push_back({1, 1, 3,  0, flagsEnable(true)}); // SBAS
    blocks.push_back({5, 1, 3,  0, flagsEnable(true)}); // QZSS

    std::vector<uint8_t> p;
    p.reserve(4 + blocks.size() * 8);
    p.push_back(0x00); // msgVer
    p.push_back(0x00); // numTrkChHw
    p.push_back(0x00); // numTrkChUse
    p.push_back(static_cast<uint8_t>(blocks.size()));

    for (const auto& b : blocks) {
        p.push_back(b.gnssId);
        p.push_back(b.resTrkCh);
        p.push_back(b.maxTrkCh);
        p.push_back(b.reserved1);
        p.push_back(static_cast<uint8_t>(b.flags & 0xFF));
        p.push_back(static_cast<uint8_t>((b.flags >> 8) & 0xFF));
        p.push_back(static_cast<uint8_t>((b.flags >> 16) & 0xFF));
        p.push_back(static_cast<uint8_t>((b.flags >> 24) & 0xFF));
    }

    (void)SendUbx(fd, 0x06, 0x3E, p);
}

static std::vector<uint8_t> BuildMgaIniTimeUtc(int64_t timeMs, int32_t uncertaintyMs) {
    std::time_t sec = static_cast<std::time_t>(timeMs / 1000);
    int64_t msRemainder = timeMs % 1000;
    if (msRemainder < 0) msRemainder += 1000;

    std::tm tmUtc{};
    gmtime_r(&sec, &tmUtc);

    const uint16_t year = static_cast<uint16_t>(tmUtc.tm_year + 1900);
    const uint8_t month = static_cast<uint8_t>(tmUtc.tm_mon + 1);
    const uint8_t day = static_cast<uint8_t>(tmUtc.tm_mday);
    const uint8_t hour = static_cast<uint8_t>(tmUtc.tm_hour);
    const uint8_t min = static_cast<uint8_t>(tmUtc.tm_min);
    const uint8_t s = static_cast<uint8_t>(tmUtc.tm_sec);

    if (uncertaintyMs < 0) uncertaintyMs = 0;
    uint32_t tAccNsTotal = static_cast<uint32_t>(uncertaintyMs) * 1000000u;
    uint16_t tAccS = static_cast<uint16_t>(tAccNsTotal / 1000000000u);
    uint32_t tAccNs = static_cast<uint32_t>(tAccNsTotal % 1000000000u);

    uint32_t ns = static_cast<uint32_t>(msRemainder) * 1000000u;

    std::vector<uint8_t> p(24, 0);
    p[0] = 0x10; // TIME_UTC
    p[1] = 0x00; // version
    p[2] = 0x00; // ref
    p[3] = 0x80; // leapSecs unknown
    p[4] = static_cast<uint8_t>(year & 0xFF);
    p[5] = static_cast<uint8_t>((year >> 8) & 0xFF);
    p[6] = month;
    p[7] = day;
    p[8] = hour;
    p[9] = min;
    p[10] = s;
    p[11] = 0x00;
    p[12] = static_cast<uint8_t>(ns & 0xFF);
    p[13] = static_cast<uint8_t>((ns >> 8) & 0xFF);
    p[14] = static_cast<uint8_t>((ns >> 16) & 0xFF);
    p[15] = static_cast<uint8_t>((ns >> 24) & 0xFF);
    p[16] = static_cast<uint8_t>(tAccS & 0xFF);
    p[17] = static_cast<uint8_t>((tAccS >> 8) & 0xFF);
    p[20] = static_cast<uint8_t>(tAccNs & 0xFF);
    p[21] = static_cast<uint8_t>((tAccNs >> 8) & 0xFF);
    p[22] = static_cast<uint8_t>((tAccNs >> 16) & 0xFF);
    p[23] = static_cast<uint8_t>((tAccNs >> 24) & 0xFF);
    return p;
}

static std::vector<uint8_t> BuildMgaIniPosLlh(const GnssLocation& loc) {
    auto clamp = [](double v, double lo, double hi) {
        return (v < lo) ? lo : (v > hi) ? hi : v;
    };
    double latD = clamp(loc.latitudeDegrees, -90.0, 90.0);
    double lonD = clamp(loc.longitudeDegrees, -180.0, 180.0);
    int32_t lat = static_cast<int32_t>(std::llround(latD * 1e7));
    int32_t lon = static_cast<int32_t>(std::llround(lonD * 1e7));
    int32_t altCm = static_cast<int32_t>(std::llround(static_cast<double>(loc.altitudeMeters) * 100.0));
    double accM = (loc.horizontalAccuracyMeters > 0.0f) ? loc.horizontalAccuracyMeters : 5000.0;
    uint32_t posAccCm = static_cast<uint32_t>(std::llround(accM * 100.0));

    std::vector<uint8_t> p(20, 0);
    p[0] = 0x01; // POS_LLH
    p[1] = 0x00;

    auto putI4LE = [&](size_t off, int32_t v) {
        uint32_t u = static_cast<uint32_t>(v);
        p[off + 0] = static_cast<uint8_t>(u & 0xFF);
        p[off + 1] = static_cast<uint8_t>((u >> 8) & 0xFF);
        p[off + 2] = static_cast<uint8_t>((u >> 16) & 0xFF);
        p[off + 3] = static_cast<uint8_t>((u >> 24) & 0xFF);
    };
    auto putU4LE = [&](size_t off, uint32_t u) {
        p[off + 0] = static_cast<uint8_t>(u & 0xFF);
        p[off + 1] = static_cast<uint8_t>((u >> 8) & 0xFF);
        p[off + 2] = static_cast<uint8_t>((u >> 16) & 0xFF);
        p[off + 3] = static_cast<uint8_t>((u >> 24) & 0xFF);
    };

    putI4LE(4, lat);
    putI4LE(8, lon);
    putI4LE(12, altCm);
    putU4LE(16, posAccCm);
    return p;
}

class UbxStreamParser {
public:
    void Feed(const uint8_t* data, size_t len) {
        for (size_t i = 0; i < len; i++) FeedByte(data[i]);
    }

private:
    enum class State { SYNC1, SYNC2, CLS, ID, LEN1, LEN2, PAYLOAD, CK_A, CK_B };
    State st_ = State::SYNC1;
    uint8_t cls_ = 0, id_ = 0;
    uint16_t len_ = 0;
    std::vector<uint8_t> payload_;
    uint8_t ckA_ = 0, ckB_ = 0;
    uint8_t calcA_ = 0, calcB_ = 0;

    void Reset() {
        st_ = State::SYNC1;
        payload_.clear();
        len_ = 0;
        calcA_ = calcB_ = 0;
    }

    void CkAcc(uint8_t b) {
        calcA_ = static_cast<uint8_t>(calcA_ + b);
        calcB_ = static_cast<uint8_t>(calcB_ + calcA_);
    }

    void Emit() {
        if (calcA_ != ckA_ || calcB_ != ckB_) {
            LOG(WARNING) << "UBX bad checksum cls=" << std::hex << static_cast<int>(cls_)
                         << " id=" << static_cast<int>(id_) << std::dec;
            return;
        }

        if (cls_ == 0x05 && (id_ == 0x01 || id_ == 0x00) && payload_.size() >= 2) {
            uint8_t ackedCls = payload_[0];
            uint8_t ackedId = payload_[1];
            if (id_ == 0x01) {
                LOG(INFO) << "UBX ACK for " << std::hex << static_cast<int>(ackedCls)
                          << ":" << static_cast<int>(ackedId) << std::dec;
            } else {
                LOG(WARNING) << "UBX NAK for " << std::hex << static_cast<int>(ackedCls)
                             << ":" << static_cast<int>(ackedId) << std::dec;
            }
            return;
        }

        if (cls_ == 0x0A && id_ == 0x04 && payload_.size() >= 40) {
            auto safeStr = [](const uint8_t* p, size_t n) {
                std::string s(reinterpret_cast<const char*>(p), n);
                auto z = s.find('\0');
                if (z != std::string::npos) s.resize(z);
                while (!s.empty() && s.back() == ' ') s.pop_back();
                return s;
            };
            std::string sw = safeStr(payload_.data(), 30);
            std::string hw = safeStr(payload_.data() + 30, 10);
            LOG(INFO) << "UBX MON-VER SW='" << sw << "' HW='" << hw << "'";
        }
    }

    void FeedByte(uint8_t b) {
        switch (st_) {
            case State::SYNC1:
                if (b == 0xB5) st_ = State::SYNC2;
                break;
            case State::SYNC2:
                if (b == 0x62) st_ = State::CLS;
                else Reset();
                break;
            case State::CLS:
                cls_ = b; calcA_ = calcB_ = 0; CkAcc(b); st_ = State::ID; break;
            case State::ID:
                id_ = b; CkAcc(b); st_ = State::LEN1; break;
            case State::LEN1:
                len_ = b; CkAcc(b); st_ = State::LEN2; break;
            case State::LEN2:
                len_ |= static_cast<uint16_t>(b) << 8; CkAcc(b);
                payload_.clear();
                payload_.reserve(len_);
                st_ = (len_ == 0) ? State::CK_A : State::PAYLOAD;
                break;
            case State::PAYLOAD:
                payload_.push_back(b);
                CkAcc(b);
                if (payload_.size() >= len_) st_ = State::CK_A;
                break;
            case State::CK_A:
                ckA_ = b; st_ = State::CK_B; break;
            case State::CK_B:
                ckB_ = b; Emit(); Reset(); break;
        }
    }
};

// -----------------------------------------------------------------------------
// GnssUsb
// -----------------------------------------------------------------------------

GnssUsb::GnssUsb() {
    positionMode_.mode = IGnss::GnssPositionMode::STANDALONE;
    positionMode_.recurrence = IGnss::GnssPositionRecurrence::RECURRENCE_PERIODIC;
    positionMode_.minIntervalMs = 1000;
    positionMode_.preferredAccuracyMeters = 50;
    positionMode_.preferredTimeMs = 1000;
    positionMode_.lowPowerMode = false;

    cfg_ = MakeStubGnssConfiguration();
    meas_ = MakeStubGnssMeasurement();
    power_ = MakeStubGnssPowerIndication();
    debug_ = MakeStubGnssDebug();
    antenna_ = MakeStubGnssAntennaInfo();
}

GnssUsb::~GnssUsb() {
    std::lock_guard<std::mutex> lk(mutex_);
    StopReaderLocked();
}

ScopedAStatus GnssUsb::setCallback(const std::shared_ptr<IGnssCallback>& callback) {
    std::lock_guard<std::mutex> lk(mutex_);
    callback_ = callback;
    if (callback_) {
        callback_->gnssSetCapabilitiesCb(
            IGnssCallback::CAPABILITY_SCHEDULING |
            IGnssCallback::CAPABILITY_MEASUREMENTS);
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

    devicePath_ = kDevicePath;
    baudrate_ = kBaudrate;

    serialFd_ = ::open(devicePath_.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
    if (serialFd_ < 0) {
        PLOG(ERROR) << "open failed for " << devicePath_;
        return ScopedAStatus::fromServiceSpecificError(IGnss::ERROR_GENERIC);
    }

    if (!ConfigureSerialRaw(serialFd_, baudrate_)) {
        LOG(ERROR) << "Serial configure failed for " << devicePath_;
        ::close(serialFd_);
        serialFd_ = -1;
        return ScopedAStatus::fromServiceSpecificError(IGnss::ERROR_GENERIC);
    }

    // Best-effort receiver configuration (ACK/NAK logged from UBX stream).
    SendMonVerPoll(serialFd_);
    SendCfgNav5Automotive(serialFd_);
    SendCfgRate(serialFd_, 1000);
    SendCfgSbasEnable(serialFd_);
    SendCfgGnssMulti(serialFd_);

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
    if (readerThread_.joinable()) readerThread_.join();
}

ScopedAStatus GnssUsb::injectTime(int64_t timeMs, int64_t /*timeReferenceMs*/, int32_t uncertaintyMs) {
    int fd;
    {
        std::lock_guard<std::mutex> lk(mutex_);
        fd = serialFd_;
    }
    if (fd < 0) return ScopedAStatus::ok();

    auto payload = BuildMgaIniTimeUtc(timeMs, uncertaintyMs);
    bool ok = SendUbx(fd, 0x13, 0x40, payload);
    LOG(INFO) << "injectTime: MGA-INI-TIME_UTC " << (ok ? "sent" : "FAILED")
              << " timeMs=" << timeMs << " uncMs=" << uncertaintyMs;
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::injectLocation(const GnssLocation& location) {
    int fd;
    std::shared_ptr<IGnssCallback> cb;
    {
        std::lock_guard<std::mutex> lk(mutex_);
        fd = serialFd_;
        cb = callback_;
    }

    if (fd >= 0) {
        auto payload = BuildMgaIniPosLlh(location);
        bool ok = SendUbx(fd, 0x13, 0x40, payload);
        LOG(INFO) << "injectLocation: MGA-INI-POS_LLH " << (ok ? "sent" : "FAILED")
                  << " lat=" << location.latitudeDegrees
                  << " lon=" << location.longitudeDegrees
                  << " acc=" << location.horizontalAccuracyMeters;
    }

    // Also forward into framework immediately.
    if (cb) {
        GnssLocation loc = location;
        if (loc.timestampMillis <= 0) loc.timestampMillis = NowMillis();
        if (loc.horizontalAccuracyMeters <= 0) loc.horizontalAccuracyMeters = 100.0f;
        cb->gnssLocationCb(loc);
    }

    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::injectBestLocation(const GnssLocation& location) {
    return injectLocation(location);
}

ScopedAStatus GnssUsb::deleteAidingData(IGnss::GnssAidingData) {
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::setPositionMode(const IGnss::PositionModeOptions& options) {
    std::lock_guard<std::mutex> lk(mutex_);
    positionMode_ = options;
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::startSvStatus() { return ScopedAStatus::ok(); }
ScopedAStatus GnssUsb::stopSvStatus() { return ScopedAStatus::ok(); }
ScopedAStatus GnssUsb::startNmea() { nmeaEnabled_ = true; return ScopedAStatus::ok(); }
ScopedAStatus GnssUsb::stopNmea() { nmeaEnabled_ = false; return ScopedAStatus::ok(); }

// Extensions
ScopedAStatus GnssUsb::getExtensionPsds(std::shared_ptr<IGnssPsds>* r) {
    *r = nullptr;
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

void GnssUsb::ReaderThreadMain() {
    NmeaParser nmea;
    UbxStreamParser ubx;
    std::string line;

    int64_t lastReadLogMs = 0;
    int64_t lastNmeaLogMs = 0;
    uint64_t totalBytes = 0;
    uint64_t totalLines = 0;
    uint64_t totalValidFixes = 0;

    uint8_t buf[512];

    while (running_) {
        int fd = serialFd_;
        if (fd < 0) break;

        ssize_t n = ::read(fd, buf, sizeof(buf));
        if (n <= 0) {
            ::usleep(10 * 1000);
            continue;
        }

        totalBytes += static_cast<uint64_t>(n);
        ubx.Feed(buf, static_cast<size_t>(n));

        int64_t now = NowMillis();
        if (now - lastReadLogMs > 5000) {
            lastReadLogMs = now;
            LOG(INFO) << "UART rx: bytes_total=" << totalBytes
                      << " lines_total=" << totalLines
                      << " validFixes=" << totalValidFixes
                      << " lastChunk=" << n
                      << " hex=" << HexPreview(buf, static_cast<size_t>(n));
        }

        for (ssize_t i = 0; i < n; i++) {
            char c = static_cast<char>(buf[i]);
            if (c == '\n') {
                totalLines++;

                if (!line.empty()) {
                    // Log a sample NMEA line once per second to validate UART parsing.
                    if (now - lastNmeaLogMs > 1000) {
                        lastNmeaLogMs = now;
                        bool ok = NmeaParser::VerifyChecksum(line);
                        LOG(INFO) << "NMEA(" << (ok ? "ck_ok" : "ck_bad") << "): " << line;
                    }

                    auto fix = nmea.ConsumeSentence(line);
                    if (fix && fix->valid) {
                        totalValidFixes++;
                        std::shared_ptr<IGnssCallback> cb;
                        {
                            std::lock_guard<std::mutex> lk(mutex_);
                            cb = callback_;
                        }
                        if (cb) {
                            GnssLocation loc{};
                            loc.latitudeDegrees = fix->latDeg;
                            loc.longitudeDegrees = fix->lonDeg;
                            loc.altitudeMeters = fix->altMeters;
                            loc.speedMetersPerSec = fix->speedMps;
                            loc.bearingDegrees = fix->bearingDeg;
                            loc.horizontalAccuracyMeters = 20.0f;
                            loc.timestampMillis = NowMillis();
                            cb->gnssLocationCb(loc);
                            LOG(INFO) << "GNSS FIX: lat=" << loc.latitudeDegrees
                                      << " lon=" << loc.longitudeDegrees
                                      << " alt=" << loc.altitudeMeters
                                      << " spd=" << loc.speedMetersPerSec
                                      << " brg=" << loc.bearingDegrees;
                        }
                    }
                }

                line.clear();
            } else if (c != '\r') {
                if (line.size() < 300) {
                    line.push_back(c);
                } else {
                    line.clear();
                }
            }
        }
    }
}

} // namespace aidl::android::hardware::gnss::usb
