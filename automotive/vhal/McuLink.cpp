#include "McuLink.h"

#include <android-base/logging.h>

#include <errno.h>
#include <fcntl.h>
#include <linux/hidraw.h>
#include <linux/input.h>
#include <poll.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <chrono>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

namespace {

constexpr int kMaxHidraw = 32;
constexpr int kHelloIntervalMs = 1000;
constexpr int kRescanIntervalMs = 1000;

uint32_t uptimeSeconds() {
    struct timespec ts {};
    clock_gettime(CLOCK_BOOTTIME, &ts);
    return static_cast<uint32_t>(ts.tv_sec);
}

// True when the report descriptor declares the vendor usage page 0xFF00
// (short item "Usage Page", 2 data bytes: 06 00 FF).
bool hasVendorUsagePage(int fd) {
    int size = 0;
    if (ioctl(fd, HIDIOCGRDESCSIZE, &size) < 0 || size <= 0) return false;
    struct hidraw_report_descriptor desc {};
    desc.size = static_cast<uint32_t>(size);
    if (ioctl(fd, HIDIOCGRDESC, &desc) < 0) return false;
    for (uint32_t i = 0; i + 2 < desc.size; i++) {
        if (desc.value[i] == 0x06 && desc.value[i + 1] == (MCU_HID_USAGE_PAGE & 0xFF) &&
            desc.value[i + 2] == (MCU_HID_USAGE_PAGE >> 8)) {
            return true;
        }
    }
    return false;
}

}  // namespace

McuLink::~McuLink() {
    stop();
}

int McuLink::findDevice(std::string* path) {
    for (int i = 0; i < kMaxHidraw; i++) {
        std::string p = "/dev/hidraw" + std::to_string(i);
        int fd = open(p.c_str(), O_RDWR | O_CLOEXEC | O_NONBLOCK);
        if (fd < 0) continue;
        struct hidraw_devinfo info {};
        if (ioctl(fd, HIDIOCGRAWINFO, &info) == 0 && info.bustype == BUS_USB &&
            static_cast<uint16_t>(info.vendor) == MCU_USB_VID &&
            static_cast<uint16_t>(info.product) == MCU_USB_PID && hasVendorUsagePage(fd)) {
            if (path) *path = p;
            return fd;
        }
        close(fd);
    }
    return -1;
}

void McuLink::start(PropsCallback onProps, InfoCallback onInfo, ConnectCallback onConnect) {
    mOnProps = std::move(onProps);
    mOnInfo = std::move(onInfo);
    mOnConnect = std::move(onConnect);
    mRunning = true;
    mThread = std::thread(&McuLink::loop, this);
}

void McuLink::stop() {
    mRunning = false;
    if (mThread.joinable()) mThread.join();
    int fd = mFd.exchange(-1);
    if (fd >= 0) close(fd);
}

std::string McuLink::devicePath() const {
    std::lock_guard<std::mutex> lk(mWriteMutex);
    return mPath;
}

bool McuLink::writeReport(const uint8_t* data, size_t len) {
    std::lock_guard<std::mutex> lk(mWriteMutex);
    int fd = mFd.load();
    if (fd < 0) return false;
    // hidraw: the first byte is the report ID, 0 for a device without numbered reports.
    uint8_t buf[MCU_REPORT_SIZE + 1] = {0};
    memcpy(buf + 1, data, len < MCU_REPORT_SIZE ? len : MCU_REPORT_SIZE);
    ssize_t n = write(fd, buf, sizeof(buf));
    if (n < 0) {
        LOG(WARNING) << "MCU write failed: " << strerror(errno);
        return false;
    }
    return true;
}

bool McuLink::sendHello() {
    mcu_hello_msg_t m{};
    m.type = MCU_MSG_HOST_HELLO;
    m.proto_version = MCU_PROTO_VERSION;
    m.host_uptime_s = uptimeSeconds();
    return writeReport(reinterpret_cast<const uint8_t*>(&m), sizeof(m));
}

