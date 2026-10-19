# Independent graphical 640x360 RGBA8888 test NRO (all original shapes).
.SUFFIXES:
.DEFAULT_GOAL := all
ifeq ($(strip $(DEVKITPRO)),)
$(error DEVKITPRO is unset)
endif
DEVKITA64 ?= $(DEVKITPRO)/devkitA64
CC := $(DEVKITA64)/bin/aarch64-none-elf-gcc
ELF2NRO ?= $(DEVKITPRO)/tools/bin/elf2nro
ROOT := $(abspath ..)
TARGET := heman_raster_probe
ARCH := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
SOURCES := source/main.c $(ROOT)/raster/raster_scene.c \
           $(ROOT)/native/src/heman_core.c $(ROOT)/native/src/heman_mask.c \
           $(ROOT)/native/src/heman_combat.c $(ROOT)/native/src/heman_session.c \
           $(ROOT)/switch/source/probe_view.c \
           $(ROOT)/switch/source/probe_selfcheck.c \
           $(ROOT)/switch/source/session_selftest.c \
           $(ROOT)/switch/source/runtime_replay.c
CFLAGS := -std=gnu99 -O2 -Wall -Wextra -Werror $(ARCH) \
          -I$(ROOT)/native/include -I$(ROOT)/raster \
          -I$(ROOT)/switch/source -I$(DEVKITPRO)/libnx/include -D__SWITCH__
# Opt-in, asset-free attack scenario. The normal NRO is unchanged.
ifeq ($(ATTACK_PROBE),1)
CFLAGS += -DHM_ATTACK_PROBE=1
endif
ifeq ($(DAMAGE_PROBE),1)
CFLAGS += -DHM_DAMAGE_PROBE=1
endif
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
