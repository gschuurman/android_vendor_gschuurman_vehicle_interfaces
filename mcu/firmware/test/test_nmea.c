#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "nmea.h"

static int feed(nmea_t *n, const char *s) {
    int ok = 0;
    for (; *s; s++) ok += nmea_feed(n, *s);
    return ok;
}

int main(void) {
    nmea_t n;
    // Build sentences with correct checksums instead of trusting hand-typed ones.
    const char *bodies[] = {
        "GNRMC,123519.00,A,5207.12345,N,00507.45678,E,10.000,84.40,081026,,,A,V",
        "GNGGA,123519.00,5207.12345,N,00507.45678,E,1,09,0.9,10.0,M,46.0,M,,",
        "GPRMC,123520.00,V,,,,,,,081026,,,N",
    };
    nmea_init(&n);
    for (int i = 0; i < 3; i++) {
        unsigned char sum = 0;
        for (const char *p = bodies[i]; *p; p++) sum ^= (unsigned char)*p;
        char line[128];
        snprintf(line, sizeof line, "$%s*%02X\r\n", bodies[i], sum);
        assert(feed(&n, line) == 1);
        if (i == 0) {
            assert(n.rmc_valid);
            assert(fabsf(n.speed_mps - 5.14444f) < 0.001f);
        }
        if (i == 1) {
            assert(n.fix_quality == 1);
            assert(n.satellites == 9);
        }
        if (i == 2) {
            assert(!n.rmc_valid);
            assert(n.speed_mps == 0.0f);
        }
    }
    // Bad checksum is rejected and leaves the values alone.
    assert(feed(&n, "$GNGGA,1,2,3,4,5,0,00,,,,,,,*00\r\n") == 0);
    assert(n.satellites == 9);
    // Garbage and a truncated line do not crash.
    feed(&n, "\x01\x02$$$,,,*\r\n$GNRMC");
    char longline[300];
    memset(longline, 'A', sizeof longline);
    longline[0] = '$';
    longline[299] = 0;
    feed(&n, longline);
    feed(&n, "\r\n");
    printf("test_nmea: ok\n");
    return 0;
}
