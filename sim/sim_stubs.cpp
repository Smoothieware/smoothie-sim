// Firmware declares these virtuals but never defines them (the ARM linker discards the unused vtable); the host linker needs them.
#include "ModbusSpindleControl.h"
void ModbusSpindleControl::turn_on(void) {}
void ModbusSpindleControl::turn_off(void) {}
void ModbusSpindleControl::set_speed(int) {}
void ModbusSpindleControl::report_speed(void) {}
// Panel creates an SDCard for the optional external SD slot; the simulator has no SD hardware.
#include "SDCard.h"
SDCard::SDCard(PinName mosi, PinName miso, PinName sclk, PinName cs) : _spi(mosi, miso, sclk), _cs(cs) {}
int SDCard::disk_initialize() { return 1; }
int SDCard::disk_write(const char *, uint32_t) { return 1; }
int SDCard::disk_read(char *, uint32_t) { return 1; }
int SDCard::disk_status() { return 1; }
int SDCard::disk_sync() { return 0; }
uint32_t SDCard::disk_sectors() { return 0; }
uint64_t SDCard::disk_size() { return 0; }
uint32_t SDCard::disk_blocksize() { return 512; }
bool SDCard::disk_canDMA(void) { return false; }
bool SDCard::busy() { return false; }
