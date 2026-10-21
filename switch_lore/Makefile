# Standalone, dev-only, original-assets-free native lore integration NRO.
.SUFFIXES:
.DEFAULT_GOAL := all
ifeq ($(strip $(DEVKITPRO)),)
$(error DEVKITPRO is unset)
endif
DEVKITA64 ?= $(DEVKITPRO)/devkitA64
CC := $(DEVKITA64)/bin/aarch64-none-elf-gcc
ELF2NRO ?= $(DEVKITPRO)/tools/bin/elf2nro
ROOT := $(abspath ..)
TARGET := heman_level11_lore_lab
ARCH := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
SOURCES := source/main.c \
           $(ROOT)/native/src/heman_core.c \
           $(ROOT)/native/src/heman_mask.c \
           $(ROOT)/native/src/heman_level11_lore.c \
           $(ROOT)/native/src/heman_level11_native_contacts.c \
           $(ROOT)/native/src/heman_level11_native_session.c \
           $(ROOT)/native/src/heman_level11_snapshot.c \
           $(ROOT)/native/src/heman_level11_lab.c
CFLAGS := -std=gnu99 -O2 -Wall -Wextra -Werror $(ARCH) \
          -I$(ROOT)/native/include -I$(DEVKITPRO)/libnx/include -D__SWITCH__
LDFLAGS := -specs=$(DEVKITPRO)/libnx/switch.specs $(ARCH) \
           -Wl,--gc-sections -L$(DEVKITPRO)/libnx/lib
.PHONY: all clean
all: $(TARGET).nro
$(TARGET).elf: $(SOURCES)
	$(CC) $(CFLAGS) $(SOURCES) $(LDFLAGS) -lnx -lm -o $@
$(TARGET).nro: $(TARGET).elf
	$(ELF2NRO) $< $@
clean:
	rm -f $(TARGET).elf $(TARGET).nro
