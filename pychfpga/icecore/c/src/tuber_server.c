#ifndef _GNU_SOURCE
# define _GNU_SOURCE
#endif

#include <stdlib.h>
#include <unistd.h>
#include <string.h>

#include <sys/stat.h>
#include <fcntl.h>

#include <dlfcn.h>
#include <libelf.h>
#include <gelf.h>

#include "tuber.h"
#include "tuber_server.h"

/*
 * Globals
 */

struct tuber_library_t {
	void *handle;
	char *path;

	struct hsearch_data object_htab;

	LIST_ENTRY(tuber_library_t) library_list_entry;

	tuber_object_entry_t *object_list[256]; /* FIXME */
	int object_count;
};
LIST_HEAD(library_list_head, tuber_library_t) library_list_head;

/*
 * Global init / cleanup
 */

void tuber_server_init(void) {
	if(elf_version(EV_CURRENT) == EV_NONE)
		fatal("libelf is out of date!");

	LIST_INIT(&library_list_head);
}

/*
 * Information functions
 */

tuber_object_entry_t *tuber_server_lookup_object(const char *name) {
	ENTRY hent, *hentp;
	struct tuber_library_t *lh;

	for(lh = library_list_head.lh_first; lh; lh=lh->library_list_entry.le_next) {
		hent.key = (char *)name;

		if(!hsearch_r(hent, FIND, &hentp, &lh->object_htab))
			continue;

		return((tuber_object_entry_t *)hentp->data);
	}

	return(NULL);
}

/*
 * Library scan
 */

int tuber_register_library(const char *path) {

	struct tuber_library_t *lh=NULL;
	char *name;

	tuber_object_entry_t *oe;

	int fd=-1;
	int symbol_count;
	int i;

	Elf *elf;
	Elf_Scn *scn = NULL;
	Elf_Data *edata = NULL;
	GElf_Sym sym;
	GElf_Shdr shdr;

	struct entry hent, *hentp;

	debug("Considering library at '%s'", path);

	if(!path)
		fatal("BUG: register_library called with null library!");

	/* Validation: We *can't* re-register libraries unless they've
	 * been cleanly removed first. That means no cp, no overwrites;
	 * you *must* use mv, unlink, rm, or install. Bail if we can't
	 * proceed cleanly. */
	for(lh = library_list_head.lh_first; lh; lh=lh->library_list_entry.le_next)
		if(!strcmp(path, lh->path))
			fatal("Eek! Module '%s' clobbered!\nReplace modules using 'rm', 'install' or 'mv' instead of 'cp'.", path);

	if(!(lh = calloc(1, sizeof(*lh))) ||
			!(lh->path = calloc(strlen(path)+1, 1)))
		fatal("Error allocating memory!");

	strcpy(lh->path, path);

	/* dlopen() the shared library */
	if(!(lh->handle = dlopen(path, RTLD_NOW))) {
		debug("Error loading library '%s' (%s)", path, dlerror());
		goto error;
	}

	/* Load the library as a file, so we can see its symbols */
	if((fd = open(path, O_RDONLY)) == -1) {
		debug("Error opening library '%s'", path);
		goto error;
	}

	/* scan for symbols */
	elf = elf_begin(fd, ELF_C_READ, NULL);
	while((scn = elf_nextscn(elf, scn)) != NULL) {
		gelf_getshdr(scn, &shdr);

		/* Find the string table */
		if(shdr.sh_type == SHT_SYMTAB)
			break;
	}
	if(!scn)
		fatal("Unable to find string table!");

	edata = elf_getdata(scn, edata);
	symbol_count = shdr.sh_size / shdr.sh_entsize;

	/* Populate object hash */
	for(i=0; i<symbol_count; i++) {
		gelf_getsym(edata, i, &sym);

		/* Ignore anything that isn't defined here */
		if(!sym.st_value)
			continue;

		/* Skip over non-global symbols and functions */
		if(ELF32_ST_BIND(sym.st_info) != STB_GLOBAL || ELF32_ST_TYPE(sym.st_info) == STT_FUNC)
			continue;

		/* Pay attention only to names starting with object prefix */
		name = elf_strptr(elf, shdr.sh_link, sym.st_name);
		if(strncmp("__tuber_object_", name, 15))
			continue;

		/* GOT AN INSTANCE. Initialize it */
		oe = (typeof(oe))dlsym(lh->handle, name);

		oe->handle = lh->handle;

		/* Add to object list */
		lh->object_list[lh->object_count++] = oe;
	}

	elf_end(elf);
	close(fd);
	fd = -1;

	/* Set up object hashtable */
	if(hcreate_r(lh->object_count*2, &lh->object_htab) == 0)
		fatal("Error creating object hash!");

	for(i=0; i<lh->object_count; i++) {
		oe = lh->object_list[i];

		/* Create hash entry */
		hent.data = oe;
		hent.key = (char *)oe->name;

		if(!hsearch_r(hent, ENTER, &hentp, &lh->object_htab))
			fatal("Failed to enter object '%s' in hashtable!", oe->name);
	}

	LIST_INSERT_HEAD(&library_list_head, lh, library_list_entry);

	debug("Registered library '%s'", lh->path);

	return(0);

error:
	if(lh) {
		if(lh->handle)
			dlclose(lh->handle);

		free(lh);
	}
	if(fd != -1)
		close(fd);

	return(-1);
}

