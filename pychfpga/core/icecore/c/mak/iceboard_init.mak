default: iceboard_init
.PHONY: clean default

SRCS :=	ipmi_frui.c		\
	iceboard_init.c		\
	iceboard_sysinfo.c	\
	support_system.c	\
	runtime_standalone.c

VPATH=../../src:../../include

iceboard_init: $(SRCS:.c=.o)
	$(CC) $(LDFLAGS) -o $@ $^

CFLAGS += -g -fpic -Wall -Werror -Wno-unused-function -D_GNU_SOURCE -I../../include
LDFLAGS += -g

clean:
	rm -f *.o iceboard_init

# Dependencies. Adapted from scottmcpeak.com/autodepend/autodepend.html
-include $(SRCS:.c=.d)
%.o: %.c
	$(CC) -c $(CFLAGS) $< -o $*.o
	$(CC) -MM $(CFLAGS) $< > $*.d
	@cp -f $*.d $*.d.tmp
	@sed -e 's/.*://' -e 's/\\$$//' < $*.d.tmp | fmt -1 | \
	  sed -e 's/^ *//' -e 's/$$/:/' >> $*.d
	@rm -f $*.d.tmp
