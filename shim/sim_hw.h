// Fake LPC1768 / mbed hardware layer for the Smoothieware x86 simulator.
// Everything here replaces a chip register, a vendor library or an mbed class.
// Blocking calls (wait, wait_ms, wait_us) are instrumented: they advance the fake
// clock and are reported to the wait detector (see sim/sim_runtime.h).
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string>
#include <vector>
#include <functional>
#include <algorithm>

#define MRI_ENABLE 0
#define __IO volatile
#define __I volatile const
#define __O volatile

// ---------- instrumented time / waiting (implemented in sim/sim_hw.cpp) ----------
extern "C" {
uint32_t us_ticker_read(void);
void wait(float seconds);
void wait_ms(int ms);
void wait_us(int us);
void sim_note_blocking(const char *what, uint64_t microseconds);
}
extern uint32_t SystemCoreClock;
void SystemInit(void);

// ---------- chip registers (plain memory, no side effects) ----------
struct LPC_GPIO_TypeDef { uint32_t FIODIR, FIOMASK, FIOPIN, FIOSET, FIOCLR; };
struct LPC_TIM_TypeDef { uint32_t IR, TCR, TC, PR, PC, MCR, MR0, MR1, MR2, MR3, CCR, CR0, CR1, EMR, CTCR; };
struct LPC_SC_TypeDef { uint32_t PCONP, PCLKSEL0, PCLKSEL1, PCON, CLKSRCSEL, CCLKCFG, PLL0CON, PLL0CFG, PLL0STAT, PLL0FEED, EXTINT, EXTMODE, EXTPOLAR; };
struct LPC_PINCON_TypeDef {
    uint32_t PINSEL0, PINSEL1, PINSEL2, PINSEL3, PINSEL4, PINSEL5, PINSEL6, PINSEL7, PINSEL8, PINSEL9, PINSEL10;
    uint32_t PINMODE0, PINMODE1, PINMODE2, PINMODE3, PINMODE4, PINMODE5, PINMODE6, PINMODE7, PINMODE8, PINMODE9;
    uint32_t PINMODE_OD0, PINMODE_OD1, PINMODE_OD2, PINMODE_OD3, PINMODE_OD4;
};
struct LPC_ADC_TypeDef { uint32_t ADCR, ADGDR, ADINTEN, ADDR[8], ADSTAT; };
struct LPC_PWM_TypeDef { uint32_t IR, TCR, TC, PR, PC, MCR, MR0, MR1, MR2, MR3, MR4, MR5, MR6, LER, PCR, CTCR; };
struct LPC_UART_TypeDef { uint32_t dummy; };
struct LPC_WDT_TypeDef { uint32_t WDMOD, WDTC, WDFEED, WDTV, WDCLKSEL; };
struct LPC_GPIOINT_TypeDef { uint32_t IntStatus, IO0IntStatR, IO0IntStatF, IO0IntClr, IO0IntEnR, IO0IntEnF, IO2IntStatR, IO2IntStatF, IO2IntClr, IO2IntEnR, IO2IntEnF; };

extern LPC_GPIO_TypeDef sim_gpio[5];
extern LPC_TIM_TypeDef sim_tim[4];
extern LPC_SC_TypeDef sim_sc;
extern LPC_PINCON_TypeDef sim_pincon;
extern LPC_ADC_TypeDef sim_adc;
extern LPC_PWM_TypeDef sim_pwm1;
extern LPC_UART_TypeDef sim_uart[4];
extern LPC_WDT_TypeDef sim_wdt;
extern LPC_GPIOINT_TypeDef sim_gpioint;
#define LPC_GPIO0 (&sim_gpio[0])
#define LPC_GPIO1 (&sim_gpio[1])
#define LPC_GPIO2 (&sim_gpio[2])
#define LPC_GPIO3 (&sim_gpio[3])
#define LPC_GPIO4 (&sim_gpio[4])
#define LPC_TIM0 (&sim_tim[0])
#define LPC_TIM1 (&sim_tim[1])
#define LPC_TIM2 (&sim_tim[2])
#define LPC_TIM3 (&sim_tim[3])
#define LPC_SC (&sim_sc)
#define LPC_PINCON (&sim_pincon)
#define LPC_ADC (&sim_adc)
#define LPC_PWM1 (&sim_pwm1)
#define LPC_UART0 (&sim_uart[0])
#define LPC_UART1 (&sim_uart[1])
#define LPC_UART2 (&sim_uart[2])
#define LPC_UART3 (&sim_uart[3])
#define LPC_WDT (&sim_wdt)
#define LPC_GPIOINT (&sim_gpioint)

// ---------- interrupt controller (no-ops; the simulator calls the ISRs itself) ----------
enum IRQn_Type { TIMER0_IRQn, TIMER1_IRQn, TIMER2_IRQn, TIMER3_IRQn, PendSV_IRQn, ADC_IRQn, USB_IRQn,
                 UART0_IRQn, UART1_IRQn, UART2_IRQn, UART3_IRQn, EINT3_IRQn, WDT_IRQn, PWM1_IRQn };
