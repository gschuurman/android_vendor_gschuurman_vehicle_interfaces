// Peripheral state shared between the hardware loop and the USB protocol.
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "power_sm.h"

#define FW_VERSION     "0.2.0"
#define PROTO_VERSION  1

typedef enum { AMP_MODE_OFF = 0, AMP_MODE_ON, AMP_MODE_AUTO } amp_mode_t;

typedef struct {
    // Inputs (read-only over USB)
    bool acc;
    bool reverse;
    bool illum;
    bool park;
    bool service;
    bool sbc_power;
    int32_t vbat_mv;    // battery voltage, updated with 100 mV hysteresis
    int32_t lux;        // BH1750 reading, -1 when no sensor answers
    pwr_state_t state;
    bool amp_out;       // actual state of the amplifier remote output

    // Settings (read/write over USB)
    amp_mode_t amp_mode;
    bool bl_en;
    uint16_t bl_duty;   // backlight duty in permille, 0..1000
    uint32_t bl_freq;   // backlight PWM frequency in Hz
    uint32_t off_delay_s;

    // One-shot requests from the host, consumed by the main loop
    uint32_t key_press_request_ms;
    bool bootsel_request;
} device_t;

void device_defaults(device_t *d);
