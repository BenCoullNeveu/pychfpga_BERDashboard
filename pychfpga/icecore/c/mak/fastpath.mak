default: fastpath
.PHONY: tuber clean

SRCS :=	tuber_fastpath.c tuber_server.c
HDRS :=	tuber.h tuber_server.h

OBJS := $(SRCS:.c=.o)
$(OBJS): $(HDRS)

VPATH=../../src:../../include

fastpath: $(OBJS) $(HDRS)
	$(CC) $(LDFLAGS) -o $@ $(OBJS) -ljansson -lelf -lmicrohttpd -ldl

CFLAGS += -g -fpic -Wall -Werror -Wno-unused-function -D_GNU_SOURCE -I../../include
LDFLAGS += -g

clean:
	rm -f $(OBJS) fastpath
