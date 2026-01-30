#pragma once
#include <optional>
#include <string>
#include <vector>

struct GpsSerialDevice {
    std::string path;
    int baudrate;
};

class SerialGpsProbe {
public:
    // Scan /dev/ttyUSB* and /dev/ttyACM* and try baud candidates.
    // Returns first device that produces valid NMEA within timeout.
    static std::optional<GpsSerialDevice> FindFirstNmeaDevice(
        const std::vector<int>& baudCandidates,
        int probeSeconds = 2);

    static std::vector<std::string> ListCandidatePorts();
};
