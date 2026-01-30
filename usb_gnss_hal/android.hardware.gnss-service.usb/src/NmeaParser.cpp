#include "NmeaParser.h"

#include <cstdlib>
#include <cmath>
#include <string>
#include <vector>

static std::vector<std::string> Split(const std::string& s, char delim) {
    std::vector<std::string> out;
    std::string cur;
    for (char c : s) {
        if (c == delim) {
            out.push_back(cur);
            cur.clear();
        } else {
            cur.push_back(c);
        }
    }
    out.push_back(cur);
    return out;
}

static bool ParseDoubleSafe(const std::string& s, double* out) {
    if (s.empty()) return false;

    char* end = nullptr;
    double v = strtod(s.c_str(), &end);

    if (end == s.c_str()) return false;
    *out = v;
    return true;
}

static int HexNibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return 10 + (c - 'A');
    if (c >= 'a' && c <= 'f') return 10 + (c - 'a');
    return -1;
}

bool NmeaParser::VerifyChecksum(const std::string& nmea) {
    auto star = nmea.find('*');
    if (star == std::string::npos || star + 2 >= nmea.size()) return false;
    if (nmea.empty() || nmea[0] != '$') return false;

    uint8_t sum = 0;
    for (size_t i = 1; i < star; i++)
        sum ^= static_cast<uint8_t>(nmea[i]);

    int hi = HexNibble(nmea[star + 1]);
    int lo = HexNibble(nmea[star + 2]);
    if (hi < 0 || lo < 0) return false;

    uint8_t expected = (hi << 4) | lo;
    return expected == sum;
}

// ddmm.mmmm → degrees
static bool ParseLatLon(const std::string& ddmm,
                        const std::string& hemi,
                        bool isLat,
                        double* outDeg) {
    if (ddmm.empty()) return false;

    double v = 0;
    if (!ParseDoubleSafe(ddmm, &v)) return false;

    double deg = floor(v / 100.0);
    double minutes = v - deg * 100.0;
    double res = deg + minutes / 60.0;

    if (hemi == "S" || hemi == "W")
        res = -res;

    *outDeg = res;
    return true;
}

std::optional<NmeaFix> NmeaParser::ParseRmc(const std::string& nmea) {

    auto star = nmea.find('*');
    std::string body = (star == std::string::npos) ?
        nmea : nmea.substr(0, star);

    auto parts = Split(body, ',');

    if (parts.size() < 10) return std::nullopt;
    if (parts[2] != "A") return std::nullopt;

    double lat = 0, lon = 0;
    if (!ParseLatLon(parts[3], parts[4], true, &lat)) return std::nullopt;
    if (!ParseLatLon(parts[5], parts[6], false, &lon)) return std::nullopt;

    double speedKnots = 0;
    double course = 0;

    ParseDoubleSafe(parts[7], &speedKnots);
    ParseDoubleSafe(parts[8], &course);

    NmeaFix fix{};
    fix.latDeg = lat;
    fix.lonDeg = lon;
    fix.speedMps = speedKnots * 0.514444;
    fix.bearingDeg = course;
    fix.valid = true;

    if (lastFix_) fix.altMeters = lastFix_->altMeters;

    return fix;
}

std::optional<NmeaFix> NmeaParser::ParseGga(const std::string& nmea) {

    auto star = nmea.find('*');
    std::string body = (star == std::string::npos) ?
        nmea : nmea.substr(0, star);

    auto parts = Split(body, ',');

    if (parts.size() < 10) return std::nullopt;
    if (parts[6].empty() || parts[6] == "0") return std::nullopt;

    double lat = 0, lon = 0;
    if (!ParseLatLon(parts[2], parts[3], true, &lat)) return std::nullopt;
    if (!ParseLatLon(parts[4], parts[5], false, &lon)) return std::nullopt;

    double alt = 0;
    ParseDoubleSafe(parts[9], &alt);

    NmeaFix fix{};
    fix.latDeg = lat;
    fix.lonDeg = lon;
    fix.altMeters = alt;
    fix.valid = true;

    if (lastFix_) {
        fix.speedMps = lastFix_->speedMps;
        fix.bearingDeg = lastFix_->bearingDeg;
    }

    return fix;
}

std::optional<NmeaFix> NmeaParser::ConsumeSentence(const std::string& nmea) {

    if (!VerifyChecksum(nmea))
        return std::nullopt;

    if (nmea.find("RMC") != std::string::npos) {
        auto f = ParseRmc(nmea);
        if (f) { lastFix_ = f; return f; }
    }

    if (nmea.find("GGA") != std::string::npos) {
        auto f = ParseGga(nmea);
        if (f) { lastFix_ = f; return f; }
    }

    return std::nullopt;
}