static void tuber_close_library(struct tuber_library_t *lh, int use_dlclose);

int tuber_unregister_library(const char *path) {
	struct tuber_library_t *lh=NULL;

	for(lh = library_list_head.lh_first; lh; lh=lh->library_list_entry.le_next) {

		/* Skip libraries until we find the matching one. */
		if(strcmp(path, lh->path))
			continue;

		debug("Closing library '%s'", lh->path);

		tuber_close_library(lh, 1);
		return(0);
	}

	debug("Failed to close library '%s': was it registered?", path);
	return(-1);
}

static void tuber_close_library(struct tuber_library_t *lh, int use_dlclose) {
	/* dlclose() crashes when libraries are hot-swapped with an overwrite
	 * (as opposed to an unlink/replace). The "official" solution is to
	 * use e.g. "install" rather than "cp". Since that seems unlikely, we
	 * just don't dlclose. */
	if(use_dlclose)
		dlclose(lh->handle);

	hdestroy_r(&lh->object_htab);
	LIST_REMOVE(lh, library_list_entry);

	free(lh->path);
	memset(lh, 0, sizeof(*lh));
	free(lh);
}

void tuber_server_fatal_call(const char *fmt, ...) {

	va_list ap;

	va_start(ap, fmt);
	vfprintf(stderr, fmt, ap);
	va_end(ap);

	exit(-1);
}

void tuber_server_cleanup(void) {
	struct tuber_library_t *h;

	while((h = library_list_head.lh_first))
		tuber_close_library(h, 1);
}

/*
 * Method invocation
 */

static void json_method_handler(tuber_object_entry_t *, json_t *, json_t **, json_t **, int);
static void json_property_handler(tuber_object_entry_t *, json_t *json_in, json_t **, json_t **, int);
static void json_object_handler(tuber_object_entry_t *, json_t *, json_t **, json_t **, int);

json_t *tuber_server_invoke(json_t *input) {
	unsigned int call_num=0;

	json_t *json_out_all, *json_out;
	json_t *json_in, *json_out_result, *json_out_error;

	const char *o_string;
	json_t *obj;

	tuber_object_entry_t *o;

	if(json_is_object(input)) {
		json_in = input;
		json_out_all = json_null();
		goto entry;
	} else
		json_out_all = json_array();

	for(; call_num<json_array_size(input); call_num++) {

		json_in = json_array_get(input, call_num);
entry:
		json_out_error = json_out_result = json_null();

		/* Parse and delegate */
		if(!json_in || !json_is_object(json_in))
			json_out_error = tuber_error_object("Call %u: Input wasn't an object!", call_num);
		else if(!(obj = json_object_get(json_in, "object")) || !(o_string=json_string_value(obj)))
			json_out_error = tuber_error_object("Call %u: Failed to parse object!", call_num);
		else if(!(o = tuber_server_lookup_object(o_string)))
			json_out_error = tuber_error_object("Call %u: Object '%s' lookup failed.", call_num, o_string);
		else {
			if(json_object_get(json_in, "method"))
				json_method_handler(o, json_in, &json_out_result, &json_out_error, call_num);
			else if(json_object_get(json_in, "property"))
				json_property_handler(o, json_in, &json_out_result, &json_out_error, call_num);
			else if(json_object_get(json_in, "object"))
				json_object_handler(o, json_in, &json_out_result, &json_out_error, call_num);
			else
				json_out_error = tuber_error_object("Call %u: Couldn't figure out what to do!", call_num);
		}

		json_out = json_pack("{s:o,s:o}",
				"result", json_out_result,
				"error", json_out_error);

		if(json_is_null(json_out_all))
			return(json_out);
		else
			json_array_append_new(json_out_all, json_out);
	}

	return(json_out_all);
}

