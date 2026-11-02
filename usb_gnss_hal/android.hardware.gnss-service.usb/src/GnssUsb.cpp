// GNSS HAL for a u-blox receiver on a serial port.
//
// Goals:
//  - u-blox on USB (CDC-ACM, /dev/ttyACM*; M9N on the car radio). persist.vendor.gnss.device or
//    ro.vendor.gnss.device override the port; /dev/ttyAML6 @ 9600 (old UART wiring) is the fallback.
//    The port disappears on USB resets and while the GNSS supply is off (VIM3 asleep): reopen it.
//  - Fixes from UBX-NAV-PVT (real accuracies), satellites from UBX-NAV-SAT, enabled on the USB port
//    only (UART1 also feeds the peripheral board MCU at 9600 baud). NMEA RMC/GGA is the fallback.
//  - Robustly read/parse NMEA and emit debug logs even without fixes
//  - Speed up TTFF using u-blox UBX (no paid AssistNow):
//      * UBX-MGA-INI-TIME_UTC
//      * UBX-MGA-INI-POS_LLH
//      * Receiver configuration best practices (NAV5 automotive, RATE 1Hz, GNSS constellations, SBAS)
//  - Provide UBX ACK/NAK + MON-VER logging to validate that injected/config messages are accepted.

#include "GnssUsb.h"

#include <android-base/logging.h>

#include <android-base/properties.h>
#include <dirent.h>
#include <fcntl.h>
#include <poll.h>
#include <termios.h>
#include <unistd.h>
#include <utils/SystemClock.h>

#include <aidl/android/hardware/gnss/ElapsedRealtime.h>
#include <aidl/android/hardware/gnss/GnssConstellationType.h>
#include <aidl/android/hardware/gnss/GnssLocation.h>

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <ctime>
#include <functional>
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

using ::aidl::android::hardware::gnss::ElapsedRealtime;
using ::aidl::android::hardware::gnss::GnssConstellationType;
using ::aidl::android::hardware::gnss::GnssLocation;
using ::aidl::android::hardware::gnss::IGnssCallback;
using ndk::ScopedAStatus;

// -----------------------------------------------------------------------------
// Device
// -----------------------------------------------------------------------------
static constexpr const char* kUartFallback = "/dev/ttyAML6";
static constexpr int kBaudrate = 9600;  // UART only; CDC-ACM ignores it
static constexpr int kReopenIntervalMs = 1000;
static constexpr int64_t kPvtStaleMs = 3000;

// The serial port to use: the property override, else the first /dev/ttyACM* (the peripheral board
// has no CDC interface of its own, so on this car radio that is the u-blox), else the UART.
static std::string FindGnssPort() {
    std::string forced = ::android::base::GetProperty("persist.vendor.gnss.device", "");
    if (forced.empty()) forced = ::android::base::GetProperty("ro.vendor.gnss.device", "");
    if (!forced.empty()) return forced;

    std::string best;
    if (DIR* dir = opendir("/dev")) {
        while (dirent* ent = readdir(dir)) {
            std::string name = ent->d_name;
            if (name.rfind("ttyACM", 0) == 0 && (best.empty() || name < best)) best = name;
        }
        closedir(dir);
    }
    return best.empty() ? kUartFallback : "/dev/" + best;
}

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

