# Synthetic Stage172 sprite clock probe; no original He-Man code/assets.
.SUFFIXES:
.DEFAULT_GOAL := all
ifeq ($(strip $(DEVKITPRO)),)
$(error DEVKITPRO is unset)
endif
DEVKITA64 ?= $(DEVKITPRO)/devkitA64
CC := $(DEVKITA64)/bin/aarch64-none-elf-gcc
ELF2NRO ?= $(DEVKITPRO)/tools/bin/elf2nro
TARGET := heman_sprite_clock_probe
ARCH := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
CFLAGS := -std=gnu99 -O2 -Wall -Wextra -Werror $(ARCH) -I$(DEVKITPRO)/libnx/include -I../native/include -D__SWITCH__
LDFLAGS := -specs=$(DEVKITPRO)/libnx/switch.specs $(ARCH) -Wl,--gc-sections -L$(DEVKITPRO)/libnx/lib
.PHONY: all clean
all: $(TARGET).nro
$(TARGET).elf: source/main.c ../native/src/heman_sprite_clock.c ../native/src/heman_app_tick_scheduler.c ../native/include/heman_sprite_clock.h ../native/include/heman_app_tick_scheduler.h
	$(CC) $(CFLAGS) source/main.c ../native/src/heman_sprite_clock.c ../native/src/heman_app_tick_scheduler.c $(LDFLAGS) -lnx -lm -o $@
$(TARGET).nro: $(TARGET).elf
	$(ELF2NRO) $< $@
clean:
	rm -f $(TARGET).elf $(TARGET).nro
