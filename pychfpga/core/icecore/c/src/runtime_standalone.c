#include <stdarg.h>
#include <stdlib.h>
#include <stdio.h>

void oops(const char *fmt, ...) {
	va_list ap;

	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	va_end(ap);
	fputc('\n', stderr);
}

void error_clear(void) {
}

char *error_fetch(void) {
	return(NULL);
}

