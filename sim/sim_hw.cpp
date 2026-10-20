#include "sim_hw.h"
#include "sim_runtime.h"
#include <cstring>

LPC_GPIO_TypeDef sim_gpio[5];
LPC_TIM_TypeDef sim_tim[4];
LPC_SC_TypeDef sim_sc;
LPC_PINCON_TypeDef sim_pincon;
LPC_ADC_TypeDef sim_adc;
LPC_PWM_TypeDef sim_pwm1;
LPC_UART_TypeDef sim_uart[4];
LPC_WDT_TypeDef sim_wdt;
LPC_GPIOINT_TypeDef sim_gpioint;
uint32_t SystemCoreClock = 96000000;
void SystemInit(void) {}

// Firmware config text lives here; Config() reads it through the same two symbols the real firmware
// gets from objcopy of src/config.default (start/end of an embedded text blob).
extern "C" { char sim_config_buf[1 << 18]; }
asm(".globl _binary_config_default_start\n_binary_config_default_start = sim_config_buf\n"
    ".globl _binary_config_default_end\n_binary_config_default_end = sim_config_buf + 262144\n");

extern "C" {
uint32_t us_ticker_read(void) { uint32_t t = (uint32_t)SIM.now_us; sim_advance(1); return t; }
void sim_note_blocking(const char *what, uint64_t us) {
    WaitRec w; w.kind = what; w.microseconds = us; w.gcode_line = SIM.current_line;
    if (!SIM.stack.empty()) { w.module = SIM.stack.back().module; w.event = sim_event_name(SIM.stack.back().event); }
    SIM.waits.push_back(w);
}
void wait(float s) { sim_note_blocking("wait", (uint64_t)(s * 1e6)); sim_advance((uint64_t)(s * 1e6)); }
void wait_ms(int ms) { sim_note_blocking("wait_ms", (uint64_t)ms * 1000); sim_advance((uint64_t)ms * 1000); }
void wait_us(int us) { sim_note_blocking("wait_us", us); sim_advance(us); }
}

uint32_t UART_Send(LPC_UART_TypeDef *, uint8_t *data, uint32_t len, TRANSFER_BLOCK_Type) {
    SIM.serial_out.append((const char *)data, len); return len;
}
void UART_SendByte(LPC_UART_TypeDef *, uint8_t byte) { SIM.serial_out.push_back((char)byte); }

// ---- link-time stand-ins for firmware-only symbols (ADC driver, heap statistics, status LEDs) ----
#include "adc.h"
#include "gpio.h"
namespace mbed {
std::vector<InterruptIn *> &sim_interrupt_pins() { static std::vector<InterruptIn *> v; return v; }
ADC::ADC(int, int) {}
void ADC::setup(PinName, int) {}
void ADC::burst(int) {}
void ADC::interrupt_state(PinName, int) {}
void ADC::append(void (*)(int, uint32_t)) {}
int ADC::_pin_to_channel(PinName) { return 0; }
}
GPIO leds[4] = {GPIO(P1_18), GPIO(P1_19), GPIO(P1_20), GPIO(P1_21)};
unsigned int g_maximumHeapAddress = 0;
extern "C" {
uint32_t __end__ = 0;
uint32_t __malloc_free_list = 0;
uint32_t _sbrk(int) { return 0; }
}
