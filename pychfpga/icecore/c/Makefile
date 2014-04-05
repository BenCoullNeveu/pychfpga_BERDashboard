# Figure out which environment we're targeting. This sets TARGET_ARCH.
TARGET_ARCHES := x86_64 arm
export BASE_DIR=$(CURDIR)
include arch.mak

.PHONY: clean $(TARGET_ARCHES)

default: x86_64

export CFLAGS += -I$(BASE_DIR)/include -fno-strict-aliasing

clean:
	$(MAKE) -C x86_64 clean
	$(MAKE) -C arm clean

$(TARGET_ARCHES):
	$(MAKE) -C $@

