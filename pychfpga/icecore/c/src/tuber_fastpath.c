#ifndef _GNU_SOURCE
# define _GNU_SOURCE
#endif

#include <string.h>
#include <getopt.h>
#include <regex.h>
#include <sys/stat.h>
#include <dirent.h>
#include <microhttpd.h>
#include <unistd.h>
#include <sys/inotify.h>

#include "tuber.h"
#include "tuber_server.h"

#define DEFAULT_PORT		8888
#define DEFAULT_MOD_ROOT	"/usr/share/tuber"
#define DEFAULT_WEB_ROOT	"/home/www"

static char *web_root = DEFAULT_WEB_ROOT;
static char *mod_root = DEFAULT_MOD_ROOT;

int tuber_verbose = 0;

/* Forward definitions for handler_ent, handler */
struct handler_ent;
typedef int(*handler_t)(struct handler_ent *, void*,
		struct MHD_Connection *,
		const char *, const char *, const char *,
		const char *, size_t *, void **);
struct handler_ent {
	const char *method;
	const char *url_regex;
	regex_t url_regex_c;

	handler_t handler;

	struct header {
		char *name;
		char *value;
	} *headers;

	void *extra;
};

typedef struct {
	struct MHD_PostProcessor *pp;

	TAILQ_HEAD(input_head, request_block) input_head;
} tuber_request;

typedef struct request_block {
	TAILQ_ENTRY(request_block) entries;
	char *start, *end;
} request_block;

static void tuber_request_completed_callback (void *cls,
			    struct MHD_Connection *connection,
			    void **con_cls,
			    enum MHD_RequestTerminationCode toe) {
	tuber_request *request = *con_cls;
	if(!request)
		return;

	/* Free serialized input */
	while(request->input_head.tqh_first) {
		free(request->input_head.tqh_first);
		TAILQ_REMOVE(&request->input_head, request->input_head.tqh_first, entries);
	}
	free(request);
}

size_t jansson_loader_callback(void *buffer, size_t buflen, tuber_request *req) {
	request_block *rb = req->input_head.tqh_first;
	if(!rb)
		return(0);

	/* Return up to buflen, depending on how much data is available */
	if(rb->end-rb->start < buflen)
		buflen = rb->end - rb->start;

	memcpy(buffer, rb->start, buflen);

	rb->start += buflen;

	if(rb->end == rb->start) {
		TAILQ_REMOVE(&req->input_head, rb, entries);
		free(rb);
	}

	return(buflen);
}

static int tuber_handler(
		struct handler_ent *self,
		void *cls,
		struct MHD_Connection *connection,
		const char *url,
		const char *method,
		const char *version,
		const char *upload_data,
		size_t * upload_data_size, void **ptr) {

	json_t *json_in = NULL;
	json_t *json_out = NULL;
	json_error_t json_error;
	int ret;
	struct header *h;
	struct MHD_Response *response = NULL;

	tuber_request *request = *ptr;
	request_block *rb = NULL;

	char *serialized_output = NULL;

	/* Requests come in 3 stages:
	 *
	 * 1. connection established; no data present
	 * 2. a sequence of calls with nonzero *upload_data_size
	 * 3. a final no-data call, where we're finally permitted
	 *    to generate a response.
	 */

	if(!request) {
		/* First stage: establish a request */
		if(!(*ptr = request = calloc(1, sizeof(tuber_request))))
			return MHD_NO; /* whoops! */
		TAILQ_INIT(&request->input_head);

		return MHD_YES;
	}

	if(*upload_data_size) {
		/* Data incoming: stash a copy (several times, unfortunately) */
		if(!(rb = malloc(sizeof(*rb) + *upload_data_size)))
			return MHD_NO; /* whoops! */

		rb->start = (char*)rb + sizeof(*rb);
		rb->end = rb->start + *upload_data_size;
		memcpy(rb->start, upload_data, *upload_data_size);

		TAILQ_INSERT_TAIL(&request->input_head, rb, entries);
		*upload_data_size = 0;

		return MHD_YES;
	}

	/* Finally, parse JSON and generate a response */
	if(!(json_in = json_load_callback((json_load_callback_t)jansson_loader_callback, request, JSON_DISABLE_EOF_CHECK, &json_error))) {
		debug("JSON error: %s\n", json_error.text);
		goto response_error;
	}

	if(!json_is_array(json_in) && !json_is_object(json_in))
		goto response_error;

	json_out = tuber_server_invoke(json_in);

	json_decref(json_in);
	json_in = NULL;

	if(!(serialized_output = json_dumps(json_out, 0)))
		goto response_error;

	json_decref(json_out);
	json_out = NULL;

	if(!(response = MHD_create_response_from_buffer(
			strlen(serialized_output),
			serialized_output,
			MHD_RESPMEM_MUST_FREE)))
		goto response_error;
	serialized_output = NULL;

	if(self->headers)
		for(h = self->headers; h->name && h->value; h++)
			MHD_add_response_header(response, h->name,
			h->value);

	ret = MHD_queue_response(connection, MHD_HTTP_OK, response);
	MHD_destroy_response(response);

	return ret;

response_error:
	if(json_in)
		json_decref(json_in);

	if(json_out)
		json_decref(json_out);

	if(serialized_output)
		free(serialized_output);

	if(!(response = MHD_create_response_from_buffer(0, NULL, MHD_RESPMEM_PERSISTENT)))
		return MHD_NO;

	ret = MHD_queue_response(connection, MHD_HTTP_NOT_FOUND, response);
	MHD_destroy_response(response);
	return ret;
}

