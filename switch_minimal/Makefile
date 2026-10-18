# Minimal independent libnx framebuffer guest; no game modules or media.
.SUFFIXES:
.DEFAULT_GOAL := all
ifeq ($(strip $(DEVKITPRO)),)
$(error DEVKITPRO is unset)
endif
DEVKITA64 ?= $(DEVKITPRO)/devkitA64
CC := $(DEVKITA64)/bin/aarch64-none-elf-gcc
ELF2NRO ?= $(DEVKITPRO)/tools/bin/elf2nro
TARGET := heman_minimal_guest_probe
ARCH := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
CFLAGS := -std=gnu99 -O2 -Wall -Wextra -Werror $(ARCH) -I$(DEVKITPRO)/libnx/include -D__SWITCH__
LDFLAGS := -specs=$(DEVKITPRO)/libnx/switch.specs $(ARCH) -Wl,--gc-sections -L$(DEVKITPRO)/libnx/lib
.PHONY: all clean
all: $(TARGET).nro
$(TARGET).elf: source/main.c
	$(CC) $(CFLAGS) $< $(LDFLAGS) -lnx -lm -o $@
$(TARGET).nro: $(TARGET).elf
	$(ELF2NRO) $< $@
clean:
	rm -f $(TARGET).elf $(TARGET).nro
