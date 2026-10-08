#include "usb_link.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "mcu_protocol.h"
#include "tusb.h"

#define LINK_TIMEOUT_MS 3500
#define QUEUE_LEN 40

typedef struct {
    mcu_prop_t p;
    bool snapshot;
} qentry_t;

static qentry_t queue[QUEUE_LEN];
static int queue_n;
static bool info_pending;
static bool snapshot_open;     // begin_snapshot seen, end not yet sent
static bool snapshot_closing;  // end_snapshot called: flag the last report
static uint8_t seq;
static uint32_t now_ms;
static uint32_t last_hello_ms;
static bool hello_seen;
static bool hello_edge;
static mcu_log_msg_t log_queue[4];
static int log_n;

static uint16_t consumer_pending;
static bool consumer_dirty;

void usb_link_init(void) {
    tusb_init();
}

bool usb_link_up(void) {
    return tud_mounted() && !tud_suspended() && hello_seen &&
           (now_ms - last_hello_ms) < LINK_TIMEOUT_MS;
}

bool usb_link_suspended(void) { return !tud_mounted() || tud_suspended(); }

void usb_link_send_prop(uint32_t prop, int32_t v0, int32_t v1) {
    for (int i = 0; i < queue_n; i++) {
        if (queue[i].p.prop == prop) {
            queue[i].p.v0 = v0;
            queue[i].p.v1 = v1;
            queue[i].snapshot |= snapshot_open;
            return;
        }
    }
    if (queue_n == QUEUE_LEN) {
        // Full (link down for a while): drop the oldest. A snapshot on reconnect resends all.
        memmove(&queue[0], &queue[1], sizeof(queue[0]) * (QUEUE_LEN - 1));
        queue_n--;
    }
    queue[queue_n].p = (mcu_prop_t){.prop = prop, .v0 = v0, .v1 = v1};
    queue[queue_n].snapshot = snapshot_open;
    queue_n++;
}

void usb_link_send_float(uint32_t prop, float v) {
    int32_t bits;
    memcpy(&bits, &v, sizeof(bits));
    usb_link_send_prop(prop, bits, 0);
}

void usb_link_begin_snapshot(void) {
    info_pending = true;
    snapshot_open = true;
    snapshot_closing = false;
}

void usb_link_end_snapshot(void) { snapshot_closing = true; }

void usb_link_log(const char *fmt, ...) {
    if (log_n == (int)(sizeof(log_queue) / sizeof(log_queue[0]))) return;
    mcu_log_msg_t *m = &log_queue[log_n];
    memset(m, 0, sizeof(*m));
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(m->text, sizeof(m->text), fmt, ap);
    va_end(ap);
    if (n < 0) return;
    m->type = MCU_MSG_LOG;
    m->len = (uint8_t)(n < (int)sizeof(m->text) ? n : (int)sizeof(m->text) - 1);
    log_n++;
}

void usb_link_consumer_key(uint16_t usage) {
    consumer_pending = usage;
    consumer_dirty = true;
}