static int file_handler(
		struct handler_ent *self,
		void *cls,
		struct MHD_Connection *connection,
		const char *url,
		const char *method,
		const char *version,
		const char *upload_data,
		size_t * upload_data_size, void **ptr) {

	FILE *f=NULL;
	struct stat stat;
	static char pathbuf[256];
	char *rp = NULL;
	struct header *h;

	int ret;
	struct MHD_Response *response = NULL;

	/* Construct a path buffer */
	pathbuf[sizeof(pathbuf)-1] = '\0';
	if(snprintf(pathbuf, sizeof(pathbuf)-1, "%s/%s", web_root, url) >= (int)sizeof(pathbuf)-1)
		goto response_error;

	if(!(rp = realpath(pathbuf, NULL)) || !(f = fopen(rp, "r")))
		goto response_error;

	if(strncmp(web_root, rp, strlen(web_root)))
		goto response_error;

	if(fstat(fileno(f), &stat) != 0)
		goto response_error;

	if(!(response = MHD_create_response_from_fd(stat.st_size, fileno(f))))
		return MHD_NO;

	/* Assign headers */
	if(self->headers)
		for(h = self->headers; h->name && h->value; h++)
			MHD_add_response_header(response, h->name, h->value);

	ret = MHD_queue_response(connection, MHD_HTTP_OK, response);
	MHD_destroy_response(response);
	return(ret);

response_error:
	if(rp)
		free(rp);

	if(f)
		fclose(f);

	if(!(response = MHD_create_response_from_buffer(0, NULL, MHD_RESPMEM_PERSISTENT)))
		return MHD_NO;
	ret = MHD_queue_response(connection, MHD_HTTP_NOT_FOUND, response);
	MHD_destroy_response(response);
	return ret;
}

static int index_handler(
		struct handler_ent *self,
		void *cls,
		struct MHD_Connection *connection,
		const char *url,
		const char *method,
		const char *version,
		const char *upload_data,
		size_t * upload_data_size, void **ptr) {

	/* Punt */
	int ret;
	char *fnbuf = calloc(strlen(url) + strlen("/index.html") + 1, 1);

	if(!fnbuf)
		return MHD_NO;

	sprintf(fnbuf, "%s/index.html", url);

	ret = file_handler(self, cls, connection, fnbuf, method, version, upload_data, upload_data_size, ptr);
	free(fnbuf);

	return ret;
}

