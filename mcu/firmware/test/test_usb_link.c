// usb_link.c against a fake TinyUSB: hello -> info + snapshot, host writes, coalescing.
#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "mcu_protocol.h"
#include "tusb.h"
#include "usb_link.h"

static uint8_t sent[64][64];
static int nsent;
static uint16_t consumer;
static uint32_t set_prop; static int32_t set_v0;
static int snapshots;

void tusb_init(void) {}
void tud_task(void) {}
bool tud_mounted(void) { return true; }
bool tud_suspended(void) { return false; }
bool tud_hid_n_ready(uint8_t i) { (void)i; return true; }
bool tud_hid_n_report(uint8_t inst, uint8_t id, void const *r, uint16_t len) {
    (void)id;
    if (inst == USB_ITF_CONSUMER) { memcpy(&consumer, r, 2); return true; }
    assert(len == 64);
    memcpy(sent[nsent++], r, 64);
    return true;
}
void app_on_host_set(uint32_t prop, int32_t v0, int32_t v1) { (void)v1; set_prop = prop; set_v0 = v0; }
void app_on_snapshot_request(void) {
    snapshots++;
    for (uint32_t i = 0; i < 7; i++) usb_link_send_prop(0x21400600 + i, (int32_t)i, 0);
}
void app_on_bootsel_request(void) {}
void app_fill_info(void *p) { ((mcu_info_msg_t *)p)->board_rev = 6; }

static void host_write(const void *msg, size_t len) {
    uint8_t buf[64] = {0};
    memcpy(buf, msg, len);
    tud_hid_set_report_cb(USB_ITF_VENDOR, 0, 0, buf, 64);
}

int main(void) {
    usb_link_init();
    uint32_t t = 1000;
    usb_link_task(t);
    assert(!usb_link_up());
    // Updates queued while the link is down coalesce per property.
    usb_link_send_prop(MCU_PROP_GEAR_SELECTION, 4, 0);
    usb_link_send_prop(MCU_PROP_GEAR_SELECTION, 2, 0);

    mcu_hello_msg_t h = {.type = MCU_MSG_HOST_HELLO, .proto_version = MCU_PROTO_VERSION};
    host_write(&h, sizeof h);
    assert(usb_link_up());
    for (int i = 0; i < 10; i++) usb_link_task(t += 10);
    assert(snapshots == 1);
    assert(sent[0][0] == MCU_MSG_INFO && ((mcu_info_msg_t *)sent[0])->board_rev == 6);
    // 1 gear + 7 snapshot props = 8 -> two PROPS reports, the last flagged SNAPSHOT_END.
    int props = 0, end = 0;
    for (int i = 1; i < nsent; i++) {
        mcu_props_msg_t *m = (mcu_props_msg_t *)sent[i];
        assert(m->type == MCU_MSG_PROPS);
        props += m->count;
        if (m->flags & MCU_PROPS_FLAG_SNAPSHOT_END) { end++; assert(i == nsent - 1); }
        for (int k = 0; k < m->count; k++)
            if (m->props[k].prop == MCU_PROP_GEAR_SELECTION) assert(m->props[k].v0 == 2);
    }
    assert(props == 8 && end == 1);

    // A second hello while connected does not resend the snapshot.
    host_write(&h, sizeof h);
    usb_link_task(t += 10);
    assert(snapshots == 1);

    // Host write reaches the app.
    mcu_props_msg_t set = {.type = MCU_MSG_HOST_SET, .count = 1,
                           .props = {{MCU_PROP_DISPLAY_BRIGHTNESS, 77, 0}}};
    host_write(&set, sizeof set);
    assert(set_prop == MCU_PROP_DISPLAY_BRIGHTNESS && set_v0 == 77);

    // Heartbeat timeout -> link down -> next hello triggers a new snapshot.
    usb_link_task(t += 4000);
    assert(!usb_link_up());
    host_write(&h, sizeof h);
    usb_link_task(t += 10);
    assert(snapshots == 2);

    usb_link_consumer_key(0xE9);
    usb_link_task(t += 10);
    assert(consumer == 0xE9);
    printf("test_usb_link: ok\n");
    return 0;
}
