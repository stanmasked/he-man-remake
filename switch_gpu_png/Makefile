# Stage226: isolated deko3d GPU transfer; not Stage225 CPU framebuffer.
.SUFFIXES:
.DEFAULT_GOAL := all
ifeq ($(strip $(DEVKITPRO)),)
$(error DEVKITPRO is required)
endif
DEVKITA64 ?= $(DEVKITPRO)/devkitA64
CC := $(DEVKITA64)/bin/aarch64-none-elf-gcc
CXX := $(DEVKITA64)/bin/aarch64-none-elf-g++
ELF2NRO ?= $(DEVKITPRO)/tools/bin/elf2nro
UAM ?= $(DEVKITPRO)/tools/bin/uam
ROMFS := romfs
VERT_SHADER := $(ROMFS)/shaders/padded_texture_vsh.dksh
FRAG_SHADER := $(ROMFS)/shaders/padded_texture_fsh.dksh
SHADER_BINARIES := $(VERT_SHADER) $(FRAG_SHADER)
ROOT := $(abspath ..)
ARCH := -march=armv8-a+crc+crypto -mtune=cortex-a57 -mtp=soft -fPIE
COMMON := -O2 -Wall -Wextra -Werror $(ARCH) -D__SWITCH__ \
          -I$(ROOT)/native/include -I$(DEVKITPRO)/libnx/include
CFLAGS := -std=c99 $(COMMON)
# libnx C headers use designated partial initializers accepted by the SDK;
# suppress only this compiler warning under C++ while keeping other -Werror.
CXXFLAGS := -std=gnu++17 -fno-exceptions -fno-rtti -Wno-missing-field-initializers $(COMMON)
LDFLAGS := -specs=$(DEVKITPRO)/libnx/switch.specs $(ARCH) \
           -Wl,--gc-sections -L$(DEVKITPRO)/libnx/lib
TARGET := heman_deko_png_transfer

.PHONY: all clean
all: $(TARGET).nro
native_upload.o: $(ROOT)/native/src/heman_native_png_upload.c \
                 $(ROOT)/native/include/heman_native_png_upload.h
	$(CC) $(CFLAGS) -c $< -o $@
$(TARGET).elf: source/main.cpp native_upload.o
	$(CXX) $(CXXFLAGS) source/main.cpp native_upload.o \
	  $(LDFLAGS) -ldeko3d -lnx -lm -o $@
$(ROMFS)/shaders:
	mkdir -p $@
$(VERT_SHADER): shaders/padded_texture_vsh.glsl | $(ROMFS)/shaders
	$(UAM) -s vert -o $@ $<
$(FRAG_SHADER): shaders/padded_texture_fsh.glsl | $(ROMFS)/shaders
	$(UAM) -s frag -o $@ $<
$(TARGET).nro: $(TARGET).elf $(SHADER_BINARIES)
	$(ELF2NRO) $< $@ --romfsdir=$(abspath $(ROMFS))
clean:
	rm -f $(TARGET).elf $(TARGET).nro native_upload.o
	rm -f $(SHADER_BINARIES)
