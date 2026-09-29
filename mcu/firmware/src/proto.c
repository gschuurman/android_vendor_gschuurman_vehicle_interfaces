#include "proto.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PROTO_LINE_MAX 96

void device_defaults(device_t *d) {
    memset(d, 0, sizeof(*d));
    d->vbat_mv = 0;
    d->lux = -1;
    d->state = PWR_STATE_OFF;
    d->amp_mode = AMP_MODE_AUTO;
    d->bl_en = true;
    d->bl_duty = 800;
    d->bl_freq = 32768; // same 30518 ns period the VHAL used on PWM_F
    d->off_delay_s = 15 * 60;
}

static const char *amp_mode_name(amp_mode_t m) {
    switch (m) {
    case AMP_MODE_OFF: return "off";
    case AMP_MODE_ON: return "on";
    case AMP_MODE_AUTO: return "auto";
    }
    return "?";
}

// ---------------------------------------------------------------- value parsing

static const char *parse_u32(const char *s, uint32_t lo, uint32_t hi, uint32_t *out) {
    if (!s || !*s) return "missing_value";
    char *end;
    unsigned long v = strtoul(s, &end, 10);
    if (*end != '\0' || !isdigit((unsigned char)s[0])) return "not_a_number";
    if (v < lo || v > hi) return "out_of_range";
    *out = (uint32_t)v;
    return NULL;
}

static const char *parse_bool(const char *s, bool *out) {
    if (!s) return "missing_value";
    if (!strcmp(s, "1") || !strcmp(s, "on") || !strcmp(s, "true")) { *out = true; return NULL; }
    if (!strcmp(s, "0") || !strcmp(s, "off") || !strcmp(s, "false")) { *out = false; return NULL; }
    return "not_a_bool";
}

// ---------------------------------------------------------------- key table

typedef void (*get_fn)(const device_t *d, char *buf, size_t n);
typedef const char *(*set_fn)(device_t *d, const char *v);

typedef struct {
    const char *name;
    get_fn get;   // NULL = write-only command
    set_fn set;   // NULL = read-only
    bool evented; // pushed as EVT when it changes
} proto_key_t;

#define GET_BOOL(field) \
    static void get_##field(const device_t *d, char *b, size_t n) { snprintf(b, n, "%d", d->field ? 1 : 0); }
GET_BOOL(acc)
GET_BOOL(reverse)
GET_BOOL(illum)
GET_BOOL(park)
GET_BOOL(service)
GET_BOOL(sbc_power)
GET_BOOL(amp_out)
GET_BOOL(bl_en)

static void get_vbat_mv(const device_t *d, char *b, size_t n) { snprintf(b, n, "%ld", (long)d->vbat_mv); }
static void get_lux(const device_t *d, char *b, size_t n) { snprintf(b, n, "%ld", (long)d->lux); }
static void get_state(const device_t *d, char *b, size_t n) { snprintf(b, n, "%s", pwr_state_name(d->state)); }
static void get_amp(const device_t *d, char *b, size_t n) { snprintf(b, n, "%s", amp_mode_name(d->amp_mode)); }
static void get_bl_duty(const device_t *d, char *b, size_t n) { snprintf(b, n, "%u", (unsigned)d->bl_duty); }
static void get_bl_freq(const device_t *d, char *b, size_t n) { snprintf(b, n, "%lu", (unsigned long)d->bl_freq); }
static void get_off_delay_s(const device_t *d, char *b, size_t n) { snprintf(b, n, "%lu", (unsigned long)d->off_delay_s); }

static const char *set_amp(device_t *d, const char *v) {
    if (!v) return "missing_value";
    if (!strcmp(v, "off") || !strcmp(v, "0")) d->amp_mode = AMP_MODE_OFF;
    else if (!strcmp(v, "on") || !strcmp(v, "1")) d->amp_mode = AMP_MODE_ON;
    else if (!strcmp(v, "auto")) d->amp_mode = AMP_MODE_AUTO;
    else return "expected_off_on_auto";
    return NULL;
}
static const char *set_bl_en(device_t *d, const char *v) { return parse_bool(v, &d->bl_en); }
static const char *set_bl_duty(device_t *d, const char *v) {
    uint32_t x; const char *e = parse_u32(v, 0, 1000, &x);
    if (!e) d->bl_duty = (uint16_t)x;
    return e;
}
static const char *set_bl_freq(device_t *d, const char *v) { return parse_u32(v, 100, 100000, &d->bl_freq); }
static const char *set_off_delay_s(device_t *d, const char *v) { return parse_u32(v, 10, 24 * 3600, &d->off_delay_s); }
static const char *set_power_key(device_t *d, const char *v) { return parse_u32(v, 50, 10000, &d->key_press_request_ms); }
static const char *set_bootsel(device_t *d, const char *v) {
    bool b; const char *e = parse_bool(v, &b);
    if (!e && b) d->bootsel_request = true;
    return e;
}

