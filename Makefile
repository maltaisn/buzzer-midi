# target should be specified when using Makefile using:
# make TARGET=<target>
ifeq ($(TARGET),)
    $(warning No MCU target set, using atmega328p by default)
    TARGET := atmega328p
endif

# target-specific settings
ifeq ($(TARGET),atmega328p)
    MCU := atmega328p
    F_CPU := 16000000
	AVRDUDE_FLAGS += -c arduino
else ifeq ($(TARGET),atmega3208)
    MCU := atmega3208
    F_CPU := 10000000
    CFLAGS += -B$(ATMEGA_TOOLCHAIN_DIR)/gcc/dev/$(MCU) -I$(ATMEGA_TOOLCHAIN_DIR)/include
	AVRDUDE_FLAGS += -c jtag2updi
endif

BUILD_DIR := build
SRC_DIR := src
INCLUDE_DIR := include
BUILD_TARGET := main
MAIN_TARGET := $(BUILD_DIR)/$(BUILD_TARGET)

# ATmega toolchain directory for targeting newer parts.
# It can be downloaded as atpack on Microchip website.
ATMEGA_TOOLCHAIN_DIR := /opt/avr/Atmel.ATmega_DFP

CC := avr-gcc
OBJCOPY := avr-objcopy
OBJDUMP := avr-objdump
AVRDUDE := avrdude

CFLAGS += -Wall -g -std=gnu11 -mmcu=$(MCU) -DF_CPU=$(F_CPU) -Os -I$(INCLUDE_DIR) \
		 -ffunction-sections -fdata-sections -flto $(addprefix -D,$(DEFINES))
LDFLAGS = -Wl,--gc-sections -Wl,--print-memory-usage

AVRDUDE_MCU = $(MCU)
AVRDUDE_PORT := /dev/ttyUSB0
AVRDUDE_BAUD := 57600
AVRDUDE_FLAGS += -v -p $(AVRDUDE_MCU) -P $(AVRDUDE_PORT) -b $(AVRDUDE_BAUD)
AVRDUDE_FLASH := -U flash:w:$(MAIN_TARGET).hex

DEPFLAGS = -MT $@ -MMD -MP -MF $(BUILD_DIR)/$*.d

CSOURCES := $(wildcard $(SRC_DIR)/*.c) $(wildcard $(SRC_DIR)/*/*.c)
ASOURCES := $(wildcard $(SRC_DIR)/*.S) $(wildcard $(SRC_DIR)/*/*.S)
OBJECTS := $(addprefix $(BUILD_DIR)/, $(CSOURCES:.c=.o)) $(addprefix $(BUILD_DIR)/, $(ASOURCES:.S=.o))
DEPS := $(addprefix $(BUILD_DIR)/, $(CSOURCES:.c=.d)) $(addprefix $(BUILD_DIR)/, $(ASOURCES:.S=.d))

-include $(DEPS)

.PHONY: clean upload

.PRECIOUS: $(BUILD_DIR)/%.o
.PRECIOUS: $(BUILD_DIR)/%.d

all: $(MAIN_TARGET).hex

$(BUILD_DIR)/%.o: %.c
$(BUILD_DIR)/%.o: %.c Makefile
	@mkdir -p $(@D)
	$(CC) $(CFLAGS) $(DEPFLAGS) -c -o $@ $<

%.elf: $(OBJECTS)
	$(CC) $(LDFLAGS) $(CFLAGS) $^ -o $@

%.hex: %.elf
	$(OBJCOPY) -O ihex $< $@

disasm: $(BUILD_DIR)/$(BUILD_TARGET).elf
	$(OBJDUMP) -D $< > $(BUILD_DIR)/$(BUILD_TARGET).S

size: $(MAIN_TARGET).elf
	$(OBJDUMP) -Pmem-usage $^

upload: $(MAIN_TARGET).hex
	$(AVRDUDE) $(AVRDUDE_FLAGS) $(AVRDUDE_FLASH)

clean:
	rm -rf $(BUILD_DIR)
