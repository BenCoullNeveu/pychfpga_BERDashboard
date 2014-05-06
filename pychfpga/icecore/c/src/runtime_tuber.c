#include "runtime.h"
#include <tuber.h>
#include <stdarg.h>

#define ERRBUF_SIZE 256

static int error_num = 0;
static char error_buf[ERRBUF_SIZE];

void tuber_voops(const char *fmt, va_list ap);

void oops(const char *fmt, ...) {
	va_list ap;

	va_start(ap, fmt);
	tuber_voops(fmt, ap);
	va_end(ap);
}

void tuber_error_clear(void) {
	error_num = 0;
}

char *tuber_error_fetch(void) {
	return(error_num ? error_buf : NULL);
}

void tuber_voops(const char *fmt, va_list ap) {
	va_list ap_copy;

	error_num = 1;
	va_copy(ap_copy, ap);
	vsnprintf(error_buf, ERRBUF_SIZE, fmt, ap_copy);
	va_end(ap_copy);
}
