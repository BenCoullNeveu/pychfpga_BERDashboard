#include "runtime.h"
#include <tuber.h>

void oops(const char *fmt, ...) {
	va_list ap;

	va_start(ap, fmt);
	tuber_voops(fmt, ap);
	va_end(ap);
}

void error_clear(void) {
	tuber_error_clear();
}

char *error_fetch(void) {
	return tuber_error_fetch();
}
