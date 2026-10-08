// USB descriptors: one device, two HID interfaces.
//   Interface 0: vendor page 0xFF00, 64-byte IN/OUT reports, the VHAL link (/dev/hidraw*).
//   Interface 1: consumer control, the display buttons as media keys (Android input).
#include <string.h>

#include "mcu_protocol.h"
#include "pico/unique_id.h"
#include "tusb.h"
#include "usb_link.h"

#define FW_BCD 0x0100

static const tusb_desc_device_t desc_device = {
    .bLength = sizeof(tusb_desc_device_t),
    .bDescriptorType = TUSB_DESC_DEVICE,
    .bcdUSB = 0x0200,
    .bDeviceClass = 0x00,
    .bDeviceSubClass = 0x00,
    .bDeviceProtocol = 0x00,
    .bMaxPacketSize0 = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor = MCU_USB_VID,
    .idProduct = MCU_USB_PID,
    .bcdDevice = FW_BCD,
    .iManufacturer = 1,
    .iProduct = 2,
    .iSerialNumber = 3,
    .bNumConfigurations = 1,
};

uint8_t const *tud_descriptor_device_cb(void) { return (uint8_t const *)&desc_device; }

static const uint8_t desc_hid_vendor[] = {TUD_HID_REPORT_DESC_GENERIC_INOUT(MCU_REPORT_SIZE)};
static const uint8_t desc_hid_consumer[] = {TUD_HID_REPORT_DESC_CONSUMER()};

uint8_t const *tud_hid_descriptor_report_cb(uint8_t instance) {
    return instance == USB_ITF_VENDOR ? desc_hid_vendor : desc_hid_consumer;
}

#define EPNUM_VENDOR_OUT 0x01
#define EPNUM_VENDOR_IN 0x81
#define EPNUM_CONSUMER_IN 0x82
#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + TUD_HID_INOUT_DESC_LEN + TUD_HID_DESC_LEN)

static const uint8_t desc_configuration[] = {
    TUD_CONFIG_DESCRIPTOR(1, 2, 0, CONFIG_TOTAL_LEN, 0, 100),
    TUD_HID_INOUT_DESCRIPTOR(USB_ITF_VENDOR, 4, HID_ITF_PROTOCOL_NONE, sizeof(desc_hid_vendor),
                             EPNUM_VENDOR_OUT, EPNUM_VENDOR_IN, MCU_REPORT_SIZE, 1),
    TUD_HID_DESCRIPTOR(USB_ITF_CONSUMER, 5, HID_ITF_PROTOCOL_NONE, sizeof(desc_hid_consumer),
                       EPNUM_CONSUMER_IN, 16, 5),
};

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) {
    (void)index;
    return desc_configuration;
}

static const char *const string_desc[] = {
    NULL,                       // 0: language (handled below)
    "gschuurman",               // 1: manufacturer
    "Car radio peripheral MCU", // 2: product
    NULL,                       // 3: serial, from the flash unique id
    "VHAL link",                // 4
    "Display buttons",          // 5
};

static uint16_t desc_str[33];

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
    (void)langid;
    size_t n;
    if (index == 0) {
        desc_str[1] = 0x0409;
        n = 1;
    } else {
        char serial[2 * PICO_UNIQUE_BOARD_ID_SIZE_BYTES + 1];
        const char *s;
        if (index == 3) {
            pico_get_unique_board_id_string(serial, sizeof(serial));
            s = serial;
        } else if (index < sizeof(string_desc) / sizeof(string_desc[0])) {
            s = string_desc[index];
        } else {
            return NULL;
        }
        n = strlen(s);
        if (n > 32) n = 32;
        for (size_t i = 0; i < n; i++) desc_str[1 + i] = (uint8_t)s[i];
    }
    desc_str[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * n + 2));
    return desc_str;
}
