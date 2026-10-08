// USB HID link to the peripheral board MCU (RP2350B). See mcu/protocol/mcu_protocol.h.
//
// Finds the MCU's vendor HID interface among /dev/hidraw*, keeps it open, sends the
// heartbeat and hands every received property update to a callback. The device goes
// away and comes back whenever the VIM3 suspends or the MCU restarts; the link reconnects
// on its own and the MCU answers each (re)connect with a full snapshot.
#pragma once

#include <mcu_protocol.h>

#include <atomic>
#include <functional>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace android {
namespace hardware {
namespace automotive {
namespace vehicle {

class McuLink {
  public:
    using PropsCallback = std::function<void(const std::vector<mcu_prop_t>& props, bool snapshot)>;
    using InfoCallback = std::function<void(const mcu_info_msg_t& info)>;
    using ConnectCallback = std::function<void(bool connected)>;

    McuLink() = default;
    ~McuLink();

    void start(PropsCallback onProps, InfoCallback onInfo, ConnectCallback onConnect);
    void stop();

    bool connected() const { return mFd.load() >= 0; }

    // Send property writes. Returns false when the MCU is not connected.
    bool set(const std::vector<mcu_prop_t>& props);
    bool set(uint32_t prop, int32_t v0, int32_t v1 = 0) { return set({{prop, v0, v1}}); }
    bool requestSnapshot();
    bool rebootToBootloader();

    std::string devicePath() const;

    // Scan /dev/hidraw* for the MCU's vendor interface. Returns an open O_RDWR fd or -1.
    static int findDevice(std::string* path);

  private:
    void loop();
    bool writeReport(const uint8_t* data, size_t len);
    bool sendHello();

    PropsCallback mOnProps;
    InfoCallback mOnInfo;
    ConnectCallback mOnConnect;
    std::atomic<bool> mRunning{false};
    std::atomic<int> mFd{-1};
    std::thread mThread;
    mutable std::mutex mWriteMutex;
    std::string mPath;
};

}  // namespace vehicle
}  // namespace automotive
}  // namespace hardware
}  // namespace android
