# If we're invoked from a Yocto recipe, then TARGET_ARCH is set. Otherwise,
# populate it assuming we're not cross-compiling.
ifndef TARGET_ARCH
ifdef FORCE_CROSS
TARGET_ARCH=arm
else
TARGET_ARCH=$(shell uname -m)
endif
endif

# Make sure we understand TARGET_ARCH.
ifneq ($(findstring $(TARGET_ARCH),$(TARGET_ARCHES)),)
# success!
else
$(error Unrecognized TARGET_ARCH $(TARGET_ARCH)! Supported: $(TARGET_ARCHES))
endif

# If we're cross-compiling, Yocto ordinarily configures BUILD_CC and CC. We
# provide fallbacks here in case we're cross-compiling outside of a Yocto
# tree. Don't rely on these!
ifdef FORCE_CROSS
export BUILD_CC		= gcc
export CROSS_COMPILE	= arm-buildroot-linux-gnueabihf-
export CC		= $(CROSS_COMPILE)gcc
export LD		= $(CROSS_COMPILE)ld
export AS		= $(CROSS_COMPILE)as
export RANLIB		= $(CROSS_COMPILE)ranlib
export CXX		= $(CROSS_COMPILE)c++
export CPP		= $(CROSS_COMPILE)cpp
export STRIP		= $(CROSS_COMPILE)strip
export OBJDUMP		= $(CROSS_COMPILE)objdump
export CFLAGS		+= -O2 -Wall -Werror -fPIC
endif
