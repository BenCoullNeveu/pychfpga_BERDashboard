#ifndef __RUNTIME_H__
#define __RUNTIME_H__

#include <boost/preprocessor.hpp>

#define fatal(fmt, ...) \
	fatal_call(__FILE__ ":" BOOST_PP_STRINGIZE(__LINE__) " " fmt "\n" , ## __VA_ARGS__)

void fatal_call(const char *fmt, ...);
void oops(const char *fmt, ...);
void error_clear(void);
char *error_fetch(void);

#endif

