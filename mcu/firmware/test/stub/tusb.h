// Minimal TinyUSB stand-in for the host test of usb_link.c.
#pragma once
#include <stdbool.h>
#include <stdint.h>
typedef int hid_report_type_t;
void tusb_init(void);
void tud_task(void);
bool tud_mounted(void);
bool tud_suspended(void);
bool tud_hid_n_ready(uint8_t instance);
bool tud_hid_n_report(uint8_t instance, uint8_t report_id, void const *report, uint16_t len);
void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id, hid_report_type_t report_type,
                           uint8_t const *buffer, uint16_t bufsize);