static void send_vendor(void) {
    if (!tud_hid_n_ready(USB_ITF_VENDOR)) return;
    uint8_t buf[MCU_REPORT_SIZE];
    memset(buf, 0, sizeof(buf));

    if (info_pending) {
        mcu_info_msg_t *info = (mcu_info_msg_t *)buf;
        app_fill_info(info);
        info->type = MCU_MSG_INFO;
        info->proto_version = MCU_PROTO_VERSION;
        if (tud_hid_n_report(USB_ITF_VENDOR, 0, buf, sizeof(buf))) info_pending = false;
        return;
    }
    if (queue_n > 0) {
        mcu_props_msg_t *m = (mcu_props_msg_t *)buf;
        m->type = MCU_MSG_PROPS;
        m->seq = seq;
        int n = queue_n < MCU_PROPS_PER_MSG ? queue_n : MCU_PROPS_PER_MSG;
        bool snap = false;
        for (int i = 0; i < n; i++) {
            m->props[i] = queue[i].p;
            snap |= queue[i].snapshot;
        }
        m->count = (uint8_t)n;
        if (snap) m->flags |= MCU_PROPS_FLAG_SNAPSHOT;
        bool last = (n == queue_n);
        if (last && snapshot_open && snapshot_closing) m->flags |= MCU_PROPS_FLAG_SNAPSHOT_END;
        if (tud_hid_n_report(USB_ITF_VENDOR, 0, buf, sizeof(buf))) {
            seq++;
            memmove(&queue[0], &queue[n], sizeof(queue[0]) * (size_t)(queue_n - n));
            queue_n -= n;
            if (m->flags & MCU_PROPS_FLAG_SNAPSHOT_END) snapshot_open = snapshot_closing = false;
        }
        return;
    }
    if (log_n > 0) {
        memcpy(buf, &log_queue[0], sizeof(log_queue[0]));
        if (tud_hid_n_report(USB_ITF_VENDOR, 0, buf, sizeof(buf))) {
            memmove(&log_queue[0], &log_queue[1], sizeof(log_queue[0]) * (size_t)(log_n - 1));
            log_n--;
        }
    }
}

static void send_consumer(void) {
    if (!consumer_dirty || !tud_hid_n_ready(USB_ITF_CONSUMER)) return;
    uint16_t usage = consumer_pending;
    if (tud_hid_n_report(USB_ITF_CONSUMER, 0, &usage, sizeof(usage))) consumer_dirty = false;
}

void usb_link_task(uint32_t now) {
    now_ms = now;
    tud_task();

    if (hello_edge) {
        hello_edge = false;
        usb_link_begin_snapshot();
        app_on_snapshot_request();
        usb_link_end_snapshot();
    }
    if (!tud_mounted() || tud_suspended()) return;
    send_vendor();
    send_consumer();
}

// ---- TinyUSB callbacks ----

uint16_t tud_hid_get_report_cb(uint8_t instance, uint8_t report_id, hid_report_type_t report_type,
                               uint8_t *buffer, uint16_t reqlen) {
    (void)instance; (void)report_id; (void)report_type; (void)buffer; (void)reqlen;
    return 0;
}

void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id, hid_report_type_t report_type,
                           uint8_t const *buffer, uint16_t bufsize) {
    (void)report_id; (void)report_type;
    if (instance != USB_ITF_VENDOR || bufsize < 1) return;
    uint8_t msg[MCU_REPORT_SIZE] = {0};
    memcpy(msg, buffer, bufsize < sizeof(msg) ? bufsize : sizeof(msg));

    switch (msg[0]) {
    case MCU_MSG_HOST_HELLO: {
        bool was_up = usb_link_up();
        last_hello_ms = now_ms;
        hello_seen = true;
        if (!was_up) hello_edge = true;  // (re)connected: send everything
        break;
    }
    case MCU_MSG_HOST_SNAPSHOT:
        hello_edge = true;
        break;
    case MCU_MSG_HOST_SET: {
        const mcu_props_msg_t *m = (const mcu_props_msg_t *)msg;
        int n = m->count <= MCU_PROPS_PER_MSG ? m->count : MCU_PROPS_PER_MSG;
        for (int i = 0; i < n; i++) app_on_host_set(m->props[i].prop, m->props[i].v0, m->props[i].v1);
        break;
    }
    case MCU_MSG_HOST_BOOTSEL: {
        const mcu_bootsel_msg_t *m = (const mcu_bootsel_msg_t *)msg;
        if (m->magic == MCU_BOOTSEL_MAGIC) app_on_bootsel_request();
        break;
    }
    default:
        break;
    }
}

void tud_umount_cb(void) { hello_seen = false; }
void tud_suspend_cb(bool remote_wakeup_en) { (void)remote_wakeup_en; hello_seen = false; }
void tud_resume_cb(void) {}
