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
           $(ROOT)/raster/pause_overlay.c $(ROOT)/raster/stage_marker.c \
           $(ROOT)/raster/dash_hud.c $(ROOT)/raster/finale_overlay.c \
           $(ROOT)/raster/air_smash_hud.c $(ROOT)/raster/third_room_marker.c \
           $(ROOT)/native/src/heman_core.c $(ROOT)/native/src/heman_mask.c \
           $(ROOT)/native/src/heman_combat.c $(ROOT)/native/src/heman_session.c \
           $(ROOT)/native/src/heman_pause.c $(ROOT)/native/src/heman_stage_chain.c \
           $(ROOT)/native/src/heman_dash.c $(ROOT)/native/src/heman_finale.c \
           $(ROOT)/native/src/heman_air_smash.c \
           $(ROOT)/native/src/heman_three_room_chain.c \
           $(ROOT)/native/src/heman_synthetic_room3.c \
           $(ROOT)/native/src/heman_synthetic_room2.c \
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
# Opt-in two-room test campaign; base NRO stays one synthetic level.
ifeq ($(CHAIN_PROBE),1)
CFLAGS += -DHM_LEVEL_CHAIN_PROBE=1
endif
# Separate opt-in second-room ZL strike. Normal NRO and existing
# NeXium A/X/B/ZR scripts preserve their previous input mappings.
ifeq ($(AIR_SMASH_PROBE),1)
ifeq ($(CHAIN_PROBE),1)
CFLAGS += -DHM_AIR_SMASH_PROBE=1
else
$(error AIR_SMASH_PROBE requires CHAIN_PROBE=1)
endif
endif
# Opt-in 0->1->2 room sequence. Existing one-/two-room NRO flows
# are unaffected and source-authored FINISH moves to the third room only.
ifeq ($(THREE_ROOM_PROBE),1)
ifeq ($(CHAIN_PROBE),1)
CFLAGS += -DHM_THREE_ROOM_PROBE=1
else
$(error THREE_ROOM_PROBE requires CHAIN_PROBE=1)
endif
endif
# Stage 049 test-only checkpoint guest NRO; normal graphics unchanged.
ifeq ($(CHECKPOINT_PROBE),1)
CFLAGS += -DHM_CHECKPOINT_PROBE=1
endif
# Opt-in real NeXium D-pad → native HM_EXIT → visible CLEAR proof.
ifeq ($(EXIT_PROBE),1)
CFLAGS += -DHM_EXIT_PROBE=1
endif
# Opt-in checkpoint + native contact-defeat scenario for real NeXium HID.
ifeq ($(CHECKPOINT_DEFEAT_PROBE),1)
CFLAGS += -DHM_CHECKPOINT_PROBE=1 -DHM_CHECKPOINT_DEFEAT_PROBE=1
endif
# Stage209: standalone synthetic textured-quad CPU-reference guest.
# The ordinary raster NRO and all existing probe configurations stay unchanged.
ifeq ($(TEXTURE_PROBE),1)
TARGET := heman_texture_probe
SOURCES := source/texture_probe.c $(ROOT)/native/src/heman_textured_quad_reference.c
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
