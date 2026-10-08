// USB HID link to the VHAL (vendor interface) and the media-key interface.
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define USB_ITF_VENDOR 0
#define USB_ITF_CONSUMER 1

void usb_link_init(void);
void usb_link_task(uint32_t now_ms);

// VHAL heartbeat seen in the last few seconds and the device is configured.
bool usb_link_up(void);
// Host has suspended the bus (VIM3 in suspend) or the device is not configured.
bool usb_link_suspended(void);

// Queue a property update. A newer value for the same property replaces a queued one.
void usb_link_send_prop(uint32_t prop, int32_t v0, int32_t v1);
void usb_link_send_float(uint32_t prop, float v);
// Mark the start/end of a full snapshot (MCU_MSG_INFO is sent first).
void usb_link_begin_snapshot(void);
void usb_link_end_snapshot(void);
void usb_link_log(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

// Media key (HID consumer usage, e.g. 0xE9 volume up). 0 = released.
void usb_link_consumer_key(uint16_t usage);

// Implemented by the application.
void app_on_host_set(uint32_t prop, int32_t v0, int32_t v1);
void app_on_snapshot_request(void);  // fill the queue between begin/end_snapshot
void app_on_bootsel_request(void);
void app_fill_info(void *info /* mcu_info_msg_t */);
