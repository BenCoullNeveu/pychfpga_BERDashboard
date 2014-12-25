default: fastpath
.PHONY: clean default

SRCS :=	tuber_fastpath.c tuber_server.c runtime_tuber.c

VPATH=../../src:../../include

fastpath: $(SRCS:.c=.o)
	$(CC) $(LDFLAGS) -o $@ $^ -ljansson -lelf -lmicrohttpd -ldl -lpthread

CFLAGS += -g -fpic -Wall -Werror -Wno-unused-function -D_GNU_SOURCE -I../../include
LDFLAGS += -g -Wl,--dynamic-list=../../mak/fastpath.txt

clean:
	rm -f *.o fastpath

# Dependencies. Adapted from scottmcpeak.com/autodepend/autodepend.html
-include $(SRCS:.c=.d)
%.o: %.c
	$(CC) -c $(CFLAGS) $< -o $*.o
	$(CC) -MM $(CFLAGS) $< > $*.d
	@cp -f $*.d $*.d.tmp
	@sed -e 's/.*://' -e 's/\\$$//' < $*.d.tmp | fmt -1 | \
	  sed -e 's/^ *//' -e 's/$$/:/' >> $*.d
	@rm -f $*.d.tmp
