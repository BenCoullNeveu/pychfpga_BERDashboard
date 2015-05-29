#include "runtime.h"
#include <tuber.h>
#include <stdarg.h>
#include <pthread.h>

/* To flag errors in a safe manner, we use POSIX thread-local storage. */

#define ERRBUF_SIZE 256

static pthread_key_t error_key;
static pthread_once_t error_key_once = PTHREAD_ONCE_INIT;

static void error_alloc(void) {
	pthread_key_create(&error_key, free);
}

void tuber_voops(const char *fmt, va_list ap) {
	va_list ap_copy;
	char *e;

	pthread_once(&error_key_once, error_alloc);

	if(!(e = pthread_getspecific(error_key))) {
		e = calloc(ERRBUF_SIZE, 1);
		pthread_setspecific(error_key, e);
	}

	va_copy(ap_copy, ap);
	vsnprintf(e, ERRBUF_SIZE, fmt, ap_copy);
	va_end(ap_copy);
}

void oops(const char *fmt, ...) {
	va_list ap;

	va_start(ap, fmt);
	tuber_voops(fmt, ap);
	va_end(ap);
}

void tuber_error_clear(void) {
	char *e = (char *)pthread_getspecific(error_key);
	if(e)
		e[0] = 0;
}

char *tuber_error_fetch(void) {
	char *e = (char*)pthread_getspecific(error_key);
	return((e && e[0]) ? e : NULL);
}
