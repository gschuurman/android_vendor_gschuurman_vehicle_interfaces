cmake_minimum_required(VERSION 3.13)

# Car radio peripheral board firmware (RP2350B, board rev 0.6).
# Build: see README.md. Needs the Pico SDK 2.x (PICO_SDK_PATH, or PICO_SDK_FETCH_FROM_GIT=1).
set(PICO_PLATFORM rp2350-arm-s)
set(PICO_BOARD carradio_rev06)
set(PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/boards)

include(pico_sdk_import.cmake)

project(carradio_mcu C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

add_executable(carradio_mcu
    src/main.c
    src/power_sm.c
    src/nmea.c
    src/periph.c
    src/usb_link.c
    src/usb_descriptors.c
)

target_include_directories(carradio_mcu PRIVATE
    src
    ${CMAKE_CURRENT_LIST_DIR}/../protocol
)

target_compile_options(carradio_mcu PRIVATE -Wall -Wextra -Wno-unused-parameter)

target_link_libraries(carradio_mcu
    pico_stdlib
    pico_unique_id
    hardware_adc
    hardware_i2c
    hardware_pwm
    hardware_uart
    hardware_watchdog
    tinyusb_device
)

# No stdio over USB or UART: TinyUSB is driven directly (no 1200-baud reset trick, no CDC).
pico_enable_stdio_usb(carradio_mcu 0)
pico_enable_stdio_uart(carradio_mcu 0)

# Bootrom IMAGE_DEF version, inverted (0xFFFF - x) like the A/B update work on top of 0.3.0:
# on an MCU that carries the A/B partition table a BOOTSEL install of this image lands in the
# other slot, and with the inverted version a normal boot picks it over a newer 0.3.x there.
# Keep in sync with FW_MAJOR/FW_MINOR/FW_PATCH in src/main.c.
pico_set_binary_version(carradio_mcu MAJOR 65535 MINOR 65022)  # 0.2.1
pico_hash_binary(carradio_mcu)
pico_add_extra_outputs(carradio_mcu)