static void json_object_handler(tuber_object_entry_t *o, json_t *json_in, json_t **json_out_result, json_t **json_out_error, int call_num) {
	/* Emit a list of properties and methods, along with documentation
	 * properties. */

	tuber_method_entry_t *m;
	tuber_property_entry_t *p;

	json_t *property_list;
	json_t *method_list;

	property_list = json_array();
	method_list = json_array();

	(void)json_in;
	(void)json_out_error;
	(void)call_num;

	/* Emit a list of methods, properties, and object properties */
	for(p = o->property_list.lh_first; p; p=p->property_list_entry.le_next)
		json_array_append_new(property_list, json_string(p->name));

	for(m = o->method_list.lh_first; m; m=m->method_list_entry.le_next)
		json_array_append_new(method_list, json_string(m->name));

	*json_out_result = json_pack("{s:o,s:o,s:s,s:s,s:s}",
			"methods", method_list,
			"properties", property_list,
			"name", o->name,
			"summary", o->summary,
			"explanation", o->explanation);
}

static void json_method_handler(tuber_object_entry_t *o, json_t *json_in, json_t **json_out_result, json_t **json_out_error, int call_num) {
	tuber_method_entry_t *m;

	ENTRY hent, *hentp;

	const char *m_string;
	json_t *json_args=NULL, *json_kwargs=NULL;
	json_t *obj;

	if(!(obj = json_object_get(json_in, "method")) || !(m_string=json_string_value(obj))) {
		*json_out_error = tuber_error_object("Call %u: Failed to parse method!", call_num);
		return;
	}
	hent.key = (char *)m_string;

	if(hsearch_r(hent, FIND, &hentp, &o->method_htab) == 0) {
		*json_out_error = tuber_error_object("Failed method look-up");
		return;
	}
	m = (tuber_method_entry_t *)hentp->data;

	/* Parse args; NULL if none */
	if((json_args = json_object_get(json_in, "args")) && !json_is_array(json_args)) {
		*json_out_error = tuber_error_object("Call %u: args wasn't an array!", call_num);
		return;
	}

	/* Parse kwargs; NULL if none */
	if((json_kwargs = json_object_get(json_in, "kwargs")) && !json_is_object(json_kwargs)) {
		*json_out_error = tuber_error_object("Call %u: kwargs wasn't an object!", call_num);
		return;
	}

	/* Call method */
	(m->method)(o->instance, json_args, json_kwargs, json_out_result, json_out_error);
	if(!*json_out_result || !*json_out_error) {

		json_decref(*json_out_result);
		json_decref(*json_out_error);

		*json_out_error = tuber_error_object("Method returned NULL!");
		return;
	}
}

static void json_property_handler(tuber_object_entry_t *o, json_t *json_in, json_t **json_out_result, json_t **json_out_error, int call_num) {
	tuber_method_entry_t *m = NULL;
	tuber_property_entry_t *p;
	int i;
	struct tuber_method_args_t *a;
	json_t *args;
	json_t *obj;

	ENTRY hent, *hentp;

	const char *p_string;

	/* See if it's a property or a method */
	if(!(obj = json_object_get(json_in, "property")) || !(p_string=json_string_value(obj))) {
		*json_out_error = tuber_error_object("Call %u: Failed to parse property!", call_num);
		return;
	}
	hent.key = (char *)p_string;

	if(hsearch_r(hent, FIND, &hentp, &o->property_htab) != 0) {

		p = (tuber_property_entry_t *)hentp->data;
		*json_out_result = p->value;
		json_incref(p->value);
		return;

	} else if(hsearch_r(hent, FIND, &hentp, &o->method_htab) != 0) {

		m = (tuber_method_entry_t *)hentp->data;

		/* Mark "no information about arguments" with null */
		args = (m->num_args == -1) ? json_null() : json_array();
		for(i=0; i<m->num_args; i++) {
			a = m->args+i;
			json_array_append_new(args, json_pack("{s:s,s:i,s:s}",
				"name", a->name,
				"type", a->type,
				"description", a->description
			));
		}
		*json_out_result = json_pack("{s:s,s:s,s:s,s:o}",
				"name", m->name,
				"summary", m->summary,
				"explanation", m->explanation,
				"args", args
		);
		return;
	}

	*json_out_error = tuber_error_object("Failed property look-up");

}


/* vim: textwidth=0
 */
