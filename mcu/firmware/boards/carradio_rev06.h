// Pico SDK board header for the car radio peripheral board, rev 0.6.
// RP2350B (QFN-80) with a 16 MB W25Q128JV QSPI flash (U21) and a 12 MHz crystal (Y3),
// as on the Raspberry Pi Pico 2 reference design.
#ifndef _BOARDS_CARRADIO_REV06_H
#define _BOARDS_CARRADIO_REV06_H

pico_board_cmake_set(PICO_PLATFORM, rp2350)

#define PICO_RP2350A 0  // RP2350B: 48 GPIOs

// No default UART: the firmware does not use stdio.
#define PICO_DEFAULT_LED_PIN 21

#define PICO_BOOT_STAGE2_CHOOSE_W25Q080 1
#ifndef PICO_FLASH_SPI_CLKDIV
#define PICO_FLASH_SPI_CLKDIV 2
#endif

pico_board_cmake_set_default(PICO_FLASH_SIZE_BYTES, (16 * 1024 * 1024))
#ifndef PICO_FLASH_SIZE_BYTES
#define PICO_FLASH_SIZE_BYTES (16 * 1024 * 1024)
#endif

// Pico 2 crystal: 12 MHz ABM8-272-T3 with the same load caps and 1k series resistor.
#ifndef PICO_XOSC_STARTUP_DELAY_MULTIPLIER
#define PICO_XOSC_STARTUP_DELAY_MULTIPLIER 64
#endif

pico_board_cmake_set_default(PICO_RP2350_A2_SUPPORTED, 1)
#ifndef PICO_RP2350_A2_SUPPORTED
#define PICO_RP2350_A2_SUPPORTED 1
#endif

#endif