static int fallback_handler(
		struct handler_ent *self,
		void *cls,
		struct MHD_Connection *connection,
		const char *url,
		const char *method,
		const char *version,
		const char *upload_data,
		size_t * upload_data_size, void **ptr) {

	int ret;
	struct header *h;
	struct MHD_Response *response = NULL;
	char *buf;

	/* Create a buffer with response text in it */
	if(!(buf = calloc(256, 1)))
		return MHD_NO;

	snprintf(buf, 255, "<html><head><title>Fastpath Webserver</title></head>"
		"<body><h1>Fastpath Webserver</h1><p>%s</p></body></html>",
		self->extra ? (char*)self->extra : "(unspecified)");

	/* Assign it to a response object */
	if(!(response = MHD_create_response_from_buffer(strlen(buf), buf, MHD_RESPMEM_MUST_FREE))) {
		free(buf);
		return MHD_NO;
	}

	/* Assign headers */
	if(self->headers)
		for(h = self->headers; h->name && h->value; h++)
			MHD_add_response_header(response, h->name, h->value);

	ret = MHD_queue_response(connection, MHD_HTTP_NOT_FOUND, response);
	MHD_destroy_response(response);
	return ret;
}

static struct handler_ent handlers[] = {
	{
		.method=MHD_HTTP_METHOD_POST,
		.url_regex="^/tuber$",
		.handler=tuber_handler,
		.headers = (struct header[]){
			{ MHD_HTTP_HEADER_CONTENT_TYPE, "application/json" },
			{ MHD_HTTP_HEADER_CACHE_CONTROL, "no-store" },
			{ NULL, NULL }
		}
	}, {
		.method=MHD_HTTP_METHOD_GET,
		.url_regex="^/.*\\.jpg$",
		.handler=file_handler,
		.headers = (struct header[]){
			{ MHD_HTTP_HEADER_CONTENT_TYPE, "image/jpeg" },
			{ MHD_HTTP_HEADER_CACHE_CONTROL, "max-age=3600" },
			{ NULL, NULL }
		}
	}, {
		.method=MHD_HTTP_METHOD_GET,
		.url_regex="^/.*\\.gif$",
		.handler=file_handler,
		.headers = (struct header[]){
			{ MHD_HTTP_HEADER_CONTENT_TYPE, "image/gif" },
			{ MHD_HTTP_HEADER_CACHE_CONTROL, "max-age=3600" },
			{ NULL, NULL }
		}
	}, {
		.method=MHD_HTTP_METHOD_GET,
		.url_regex="^/.*\\.png$",
		.handler=file_handler,
		.headers = (struct header[]){
			{ MHD_HTTP_HEADER_CONTENT_TYPE, "image/png" },
			{ MHD_HTTP_HEADER_CACHE_CONTROL, "max-age=3600" },
			{ NULL, NULL }
		}
	}, {
		.method=MHD_HTTP_METHOD_GET,
		.url_regex="^/.*\\.svg$",
		.handler=file_handler,
		.headers = (struct header[]){
			{ MHD_HTTP_HEADER_CONTENT_TYPE, "image/svg" },
			{ MHD_HTTP_HEADER_CACHE_CONTROL, "max-age=3600" },
			{ NULL, NULL }
		}
	}, {
		.method=MHD_HTTP_METHOD_GET,
		.url_regex="^/.*\\.css$",
		.handler=file_handler,
		.headers = (struct header[]){
			{ MHD_HTTP_HEADER_CONTENT_TYPE, "text/css" },
			{ MHD_HTTP_HEADER_CACHE_CONTROL, "max-age=3600" },
			{ NULL, NULL }
		}
	}, {
		.method=MHD_HTTP_METHOD_GET,
		.url_regex="^/.*\\.js$",
		.handler=file_handler,
		.headers = (struct header[]){
			{ MHD_HTTP_HEADER_CONTENT_TYPE, "application/javascript" },
			{ MHD_HTTP_HEADER_CACHE_CONTROL, "max-age=3600" },
			{ NULL, NULL }
		}
	}, {
		.method=MHD_HTTP_METHOD_GET,
		.url_regex="^/.*\\.html$",
		.handler=file_handler,
		.headers = (struct header[]){
			{ MHD_HTTP_HEADER_CONTENT_TYPE, "text/html" },
			{ MHD_HTTP_HEADER_CACHE_CONTROL, "max-age=3600" },
			{ NULL, NULL }
		}
	}, {
		.method=MHD_HTTP_METHOD_GET,
		.url_regex="^.*/$",
		.handler=index_handler,
		.headers = (struct header[]){
			{ MHD_HTTP_HEADER_CONTENT_TYPE, "text/html" },
			{ MHD_HTTP_HEADER_CACHE_CONTROL, "max-age=3600" },
			{ NULL, NULL }
		}
	}, {
		/* Fallback error handler */
		.method=MHD_HTTP_METHOD_GET,
		.url_regex=".*",
		.handler=fallback_handler,
		.headers= (struct header[]){
			{ MHD_HTTP_HEADER_CONTENT_TYPE, "text/html" },
			{ NULL, NULL }
		},
		.extra = "The requested URL wasn't matched by any of our handlers."
	}
};

