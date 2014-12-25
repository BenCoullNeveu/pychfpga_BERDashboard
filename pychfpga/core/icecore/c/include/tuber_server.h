#ifndef __TUBER_SERVER_H__
#define __TUBER_SERVER_H__

#include "tuber.h"

extern int tuber_verbose;

#define fatal(fmt, ...) tuber_server_fatal_call(fmt "\n" , ## __VA_ARGS__) 
#define warn(fmt, ...) ({ if(tuber_verbose) { fprintf(stderr, fmt "\n" , ## __VA_ARGS__); }})
#define debug(fmt, ...) ({ if(tuber_verbose) { fprintf(stderr, fmt "\n" , ## __VA_ARGS__); }})

struct tuber_library_t;

void tuber_server_fatal_call(const char *fmt, ...);

void tuber_server_init(void);
void tuber_server_cleanup(void);

int tuber_register_library(const char *filename);
int tuber_unregister_library(const char *filename);

tuber_object_entry_t *tuber_server_lookup_object(const char *);
json_t *tuber_server_invoke(json_t *);

#endif

