#pragma once
#include "mbed.h"
// host shim: pin multiplexing does nothing in the simulator
static inline void pin_function(int, int) {}
static inline void pin_mode(int, int) {}
static inline PinName parse_pins(const char *) { return (PinName)0; }
