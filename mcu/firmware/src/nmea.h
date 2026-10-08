// Minimal NMEA reader: speed from RMC, fix and satellites from GGA.
// Hardware independent (host tests in test/).
#pragma once
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    char line[96];
    uint8_t len;
    bool overflow;
    // results
    bool rmc_valid;      // last RMC had status A
    float speed_mps;     // from the last valid RMC
    uint8_t fix_quality; // GGA field 6
    uint8_t satellites;  // GGA field 7
    uint32_t good_sentences;
    uint32_t bad_sentences;
    uint32_t rmc_count;  // increments on every RMC parsed
} nmea_t;

void nmea_init(nmea_t *n);
// Feed one received byte. Returns true when a sentence with a good checksum was parsed.
bool nmea_feed(nmea_t *n, char c);
