LIB := libiceboard.so
default: $(LIB)
.PHONY: clean default

SRCS :=	iceboard.c				\
	iceboard_hw.c				\
	iceboard_constants.c			\
	iceboard_fpga.c				\
	iceboard_mezz.c				\
	iceboard_hk.c				\
	base64.c				\
	runtime_tuber.c				\
	support_system.c			\
	i2c_eeprom.c				\
	ipmi_frui.c

HDRS :=	iceboard.h				\
	iceboard_hw.h				\
	runtime.h				\
	iceboard_constants.h			\
	i2c_eeprom.h				\
	ipmi_frui.c

OBJS := $(SRCS:.c=.o)
$(OBJS): $(HDRS)

VPATH=../../src:../../include

$(LIB): $(OBJS) $(HDRS)
	$(CC) $(LDFLAGS) -shared -o $@ $(OBJS)	\
		-lm -ljansson -lssl -lcrypto

CFLAGS += -g -fPIC -Wall -Werror -Wno-unused-function -D_GNU_SOURCE -I../../include
LDFLAGS += -g

clean:
	rm -f $(OBJS) $(LIB)