bool McuLink::set(const std::vector<mcu_prop_t>& props) {
    if (!connected()) return false;
    size_t i = 0;
    bool ok = true;
    while (i < props.size()) {
        mcu_props_msg_t m{};
        m.type = MCU_MSG_HOST_SET;
        size_t n = std::min<size_t>(MCU_PROPS_PER_MSG, props.size() - i);
        for (size_t k = 0; k < n; k++) m.props[k] = props[i + k];
        m.count = static_cast<uint8_t>(n);
        ok &= writeReport(reinterpret_cast<const uint8_t*>(&m), sizeof(m));
        i += n;
    }
    return ok;
}

bool McuLink::requestSnapshot() {
    uint8_t type = MCU_MSG_HOST_SNAPSHOT;
    return writeReport(&type, 1);
}

bool McuLink::rebootToBootloader() {
    mcu_bootsel_msg_t m{};
    m.type = MCU_MSG_HOST_BOOTSEL;
    m.magic = MCU_BOOTSEL_MAGIC;
    return writeReport(reinterpret_cast<const uint8_t*>(&m), sizeof(m));
}

void McuLink::loop() {
    using Clock = std::chrono::steady_clock;
    auto lastHello = Clock::now() - std::chrono::seconds(10);
    bool loggedMissing = false;

    while (mRunning.load()) {
        if (mFd.load() < 0) {
            std::string path;
            int fd = findDevice(&path);
            if (fd < 0) {
                if (!loggedMissing) {
                    LOG(WARNING) << "MCU not found (USB " << std::hex << MCU_USB_VID << ":"
                                 << MCU_USB_PID << "), waiting for it";
                    loggedMissing = true;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(kRescanIntervalMs));
                continue;
            }
            {
                std::lock_guard<std::mutex> lk(mWriteMutex);
                mPath = path;
            }
            mFd = fd;
            loggedMissing = false;
            LOG(INFO) << "MCU connected on " << path;
            if (mOnConnect) mOnConnect(true);
            sendHello();  // the MCU answers with MCU_MSG_INFO and a full snapshot
            lastHello = Clock::now();
        }

        int fd = mFd.load();
        struct pollfd pfd = {fd, POLLIN, 0};
        int ret = poll(&pfd, 1, 200);
        bool lost = false;
        if (ret > 0 && (pfd.revents & (POLLERR | POLLHUP | POLLNVAL))) {
            lost = true;
        } else if (ret > 0 && (pfd.revents & POLLIN)) {
            uint8_t buf[MCU_REPORT_SIZE + 1];
            ssize_t n = read(fd, buf, sizeof(buf));
            if (n < 0 && errno != EAGAIN && errno != EINTR) {
                lost = true;
            } else if (n > 0) {
                switch (buf[0]) {
                    case MCU_MSG_PROPS: {
                        mcu_props_msg_t m{};
                        memcpy(&m, buf, std::min<size_t>(n, sizeof(m)));
                        std::vector<mcu_prop_t> props(
                                m.props, m.props + std::min<int>(m.count, MCU_PROPS_PER_MSG));
                        if (mOnProps) mOnProps(props, m.flags & MCU_PROPS_FLAG_SNAPSHOT);
                        break;
                    }
                    case MCU_MSG_INFO: {
                        mcu_info_msg_t info{};
                        memcpy(&info, buf, std::min<size_t>(n, sizeof(info)));
                        info.build[sizeof(info.build) - 1] = 0;
                        if (mOnInfo) mOnInfo(info);
                        break;
                    }
                    case MCU_MSG_LOG: {
                        mcu_log_msg_t m{};
                        memcpy(&m, buf, std::min<size_t>(n, sizeof(m)));
                        m.text[sizeof(m.text) - 1] = 0;
                        LOG(INFO) << "MCU: " << m.text;
                        break;
                    }
                    default:
                        break;
                }
            }
        }

        if (!lost && Clock::now() - lastHello >= std::chrono::milliseconds(kHelloIntervalMs)) {
            lost = !sendHello();
            lastHello = Clock::now();
        }

        if (lost) {
            LOG(WARNING) << "MCU link lost";
            {
                std::lock_guard<std::mutex> lk(mWriteMutex);
                int old = mFd.exchange(-1);
                if (old >= 0) close(old);
            }
            if (mOnConnect) mOnConnect(false);
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
        }
    }
}

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android