static const proto_key_t KEYS[] = {
    {"state",       get_state,       NULL,            true},
    {"acc",         get_acc,         NULL,            true},
    {"reverse",     get_reverse,     NULL,            true},
    {"illum",       get_illum,       NULL,            true},
    {"park",        get_park,        NULL,            true},
    {"service",     get_service,     NULL,            true},
    {"sbc_power",   get_sbc_power,   NULL,            true},
    {"vbat_mv",     get_vbat_mv,     NULL,            true},
    {"lux",         get_lux,         NULL,            true},
    {"amp_out",     get_amp_out,     NULL,            true},
    {"amp",         get_amp,         set_amp,         true},
    {"bl_en",       get_bl_en,       set_bl_en,       true},
    {"bl_duty",     get_bl_duty,     set_bl_duty,     true},
    {"bl_freq",     get_bl_freq,     set_bl_freq,     false},
    {"off_delay_s", get_off_delay_s, set_off_delay_s, false},
    {"power_key",   NULL,            set_power_key,   false},
    {"bootsel",     NULL,            set_bootsel,     false},
};
#define NKEYS (sizeof(KEYS) / sizeof(KEYS[0]))

static const proto_key_t *find_key(const char *name) {
    for (size_t i = 0; i < NKEYS; i++)
        if (!strcmp(KEYS[i].name, name)) return &KEYS[i];
    return NULL;
}

static void emit_kv(proto_out_fn out, const char *tag, const char *key, const char *val) {
    char line[PROTO_LINE_MAX + 32];
    snprintf(line, sizeof(line), "%s %s %s", tag, key, val);
    out(line);
}

// ---------------------------------------------------------------- public API

void proto_hello(proto_out_fn out) {
    char line[64];
    snprintf(line, sizeof(line), "HELLO carradio-periph %s %d", FW_VERSION, PROTO_VERSION);
    out(line);
}

void proto_handle_line(device_t *d, const char *raw, uint32_t uptime_ms, proto_out_fn out) {
    char line[PROTO_LINE_MAX + 1];
    size_t n = strlen(raw);
    if (n > PROTO_LINE_MAX) { out("ERR - line_too_long"); return; }
    memcpy(line, raw, n + 1);
    while (n && (line[n - 1] == '\r' || line[n - 1] == ' ')) line[--n] = '\0';

    char *save = NULL;
    char *verb = strtok_r(line, " ", &save);
    if (!verb || verb[0] == '#') return; // empty line or comment
    for (char *p = verb; *p; p++) *p = (char)toupper((unsigned char)*p);
    char *key = strtok_r(NULL, " ", &save);
    char *val = strtok_r(NULL, " ", &save);
    char buf[48];

    if (!strcmp(verb, "PING")) {
        snprintf(buf, sizeof(buf), "PONG %lu", (unsigned long)uptime_ms);
        out(buf);
    } else if (!strcmp(verb, "VER")) {
        proto_hello(out);
    } else if (!strcmp(verb, "GET")) {
        if (!key) { out("ERR - missing_key"); return; }
        if (!strcmp(key, "*")) {
            for (size_t i = 0; i < NKEYS; i++) {
                if (!KEYS[i].get) continue;
                KEYS[i].get(d, buf, sizeof(buf));
                emit_kv(out, "VAL", KEYS[i].name, buf);
            }
            out("END");
            return;
        }
        const proto_key_t *k = find_key(key);
        if (!k || !k->get) { emit_kv(out, "ERR", key, "unknown_key"); return; }
        k->get(d, buf, sizeof(buf));
        emit_kv(out, "VAL", key, buf);
    } else if (!strcmp(verb, "SET")) {
        if (!key) { out("ERR - missing_key"); return; }
        const proto_key_t *k = find_key(key);
        if (!k) { emit_kv(out, "ERR", key, "unknown_key"); return; }
        if (!k->set) { emit_kv(out, "ERR", key, "read_only"); return; }
        const char *err = k->set(d, val);
        if (err) { emit_kv(out, "ERR", key, err); return; }
        if (k->get) k->get(d, buf, sizeof(buf));
        emit_kv(out, "OK", key, k->get ? buf : val);
    } else {
        emit_kv(out, "ERR", "-", "unknown_command");
    }
}

void proto_emit_changes(const device_t *cur, device_t *last, proto_out_fn out) {
    char a[48], b[48];
    for (size_t i = 0; i < NKEYS; i++) {
        if (!KEYS[i].evented) continue;
        KEYS[i].get(cur, a, sizeof(a));
        KEYS[i].get(last, b, sizeof(b));
        if (strcmp(a, b)) emit_kv(out, "EVT", KEYS[i].name, a);
    }
    *last = *cur;
}