// UBX-CFG-VALSET in the RAM layer (M9/M10 configuration interface; older receivers NAK it).
// Turns on NAV-PVT and NAV-SAT on the USB port and sets the automotive dynamic model.
static void SendValsetUsbPvtSat(int fd) {
    std::vector<uint8_t> p = {0x00, 0x01, 0x00, 0x00};  // version 0, layer RAM
    auto key1 = [&](uint32_t key, uint8_t value) {
        for (int i = 0; i < 4; i++) p.push_back(static_cast<uint8_t>(key >> (8 * i)));
        p.push_back(value);
    };
    key1(0x20910009, 1);  // CFG-MSGOUT-UBX_NAV_PVT_USB
    key1(0x20910018, 1);  // CFG-MSGOUT-UBX_NAV_SAT_USB
    key1(0x20110021, 4);  // CFG-NAVSPG-DYNMODEL = automotive
    (void)SendUbx(fd, 0x06, 0x8A, p);
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
    // Called for every UBX message with a good checksum.
    std::function<void(uint8_t cls, uint8_t id, const std::vector<uint8_t>& payload)> onMessage;

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
        if (onMessage) onMessage(cls_, id_, payload_);

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
    StopReader();
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
    {
        std::lock_guard<std::mutex> lk(mutex_);
        callback_.reset();
    }
    StopReader();
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::start() {
    std::lock_guard<std::mutex> lk(mutex_);

    if (!callback_) {
        return ScopedAStatus::fromServiceSpecificError(IGnss::ERROR_INVALID_ARGUMENT);
    }
    if (running_) return ScopedAStatus::ok();

    // A missing receiver is not an error: the reader thread keeps looking for it.
    OpenPortLocked(/*logFailure=*/true);

    running_ = true;
    readerThread_ = std::thread(&GnssUsb::ReaderThreadMain, this);
    return ScopedAStatus::ok();
}

ScopedAStatus GnssUsb::stop() {
    StopReader();
    return ScopedAStatus::ok();
}

bool GnssUsb::OpenPortLocked(bool logFailure) {
    const std::string path = FindGnssPort();
    int fd = ::open(path.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) {
        if (logFailure) PLOG(ERROR) << "open failed for " << path << ", waiting for the receiver";
        return false;
    }
    if (!ConfigureSerialRaw(fd, kBaudrate)) {
        LOG(ERROR) << "Serial configure failed for " << path;
        ::close(fd);
        return false;
    }

    // Best-effort receiver configuration (ACK/NAK logged from UBX stream). The receiver loses RAM
    // settings when its supply is switched, so this runs on every (re)open.
    SendMonVerPoll(fd);
    SendCfgNav5Automotive(fd);
    SendCfgRate(fd, 1000);
    SendCfgSbasEnable(fd);
    SendCfgGnssMulti(fd);
    SendValsetUsbPvtSat(fd);

    serialFd_ = fd;
    devicePath_ = path;
    baudrate_ = kBaudrate;
    LOG(INFO) << "GNSS port " << path << " open";
    return true;
}

void GnssUsb::ClosePortLocked() {
    if (serialFd_ >= 0) {
        ::close(serialFd_);
        serialFd_ = -1;
    }
}

// Not under mutex_ while joining: the reader thread takes it to reopen the port and to fetch the
// callback.
void GnssUsb::StopReader() {
    std::thread reader;
    {
        std::lock_guard<std::mutex> lk(mutex_);
        running_ = false;
        reader = std::move(readerThread_);
    }
    if (reader.joinable()) reader.join();
    std::lock_guard<std::mutex> lk(mutex_);
    ClosePortLocked();
}

std::shared_ptr<IGnssCallback> GnssUsb::Callback() {
    std::lock_guard<std::mutex> lk(mutex_);
    return callback_;
}

void GnssUsb::PublishLocation(const GnssLocation& location) {
    if (auto cb = Callback()) cb->gnssLocationCb(location);
}

static int32_t I4(const std::vector<uint8_t>& p, size_t off) {
    return static_cast<int32_t>(p[off] | (p[off + 1] << 8) | (p[off + 2] << 16) |
                                (static_cast<uint32_t>(p[off + 3]) << 24));
}
static uint32_t U4(const std::vector<uint8_t>& p, size_t off) { return static_cast<uint32_t>(I4(p, off)); }
static int16_t I2(const std::vector<uint8_t>& p, size_t off) {
    return static_cast<int16_t>(p[off] | (p[off + 1] << 8));
}

void GnssUsb::HandleUbx(uint8_t cls, uint8_t id, const std::vector<uint8_t>& p) {
    if (cls == 0x01 && id == 0x07 && p.size() >= 92) {  // NAV-PVT
        lastPvtMs_ = NowMillis();
        const uint8_t valid = p[11];
        const uint8_t fixType = p[20];
        const bool gnssFixOk = p[21] & 0x01;
        const uint8_t numSv = p[23];
        if (!gnssFixOk || fixType < 2 || fixType > 4) return;  // no fix / dead reckoning only / time only

        GnssLocation loc{};
        loc.longitudeDegrees = I4(p, 24) * 1e-7;
        loc.latitudeDegrees = I4(p, 28) * 1e-7;
        loc.altitudeMeters = I4(p, 36) / 1000.0;  // above mean sea level
        loc.horizontalAccuracyMeters = U4(p, 40) / 1000.0;
        loc.verticalAccuracyMeters = U4(p, 44) / 1000.0;
        loc.speedMetersPerSec = I4(p, 60) / 1000.0;
        loc.speedAccuracyMetersPerSecond = U4(p, 68) / 1000.0;
        loc.bearingDegrees = I4(p, 64) * 1e-5;
        loc.bearingAccuracyDegrees = U4(p, 72) * 1e-5;
        loc.gnssLocationFlags = GnssLocation::HAS_LAT_LONG | GnssLocation::HAS_HORIZONTAL_ACCURACY |
                                GnssLocation::HAS_SPEED | GnssLocation::HAS_SPEED_ACCURACY;
        if (fixType != 2) {
            loc.gnssLocationFlags |= GnssLocation::HAS_ALTITUDE | GnssLocation::HAS_VERTICAL_ACCURACY;
        }
        // Heading of motion is only meaningful while moving.
        if (loc.speedMetersPerSec > 0.5) {
            loc.gnssLocationFlags |= GnssLocation::HAS_BEARING | GnssLocation::HAS_BEARING_ACCURACY;
        }

        // UTC from the receiver when date and time are valid and fully resolved.
        if ((valid & 0x07) == 0x07) {
            std::tm t{};
            t.tm_year = (p[4] | (p[5] << 8)) - 1900;
            t.tm_mon = p[6] - 1;
            t.tm_mday = p[7];
            t.tm_hour = p[8];
            t.tm_min = p[9];
            t.tm_sec = p[10];
            loc.timestampMillis = static_cast<int64_t>(timegm(&t)) * 1000 + I4(p, 16) / 1000000;
        } else {
            loc.timestampMillis = NowMillis();
        }
        loc.elapsedRealtime.flags = ElapsedRealtime::HAS_TIMESTAMP_NS;
        loc.elapsedRealtime.timestampNs = ::android::elapsedRealtimeNano();

        PublishLocation(loc);

        static int64_t lastLogMs = 0;
        if (lastPvtMs_ - lastLogMs > 10000) {
            lastLogMs = lastPvtMs_;
            LOG(INFO) << "NAV-PVT fix " << int(fixType) << "D, " << int(numSv) << " SV, lat="
                      << loc.latitudeDegrees << " lon=" << loc.longitudeDegrees
                      << " hAcc=" << loc.horizontalAccuracyMeters << " m";
        }
        return;
    }

    if (cls == 0x01 && id == 0x35 && p.size() >= 8) {  // NAV-SAT
        auto cb = Callback();
        if (!cb) return;
        const size_t numSvs = p[5];
        std::vector<IGnssCallback::GnssSvInfo> svs;
        for (size_t i = 0; i < numSvs && 8 + 12 * (i + 1) <= p.size(); i++) {
            const size_t o = 8 + 12 * i;
            const uint8_t gnssId = p[o];
            int svid = p[o + 1];
            const uint32_t flags = U4(p, o + 8);
            IGnssCallback::GnssSvInfo sv{};
            switch (gnssId) {
                case 0: sv.constellation = GnssConstellationType::GPS;
                        sv.carrierFrequencyHz = 1575420000; break;
                case 1: sv.constellation = GnssConstellationType::SBAS;
                        sv.carrierFrequencyHz = 1575420000; break;
                case 2: sv.constellation = GnssConstellationType::GALILEO;
                        sv.carrierFrequencyHz = 1575420000; break;
                case 3: sv.constellation = GnssConstellationType::BEIDOU;
                        sv.carrierFrequencyHz = 1561098000; break;
                case 5: sv.constellation = GnssConstellationType::QZSS;
                        sv.carrierFrequencyHz = 1575420000;
                        svid += 192; break;  // Android numbers QZSS 193-200
                case 6: sv.constellation = GnssConstellationType::GLONASS;
                        sv.carrierFrequencyHz = 1602000000; break;
                default: continue;
            }
            sv.svid = svid;
            sv.cN0Dbhz = p[o + 2];
            sv.basebandCN0DbHz = p[o + 2];
            sv.elevationDegrees = static_cast<int8_t>(p[o + 3]);
            sv.azimuthDegrees = I2(p, o + 4);
            sv.svFlag = static_cast<int>(IGnssCallback::GnssSvFlags::HAS_CARRIER_FREQUENCY);
            if (flags & (1u << 3)) sv.svFlag |= static_cast<int>(IGnssCallback::GnssSvFlags::USED_IN_FIX);
            if (flags & (1u << 11)) sv.svFlag |= static_cast<int>(IGnssCallback::GnssSvFlags::HAS_EPHEMERIS_DATA);
            if (flags & (1u << 12)) sv.svFlag |= static_cast<int>(IGnssCallback::GnssSvFlags::HAS_ALMANAC_DATA);
            svs.push_back(sv);
        }
        cb->gnssSvStatusCb(svs);

        static int64_t lastSatLogMs = 0;
        const int64_t now = NowMillis();
        if (now - lastSatLogMs > 10000) {
            lastSatLogMs = now;
            int used = 0, tracked = 0;
            float best = 0;
            for (const auto& sv : svs) {
                if (sv.cN0Dbhz > 0) tracked++;
                if (sv.svFlag & static_cast<int>(IGnssCallback::GnssSvFlags::USED_IN_FIX)) used++;
                best = std::max(best, sv.cN0Dbhz);
            }
            LOG(INFO) << "NAV-SAT " << svs.size() << " SV known, " << tracked << " tracked, " << used
                      << " used, best C/N0 " << best << " dBHz";
        }
    }
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
    ubx.onMessage = [this](uint8_t cls, uint8_t id, const std::vector<uint8_t>& p) {
        HandleUbx(cls, id, p);
    };
    int64_t nextOpenMs = 0;

    while (running_) {
        int fd;
        {
            std::lock_guard<std::mutex> lk(mutex_);
            fd = serialFd_;
        }
        if (fd < 0) {
            if (NowMillis() < nextOpenMs) {
                ::usleep(100 * 1000);
                continue;
            }
            std::lock_guard<std::mutex> lk(mutex_);
            if (!running_) break;
            if (!OpenPortLocked(/*logFailure=*/false)) nextOpenMs = NowMillis() + kReopenIntervalMs;
            line.clear();
            continue;
        }

        struct pollfd pfd = {fd, POLLIN, 0};
        int ret = ::poll(&pfd, 1, 500);  // 500 ms so stop() is noticed
        if (ret <= 0) continue;
        bool lost = pfd.revents & (POLLERR | POLLHUP | POLLNVAL);
        ssize_t n = 0;
        if (!lost) {
            n = ::read(fd, buf, sizeof(buf));
            // POLLIN with nothing to read is a hangup on a tty.
            if (n == 0 || (n < 0 && errno != EAGAIN && errno != EINTR)) lost = true;
        }
        if (lost) {
            LOG(WARNING) << "GNSS port gone (revents=" << pfd.revents << "), reopening";
            std::lock_guard<std::mutex> lk(mutex_);
            ClosePortLocked();
            nextOpenMs = NowMillis() + kReopenIntervalMs;
            continue;
        }
        if (n <= 0) continue;

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

                if (!line.empty() && line[0] == '$') {
                    // Log a sample NMEA line once per second to validate UART parsing.
                    if (now - lastNmeaLogMs > 1000) {
                        lastNmeaLogMs = now;
                        bool ok = NmeaParser::VerifyChecksum(line);
                        LOG(INFO) << "NMEA(" << (ok ? "ck_ok" : "ck_bad") << "): " << line;
                    }

                    if (nmeaEnabled_ && line[0] == '$') {
                        if (auto cb = Callback()) cb->gnssNmeaCb(now, line);
                    }

                    auto fix = nmea.ConsumeSentence(line);
                    if (fix && fix->valid) {
                        totalValidFixes++;
                        std::shared_ptr<IGnssCallback> cb = Callback();
                        // NAV-PVT carries the same fix with real accuracies.
                        if (now - lastPvtMs_ < kPvtStaleMs) cb.reset();
                        if (cb) {
                            GnssLocation loc{};
                            loc.gnssLocationFlags = GnssLocation::HAS_LAT_LONG |
                                    GnssLocation::HAS_ALTITUDE | GnssLocation::HAS_SPEED |
                                    GnssLocation::HAS_BEARING | GnssLocation::HAS_HORIZONTAL_ACCURACY;
                            loc.elapsedRealtime.flags = ElapsedRealtime::HAS_TIMESTAMP_NS;
                            loc.elapsedRealtime.timestampNs = ::android::elapsedRealtimeNano();
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
            } else if (c == '$') {
                // NMEA sentences start at '$'; anything before it is UBX binary sharing the stream.
                line.assign(1, c);
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