typedef IRQn_Type IRQn;
static inline void NVIC_SetPriorityGrouping(uint32_t) {}
static inline void NVIC_SetPriority(IRQn_Type, uint32_t) {}
static inline uint32_t NVIC_GetPriority(IRQn_Type) { return 0; }
static inline void NVIC_EnableIRQ(IRQn_Type) {}
static inline void NVIC_DisableIRQ(IRQn_Type) {}
static inline void NVIC_SetVector(IRQn_Type, uint32_t) {}
static inline void NVIC_SetPendingIRQ(IRQn_Type) {}
static inline void __disable_irq(void) {}
static inline void __enable_irq(void) {}
static inline void __debugbreak(void) {  /* debugger breakpoint: not a wait */ }
static inline void __WFI(void) {}
static inline void __NOP(void) {}
static inline uint32_t __get_PRIMASK(void) { return 0; }
static inline void __set_PRIMASK(uint32_t) {}
static inline void __set_BASEPRI(uint32_t) {}

// ---------- MRI debug monitor ----------
static inline int __mriPlatform_CommUartIndex(void) { return 0; }
static inline int __mriPlatform_CommHasReceiveData(void) { return 0; }
static inline void __mriPlatform_EnteringDebuggerHook(void) {}
static inline void __mriPlatform_LeavingDebuggerHook(void) {}

// ---------- UART vendor library used by SerialConsole (captures output) ----------
enum FunctionalState { DISABLE = 0, ENABLE = 1 };
enum TRANSFER_BLOCK_Type { NONE_BLOCKING = 0, BLOCKING };
struct UART_CFG_Type { uint32_t Baud_rate; int Databits, Parity, Stopbits; };
struct UART_FIFO_CFG_Type { int FIFO_ResetRxBuf, FIFO_ResetTxBuf, FIFO_DMAMode, FIFO_Level; };
struct PINSEL_CFG_Type { uint8_t Portnum, Pinnum, Funcnum, Pinmode, OpenDrain; };
#define UART_DATABIT_8 0
#define UART_PARITY_NONE 0
#define UART_STOPBIT_1 0
#define UART_FIFO_TRGLEV0 0
#define UART_INTCFG_RBR 0
#define UART_INTCFG_RLS 1
#define UART_INTCFG_THRE 2
#define UART_IIR_INTID_MASK 0xE
#define UART_IIR_INTID_RLS 0x6
#define UART_IIR_INTID_RDA 0x4
#define UART_IIR_INTID_CTI 0xC
#define UART_LSR_OE 1
#define UART_LSR_PE 2
#define UART_LSR_FE 4
#define UART_LSR_BI 8
#define UART_LSR_RXFE 0x80
#define PINSEL_PINMODE_PULLUP 0
#define PINSEL_PINMODE_NORMAL 0
#define PINSEL_PINMODE_TRISTATE 2
static inline void UART_ConfigStructInit(UART_CFG_Type *c) { c->Baud_rate = 9600; }
static inline void UART_FIFOConfigStructInit(UART_FIFO_CFG_Type *) {}
static inline void UART_Init(LPC_UART_TypeDef *, UART_CFG_Type *) {}
static inline void UART_DeInit(LPC_UART_TypeDef *) {}
static inline void UART_FIFOConfig(LPC_UART_TypeDef *, UART_FIFO_CFG_Type *) {}
static inline void UART_TxCmd(LPC_UART_TypeDef *, FunctionalState) {}
static inline void UART_IntConfig(LPC_UART_TypeDef *, int, FunctionalState) {}
static inline void PINSEL_ConfigPin(PINSEL_CFG_Type *) {}
static inline uint32_t UART_GetIntId(LPC_UART_TypeDef *) { return 1; }
static inline uint32_t UART_GetLineStatus(LPC_UART_TypeDef *) { return 0; }
static inline uint32_t UART_Receive(LPC_UART_TypeDef *, uint8_t *, uint32_t, TRANSFER_BLOCK_Type) { return 0; }
uint32_t UART_Send(LPC_UART_TypeDef *, uint8_t *data, uint32_t len, TRANSFER_BLOCK_Type);
void UART_SendByte(LPC_UART_TypeDef *, uint8_t byte);

// ---------- mbed classes ----------
typedef enum { P0_0 = 0x000, P0_1, P0_2, P0_3, P0_4, P0_5, P0_6, P0_7, P0_8, P0_9, P0_10, P0_11, P0_15 = 0x00F,
               P0_16, P0_17, P0_18, P0_19, P0_20, P0_21, P0_22, P0_23, P0_24, P0_25, P0_26, P0_27, P0_28, P0_29, P0_30,
               P1_0 = 0x020, P1_18 = 0x032, P1_19, P1_20, P1_21, P1_22, P1_23, P1_24, P1_25, P1_26, P1_27, P1_28, P1_29,
               P2_0 = 0x040, P2_1, P2_2, P2_3, P2_4, P2_5, P2_6, P2_7, P2_8, P2_9, P2_10, P2_11, P2_12, P2_13,
               P3_25 = 0x079, P3_26, P4_28 = 0x09C, P4_29, NC = (int)0xFFFFFFFF } PinName;
