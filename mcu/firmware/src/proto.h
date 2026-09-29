// Line-based text protocol spoken over USB CDC (see ../PROTOCOL.md).
#pragma once
#include <stdint.h>
#include "device.h"

typedef void (*proto_out_fn)(const char *line); // line without '\n'

// Handle one received line (without the trailing newline).
void proto_handle_line(device_t *d, const char *line, uint32_t uptime_ms, proto_out_fn out);

// Emit "EVT <key> <value>" for every evented key whose value differs
// between *last and *cur, then copy the evented values into *last.
void proto_emit_changes(const device_t *cur, device_t *last, proto_out_fn out);

// Greeting sent when the host opens the port.
void proto_hello(proto_out_fn out);
