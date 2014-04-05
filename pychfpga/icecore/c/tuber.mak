default: tuber
.PHONY: tuber clean

tuber: libiceboard_tuber.so

SRCS :=	iceboard.c				\
	iceboard_hw.c				\
	fpga.c					\
	mezz.c					\
	hk.c					\
	base64.c				\
	runtime_tuber.c support_system.c
HDRS :=	iceboard.h iceboard_hw.h runtime.h
OBJS := $(SRCS:.c=.o)
$(OBJS): $(HDRS)

VPATH=../../src:../../include

libiceboard_tuber.so: $(OBJS) $(HDRS)
	$(CC) $(LDFLAGS) -shared -o $@ $(OBJS)	\
		-lm -ljansson -ltuber -lssl -lcrypto

CFLAGS += -g -fPIC -Wall -Werror -I../../include
LDFLAGS += -g

clean:
	rm -f $(OBJS) libiceboard_tuber.so