static void usage() {
	printf("fastpath: Fastpath for DfMUX CGI scripts\n");
	printf("\n");
	printf("usage: fastpath [ARGUMENTS]...\n");
	printf("\n");
	printf("You may use one of the following ARGUMENTS:\n");
	printf("	-p|--port [PORT]	Use PORT (default is %i)\n", DEFAULT_PORT);
	printf("	-l|--library [PATH]	Register a library file or directory (default is %s)\n", DEFAULT_MOD_ROOT);
	printf("	-w|--webroot [PATH]	Use webroot PATH (default is %s)\n", DEFAULT_WEB_ROOT);
	printf("	-v|--verbose\n");
	printf("\n");
}

static int mhd_dispatcher(
		void *cls,
		struct MHD_Connection *connection,
		const char *url,
		const char *method,
		const char *version,
		const char *upload_data,
		size_t * upload_data_size, void **ptr);

int main(int argc, char **argv)
{
	struct MHD_Daemon *d;
	struct handler_ent *he;

	int fastpath_port = DEFAULT_PORT;
	int inotify_fd = -1;
	struct inotify_event *inotify_event;
	const int inotify_event_size = sizeof(*inotify_event) + NAME_MAX + 1;

	DIR *dir = NULL;
	struct dirent *entryp;
	struct stat st;
	char *path;

	int mod_root_specified = 0;
	int web_root_specified = 0;
	int mod_root_is_directory = 0;

	/* Parse command-line arguments */
	while(1) {
		int option_index = 0;
		int c;
		static struct option long_options[] = {
			{"port", 1, 0, 'p'},
			{"library", 1, 0, 'l'},
			{"webroot", 1, 0, 'w'},
			{"verbose", 0, 0, 'v'},
			{"help", 0, 0, 'h'},
			{0, 0, 0, 0}
		};

		c = getopt_long(argc, argv, "p:l:w:vh", long_options, &option_index);
		if(c == -1)
			break;

		switch(c) {
			case 'p':
				fastpath_port = atoi(optarg);
				break;

			case 'l':
				if(mod_root_specified++)
					fatal("Only one module root ('-l') may be specified!");
				mod_root = optarg;
				break;

			case 'w':
				if(web_root_specified++)
					fatal("Only one webroot ('-w') may be specified!");
				web_root = optarg;
				break;

			case 'v':
				tuber_verbose++;
				break;

			case 'h':
			default:
				usage();
				exit(-1);
				break;
		}
	}

	if(optind < argc) {
		usage();
		exit(-1);
	}

	/* Fully resolve paths. These buffers need to be free()'d */
	if(!web_root || !(web_root = realpath(web_root, NULL)))
		fatal("Unspecified or invalid web root ('-w') option!");

	if(!mod_root || !(mod_root = realpath(mod_root, NULL)))
		fatal("Unspecified or invalid module root ('-l') option!");

	/*
	 * Discover and initialize modules
	 */

	tuber_server_init();

	/* Register an inotify watch on the library file or directory,
	 * so we notice when modules appear and disappear. Do this before
	 * inspecting the library to avoid missed notifications. */
	if((inotify_fd = inotify_init()) == -1)
		fatal("Unable to create inotify descriptor!");

	if(inotify_add_watch(inotify_fd, mod_root, IN_CLOSE_WRITE | IN_DELETE) == -1) {
		warn("Unable to add inotify watch on '%s': modules won't be hot-swappable.", mod_root);
		close(inotify_fd);
		inotify_fd = -1;
	}

	if(!(inotify_event = calloc(1, inotify_event_size)))
		fatal("Unable to allocate memory!");

	/* If mod_root is a directory, scan its contents. */
	if((dir = opendir(mod_root)) != 0) {

		mod_root_is_directory = 1;

		while((entryp = readdir(dir))) {

			/* Skip ., .., and hidden files */
			if(entryp->d_name[0] == '.')
				continue;

			/* Resolve full pathname */
			if(!(path = calloc(strlen(mod_root) + strlen(entryp->d_name) + 2, 1)))
				fatal("Error allocating memory!");
			sprintf(path, "%s/%s", mod_root, entryp->d_name);

			/* Make sure we can stat the file */
			if(lstat(path, &st) == -1 || !S_ISREG(st.st_mode)) {
				warn("Skipping unavailable or non-file module '%s'", entryp->d_name);
				free(path);
				continue;
			}

			if(tuber_register_library(path) == 0)
				debug("Registered module '%s' from directory '%s'", entryp->d_name, mod_root);

			free(path);
		}
	} else {
		if(tuber_register_library(mod_root) != 0)
			fatal("Unable to open library! Specify a valid library with the '-l' option.");
	}
	if(dir)
		closedir(dir);

	/* Compile regular expressions for URL handlers */
	for(he=handlers; (char*)he < (char*)handlers + sizeof(handlers); he++) {
		if(regcomp(&he->url_regex_c, he->url_regex, REG_NEWLINE | REG_EXTENDED))
			fatal("Error compiling regular expression '%s'", he->url_regex);
	}

	/* Create microhttpd handle */
	if(!(d = MHD_start_daemon (
			MHD_USE_EPOLL_INTERNALLY_LINUX_ONLY | (tuber_verbose ? MHD_USE_DEBUG : 0),
			fastpath_port,
			NULL, NULL,
			mhd_dispatcher, NULL,
			MHD_OPTION_THREAD_POOL_SIZE, 4,
			MHD_OPTION_NOTIFY_COMPLETED, tuber_request_completed_callback, NULL,
			MHD_OPTION_END)))
		fatal("Error creating libmicrohttpd handle!");

	/* The web server now operates in side threads, leaving us little
	 * to do here. We just monitor libraries (specified using '-l')
	 * for changes, and re-register them when needed. */
	while(1) {
		/* Wait for something to happen. If we're interrupted by
		 * a signal, read will return an invalid inotify event
		 * and we bail. */
		if(read(inotify_fd, inotify_event, inotify_event_size) <= 0)
			break;

		/* Resolve full pathname */
		if(mod_root_is_directory) {
			if(!(path = calloc(strlen(mod_root) + inotify_event->len + 2, 1)))
				fatal("Error allocating memory!");
			sprintf(path, "%s/%s", mod_root, inotify_event->name);
		} else
			path = mod_root;

		/* If a "delete" occurred, unregister the library. */
		if(inotify_event->mask & IN_DELETE)
			tuber_unregister_library(path);

		/* Register if something new showed up */
		if(inotify_event->mask & IN_CLOSE_WRITE)
			tuber_register_library(path);

		if(mod_root_is_directory)
			free(path);
	}

	close(inotify_fd);
	free(inotify_event);

	free(web_root);
	free(mod_root);

	return 0;
}

static int mhd_dispatcher(
		void *cls,
		struct MHD_Connection *connection,
		const char *url,
		const char *method,
		const char *version,
		const char *upload_data,
		size_t * upload_data_size, void **ptr) {

	struct handler_ent *he;
	regmatch_t rm[2];
	int ret;
	struct MHD_Response *response = NULL;

	for(he=handlers; (char*)he < (char*)handlers + sizeof(handlers); he++) {

		/* Match method */
		if(strcmp(method, he->method))
			continue;

		/* Match URL */
		if(regexec(&he->url_regex_c, url, 2, rm, 0) != 0)
			continue;

		return he->handler(he, cls, connection, url, method, version,
				upload_data, upload_data_size, ptr);
	}

	debug("URI %s (%s): No handlers matched!", url, method);

	if(!(response = MHD_create_response_from_buffer(0, NULL, MHD_RESPMEM_MUST_FREE)))
		return(MHD_NO);

	ret = MHD_queue_response(connection, MHD_HTTP_NOT_FOUND, response);
	MHD_destroy_response(response);
	return ret;
}
