#include "nmea.h"

#include <stdlib.h>
#include <string.h>

void nmea_init(nmea_t *n) { memset(n, 0, sizeof(*n)); }

static int hexval(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

// Pointer to field idx (0 = sentence id) of a comma-separated line, or NULL.
static const char *field(const char *s, int idx) {
    while (idx > 0) {
        s = strchr(s, ',');
        if (!s) return NULL;
        s++;
        idx--;
    }
    return s;
}

static bool empty_field(const char *f) { return !f || *f == ',' || *f == '*' || *f == 0; }

static void parse(nmea_t *n, const char *s) {
    // s starts after '$', e.g. "GNRMC,..." (talker GP, GN, GL, GA, GB)
    if (strlen(s) < 6) return;
    const char *type = s + 2;
    if (strncmp(type, "RMC,", 4) == 0) {
        n->rmc_count++;
        const char *st = field(s, 2);
        n->rmc_valid = st && *st == 'A';
        const char *sp = field(s, 7);
        if (n->rmc_valid && !empty_field(sp)) {
            float knots = strtof(sp, NULL);
            n->speed_mps = knots * 0.514444f;
        } else {
            n->speed_mps = 0.0f;
        }
    } else if (strncmp(type, "GGA,", 4) == 0) {
        const char *q = field(s, 6);
        const char *sat = field(s, 7);
        n->fix_quality = empty_field(q) ? 0 : (uint8_t)atoi(q);
        n->satellites = empty_field(sat) ? 0 : (uint8_t)atoi(sat);
    }
}

bool nmea_feed(nmea_t *n, char c) {
    if (c == '$') {
        n->len = 0;
        n->overflow = false;
        n->line[n->len++] = c;
        return false;
    }
    if (n->len == 0) return false;  // waiting for '$'
    if (c == '\r' || c == '\n') {
        bool ok = false;
        n->line[n->len] = 0;
        char *star = strrchr(n->line, '*');
        if (!n->overflow && star && (star - n->line) + 3 <= n->len) {
            uint8_t sum = 0;
            for (char *p = n->line + 1; p < star; p++) sum ^= (uint8_t)*p;
            int hi = hexval(star[1]), lo = hexval(star[2]);
            if (hi >= 0 && lo >= 0 && ((hi << 4) | lo) == sum) {
                parse(n, n->line + 1);
                ok = true;
            }
        }
        if (ok) n->good_sentences++;
        else n->bad_sentences++;
        n->len = 0;
        return ok;
    }
    if (n->len < sizeof(n->line) - 1) n->line[n->len++] = c;
    else n->overflow = true;
    return false;
}
