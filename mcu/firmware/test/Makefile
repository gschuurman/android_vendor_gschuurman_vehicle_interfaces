# Host tests for the hardware-independent parts: make -C test
CFLAGS = -std=c11 -Wall -Wextra -Werror -g -I../src -I../../protocol
all: test_power_sm test_nmea test_usb_link
	./test_power_sm
	./test_nmea
	./test_usb_link
test_power_sm: test_power_sm.c ../src/power_sm.c
	$(CC) $(CFLAGS) -o $@ $^
test_nmea: test_nmea.c ../src/nmea.c
	$(CC) $(CFLAGS) -o $@ $^ -lm
test_usb_link: test_usb_link.c ../src/usb_link.c
	$(CC) $(CFLAGS) -Istub -Wno-unused-parameter -o $@ $^
clean:
	rm -f test_power_sm test_nmea test_usb_link
