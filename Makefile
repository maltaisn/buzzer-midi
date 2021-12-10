ifeq ($(TARGET),)
    $(warning No MCU target set, using atmega328p by default)
    TARGET := atmega328p
endif

ifeq ($(TARGET),atmega328p)
    MCU = atmega328p
    F_CPU := 16000000
else ifeq ($(TARGET),atmega3208)
    MCU = atmega3208
    F_CPU := 10000000
    CFLAGS += -B$(ATMEGA_TOOLCHAIN_DIR)/gcc/dev/$(MCU) -I$(ATMEGA_TOOLCHAIN_DIR)/include
endif

BUILD_DIR := build
SRC_DIR := src
INCLUDE_DIR := include
BUILD_TARGET := main

ATMEGA_TOOLCHAIN_DIR := /opt/avr/Atmel.ATmega_DFP

CC := avr-gcc
OBJCOPY := avr-objcopy
OBJDUMP := avr-objdump
AVRDUDE := avrdude

CFLAGS += -Wall -g -std=gnu11 -mmcu=$(MCU) -DF_CPU=$(F_CPU) -Os -I$(INCLUDE_DIR) \
		 -ffunction-sections -fdata-sections -flto $(addprefix -D,$(DEFINES))
LDFLAGS = -Wl,--gc-sections

AVRDUDE_MCU = $(MCU)
AVRDUDE_PORT := /dev/ttyUSB0
AVRDUDE_BAUD := 57600
AVRDUDE_FLAGS := -v -p $(AVRDUDE_MCU) -c arduino -P $(AVRDUDE_PORT) -b $(AVRDUDE_BAUD) -D
AVRDUDE_FLASH := -U flash:w:build/main.hex

DEPFLAGS = -MT $@ -MMD -MP -MF $(BUILD_DIR)/$*.d

CSOURCES := $(wildcard $(SRC_DIR)/*.c) $(wildcard $(SRC_DIR)/*/*.c)
ASOURCES := $(wildcard $(SRC_DIR)/*.S) $(wildcard $(SRC_DIR)/*/*.S)
OBJECTS := $(addprefix $(BUILD_DIR)/, $(CSOURCES:.c=.o)) $(addprefix $(BUILD_DIR)/, $(ASOURCES:.S=.o))
DEPS := $(addprefix $(BUILD_DIR)/, $(CSOURCES:.c=.d)) $(addprefix $(BUILD_DIR)/, $(ASOURCES:.S=.d))
MAIN_TARGET := $(BUILD_DIR)/$(BUILD_TARGET)

-include $(DEPS)

.PHONY: clean upload

.PRECIOUS: $(BUILD_DIR)/%.o
.PRECIOUS: $(BUILD_DIR)/%.d

all: $(MAIN_TARGET).hex

$(BUILD_DIR)/%.o: %.c
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(DEPFLAGS) -c -o $@ $<

%.elf: $(OBJECTS)
	$(CC) $(LDFLAGS) $(CFLAGS) $^ -o $@

%.hex: %.elf
	$(OBJCOPY) -O ihex $< $@
	$(MAKE) size

disasm: $(BUILD_DIR)/$(BUILD_TARGET).elf
	$(OBJDUMP) -d $< > $(BUILD_DIR)/$(BUILD_TARGET).S

size: $(MAIN_TARGET).elf
	$(OBJDUMP) -Pmem-usage $^

upload: $(MAIN_TARGET).hex
	$(AVRDUDE) $(AVRDUDE_FLAGS) $(AVRDUDE_FLASH)

clean:
	rm -rf $(BUILD_DIR)