typedef enum { Port0 = 0, Port1, Port2, Port3, Port4 } PortName;
static inline PinName port_pin(PortName p, int pin) { return (PinName)((int)p * 32 + pin); }
static inline void NVIC_SystemReset(void) {}
static inline void FIO_SetDir(int, uint32_t, uint8_t) {}
static inline void FIO_SetValue(int, uint32_t) {}
static inline void FIO_ClearValue(int, uint32_t) {}
static inline uint32_t FIO_ReadValue(int) { return 0; }
namespace mbed {
class PwmOut { public: PwmOut(PinName) {} void period(float) {} void period_us(int) {} void write(float) {} float read() { return 0; } void pulsewidth_us(int) {} };
class InterruptIn;
// Every InterruptIn that has a rising-edge handler; sim_fire_pin_rise() calls them the way the GPIO interrupt would.
std::vector<InterruptIn *> &sim_interrupt_pins();
class InterruptIn { public: PinName pin_; std::function<void()> rise_cb_;
    int read() { return 0; }
    InterruptIn(PinName p) : pin_(p) { sim_interrupt_pins().push_back(this); }
    ~InterruptIn() { auto &v = sim_interrupt_pins(); v.erase(std::remove(v.begin(), v.end(), this), v.end()); }
    void rise(void (*f)()) { rise_cb_ = f; } void fall(void (*)()) {}
    template <typename O, typename M> void rise(O o, M m) { rise_cb_ = [o, m]() { (o->*m)(); }; }
    template <typename O, typename M> void fall(O, M) {} void mode(int) {} };
class Timer { uint32_t t0_ = 0; bool on_ = false; public:
    void start() { t0_ = us_ticker_read(); on_ = true; } void stop() { on_ = false; } void reset() { t0_ = us_ticker_read(); }
    int read_us() { return us_ticker_read() - t0_; } float read() { return (us_ticker_read() - t0_) / 1e6f; } int read_ms() { return (us_ticker_read() - t0_) / 1000; } };
class Ticker { public: template <typename T> void attach_us(T, int) {} template <typename O, typename M> void attach(O, M, float) {} void detach() {} };
class Timeout { public: template <typename O, typename M> void attach(O, M, float) {} template <typename O, typename M> void attach_us(O, M, int) {} void detach() {} };
class SPI { public: SPI(PinName, PinName, PinName) {} void format(int, int = 0) {} void frequency(int) {} int write(int) { return 0; } };
class I2C { public: I2C(PinName, PinName) {} void frequency(int) {} int write(int) { return 0; } void start() {} void stop() {} int write(int, const char *, int, bool = false) { return 0; } int read(int, char *, int, bool = false) { return 0; } };
}
using mbed::Ticker; using mbed::Timeout; using mbed::InterruptIn;
struct FunctionPointer { void attach(void (*)()) {} template <typename T> void attach(T *o, void (T::*m)()) {} void call() {} };
struct sim_timer_event { unsigned int timestamp = 0; };
class TimerEvent { public: sim_timer_event event; TimerEvent() {} virtual ~TimerEvent() {} void insert(unsigned int) {} void remove() {} protected: virtual void handler() {} };
static const PinName p5 = (PinName)5;
static const PinName p6 = (PinName)6;
static const PinName p7 = (PinName)7;
static const PinName p8 = (PinName)8;
static const PinName p9 = (PinName)9;
static const PinName p10 = (PinName)10;
static const PinName p11 = (PinName)11;
static const PinName p12 = (PinName)12;
static const PinName p13 = (PinName)13;
static const PinName p14 = (PinName)14;
static const PinName p15 = (PinName)15;
static const PinName p16 = (PinName)16;
static const PinName p17 = (PinName)17;
static const PinName p18 = (PinName)18;
static const PinName p19 = (PinName)19;
static const PinName p20 = (PinName)20;
static const PinName p21 = (PinName)21;
static const PinName p22 = (PinName)22;
static const PinName p23 = (PinName)23;
static const PinName p24 = (PinName)24;
static const PinName p25 = (PinName)25;
static const PinName p26 = (PinName)26;
static const PinName p27 = (PinName)27;
static const PinName p28 = (PinName)28;
static const PinName p29 = (PinName)29;
static const PinName p30 = (PinName)30;
class Timer : public mbed::Timer {};
#define PullUp 0
#define PullDown 3
#define PullNone 2
class DigitalOut { public: DigitalOut(PinName) {} void write(int) {} int read() { return 0; } DigitalOut &operator=(int) { return *this; } operator int() { return 0; } };
class DigitalIn { public: DigitalIn(PinName) {} int read() { return 0; } void mode(int) {} operator int() { return 0; } };
class AnalogIn { public: AnalogIn(PinName) {} float read() { return 0; } };
