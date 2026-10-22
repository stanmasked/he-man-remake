# Stage183: isolated real-time clock probe; no original game assets.
.SUFFIXES:
.DEFAULT_GOAL := all
ifeq ($(strip $(DEVKITPRO)),)
$(error DEVKITPRO is unset)
endif
DEVKITA64 ?= $(DEVKITPRO)/devkitA64
CC := $(DEVKITA64)/bin/aarch64-none-elf-gcc
ELF2NRO ?= $(DEVKITPRO)/tools/bin/elf2nro
TARGET := heman_realtime_clock_probe
ARCH := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
CFLAGS := -std=gnu99 -O2 -Wall -Wextra -Werror $(ARCH) \
          -I$(DEVKITPRO)/libnx/include -I../native/include -I../native/clock -D__SWITCH__
LDFLAGS := -specs=$(DEVKITPRO)/libnx/switch.specs $(ARCH) \
           -Wl,--gc-sections -L$(DEVKITPRO)/libnx/lib
SOURCES := source/main.c ../native/clock/heman_app_tick_clock.c \
           ../native/src/heman_app_tick_scheduler.c \
           ../native/src/heman_sprite_clock.c
.PHONY: all clean
all: $(TARGET).nro
$(TARGET).elf: $(SOURCES)
	$(CC) $(CFLAGS) $(SOURCES) $(LDFLAGS) -lnx -lm -o $@
$(TARGET).nro: $(TARGET).elf
	$(ELF2NRO) $< $@
clean:
	rm -f $(TARGET).elf $(TARGET).nro
