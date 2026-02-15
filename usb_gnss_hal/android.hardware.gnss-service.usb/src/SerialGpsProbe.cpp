#include "SerialGpsProbe.h"

#include <android-base/logging.h>
#include <dirent.h>
#include <fcntl.h>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

#include <chrono>
#include <cstring>

#define LOG_TAG "GnssUsbHal"

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

static bool LooksLikeNmeaSentence(const std::string& line) {
    if (line.size() < 6 || line[0] != '$') return false;
    // common talkers: GP, GN, GL, GA, BD
    if (line.size() >= 3) {
        const std::string talker = line.substr(1, 2);
        if (talker != "GP" && talker != "GN" && talker != "GL" && talker != "GA" && talker != "BD") {
            // still allow unknown talkers, but require common sentence types below
        }
    }
    // require common sentence IDs
    if (line.find("GGA") == std::string::npos &&
        line.find("RMC") == std::string::npos &&
        line.find("GSA") == std::string::npos &&
        line.find("GSV") == std::string::npos) {
        return false;
    }
    // checksum presence "*HH"
    auto star = line.find('*');
    if (star == std::string::npos || star + 2 >= line.size()) return false;
    return true;
}

static bool VerifyNmeaChecksum(const std::string& line) {
    auto star = line.find('*');
    if (star == std::string::npos || star + 2 >= line.size()) return false;
    if (line[0] != '$') return false;

    uint8_t sum = 0;
    for (size_t i = 1; i < star; i++) sum ^= static_cast<uint8_t>(line[i]);

    auto hex = line.substr(star + 1, 2);
    auto toNibble = [](char c) -> int {
        if (c >= '0' && c <= '9') return c - '0';
        if (c >= 'A' && c <= 'F') return 10 + (c - 'A');
        if (c >= 'a' && c <= 'f') return 10 + (c - 'a');
        return -1;
    };
    int hi = toNibble(hex[0]);
    int lo = toNibble(hex[1]);
    if (hi < 0 || lo < 0) return false;
    uint8_t expected = static_cast<uint8_t>((hi << 4) | lo);
    return expected == sum;
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

static bool ProbePortAtBaud(const std::string& path, int baud, int probeSeconds) {
    int fd = open(path.c_str(), O_RDONLY | O_NOCTTY | O_NONBLOCK);
    if (fd < 0) return false;

    if (!ConfigureSerial(fd, baud)) {
        close(fd);
        return false;
    }

    std::string line;
    char buf[256];

    auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(probeSeconds);
    while (std::chrono::steady_clock::now() < deadline) {
        fd_set rfds;
        FD_ZERO(&rfds);
        FD_SET(fd, &rfds);

        timeval tv{};
        tv.tv_sec = 0;
        tv.tv_usec = 200 * 1000;  // 200ms

        int r = select(fd + 1, &rfds, nullptr, nullptr, &tv);
        if (r <= 0) continue;

        ssize_t n = read(fd, buf, sizeof(buf));
        if (n <= 0) continue;

        for (ssize_t i = 0; i < n; i++) {
            char c = buf[i];
            if (c == '\n') {
                if (LooksLikeNmeaSentence(line) && VerifyNmeaChecksum(line)) {
                    close(fd);
                    return true;
                }
                line.clear();
            } else if (c != '\r') {
                // cap line length to avoid garbage
                if (line.size() < 200) line.push_back(c);
            }
        }
    }

    close(fd);
    return false;
}

std::vector<std::string> SerialGpsProbe::ListCandidatePorts() {
    std::vector<std::string> out;
    DIR* dir = opendir("/dev");
    if (!dir) return out;

    dirent* ent;
    while ((ent = readdir(dir)) != nullptr) {
        if (
            strncmp(ent->d_name, "ttyUSB", 6) == 0 ||
            strncmp(ent->d_name, "ttyACM", 6) == 0 ||
            strncmp(ent->d_name, "ttyAML", 6) == 0
        ) {
            out.emplace_back(std::string("/dev/") + ent->d_name);
        }
    }
    closedir(dir);
    return out;
}

std::optional<GpsSerialDevice> SerialGpsProbe::FindFirstNmeaDevice(
        const std::vector<int>& baudCandidates, int probeSeconds) {
    auto ports = ListCandidatePorts();
    for (const auto& port : ports) {
        for (int baud : baudCandidates) {
            LOG(INFO) << "Probing " << port << " @ " << baud;
            if (ProbePortAtBaud(port, baud, probeSeconds)) {
                LOG(INFO) << "Selected GNSS serial device: " << port << " @ " << baud;
                return GpsSerialDevice{port, baud};
            }
        }
    }
    return std::nullopt;
}
