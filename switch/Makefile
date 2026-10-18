# Experimental libnx/devkitA64 target: synthetic C99 console probe ONLY.
# Requires preinstalled devkitPro Switch SDK. No copyrighted assets.
.SUFFIXES:
.DEFAULT_GOAL := all

ifeq ($(strip $(DEVKITPRO)),)
$(error DEVKITPRO is unset; install devkitPro switch-dev and export DEVKITPRO)
endif

DEVKITA64 ?= $(DEVKITPRO)/devkitA64
CC := $(DEVKITA64)/bin/aarch64-none-elf-gcc
ELF2NRO ?= $(DEVKITPRO)/tools/bin/elf2nro
TARGET := heman_core_probe
ROOT := $(abspath ..)
ARCH := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
SOURCES := source/main.c source/probe_view.c source/probe_selfcheck.c $(ROOT)/native/src/heman_core.c $(ROOT)/native/src/heman_mask.c $(ROOT)/native/src/heman_combat.c $(ROOT)/native/src/heman_session.c
CFLAGS := -std=gnu99 -O2 -g -Wall -Wextra -ffunction-sections -fdata-sections $(ARCH) \
          -Isource -I$(ROOT)/native/include -I$(DEVKITPRO)/libnx/include -D__SWITCH__
LDFLAGS := -specs=$(DEVKITPRO)/libnx/switch.specs $(ARCH) \
           -Wl,--gc-sections -L$(DEVKITPRO)/libnx/lib

.PHONY: all clean check-toolchain
all: check-toolchain $(TARGET).nro

check-toolchain:
	@test -x "$(CC)" || { echo "devkitA64 compiler not installed: $(CC)" >&2; exit 1; }
	@test -x "$(ELF2NRO)" || { echo "elf2nro missing: $(ELF2NRO)" >&2; exit 1; }
	@test -f "$(DEVKITPRO)/libnx/switch.specs" || { echo "libnx missing" >&2; exit 1; }

$(TARGET).elf: $(SOURCES)
	$(CC) $(CFLAGS) $(SOURCES) $(LDFLAGS) -lnx -lm -o $@

$(TARGET).nro: $(TARGET).elf
	$(ELF2NRO) $< $@

clean:
	rm -f $(TARGET).elf $(TARGET).nro
