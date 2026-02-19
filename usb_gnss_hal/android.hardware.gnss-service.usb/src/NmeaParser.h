#pragma once

#include <optional>
#include <string>

struct NmeaFix {
    double latDeg = 0.0;
    double lonDeg = 0.0;
    double altMeters = 0.0;
    double speedMps = 0.0;
    double bearingDeg = 0.0;
    bool valid = false;
};

class NmeaParser {
public:
    // Feed one full NMEA sentence (without \r\n). Returns a fix when enough data exists.
    // Accepts multi-GNSS talkers (GN/GP/GL/GA/GB/...) by matching message types (RMC/GGA).
    std::optional<NmeaFix> ConsumeSentence(const std::string& nmea);

    // NMEA checksum verification. If sentence has no '*hh' checksum, returns true.
    static bool VerifyChecksum(const std::string& nmea);

private:
    std::optional<NmeaFix> ParseRmc(const std::string& nmea);
    std::optional<NmeaFix> ParseGga(const std::string& nmea);

    // Latest known components
    std::optional<NmeaFix> lastFix_;
};
