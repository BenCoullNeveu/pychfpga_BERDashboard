#ifndef __TUBER_H__
#define __TUBER_H__

#ifndef _GNU_SOURCE
# define _GNU_SOURCE
#endif

#include <jansson.h>
#include <boost/preprocessor.hpp>
#include <sys/queue.h>
#include <search.h>
#include <math.h> /* for isfinite() */

#define TUBER_MAX_NUM_PROPS		512
#define TUBER_MAX_NUM_METHODS		512

/* Call types */
typedef void (*tuber_method_t)(void *self, json_t *args, json_t *kwargs, json_t **results, json_t **error);

/*
 * Error Handling
 */

void tuber_oops(const char *fmt, ...);
void tuber_voops(const char *fmt, va_list ap);
void tuber_error_clear(void);
char *tuber_error_fetch(void);

struct tuber_object_entry_t; /* forward declaration */

typedef struct tuber_method_entry_t {
	LIST_ENTRY(tuber_method_entry_t) method_list_entry;

	tuber_method_t method;
	const char *name;
	const char *summary;
	const char *explanation;

	int num_args;

	struct tuber_method_args_t {
		const char *name;
		int type;
		const char *default_value; /* unused, and I hate it right now */
		const char *description;
	} args[];
} tuber_method_entry_t;

typedef struct tuber_property_entry_t {
	LIST_ENTRY(tuber_property_entry_t) property_list_entry;

	const char *name;
	json_t *value;
} tuber_property_entry_t;

/* Object entries look like this. */
typedef struct tuber_object_entry_t {
	const char *name;
	const char *summary;
	const char *explanation;

	/*
	 * ALL THE REMAINING must be filled in at load time
	 */

	void *instance;
	void *handle;

	struct hsearch_data property_htab;
	LIST_HEAD(property_list, tuber_property_entry_t) property_list;
	int property_count;

	struct hsearch_data method_htab;
	LIST_HEAD(method_list, tuber_method_entry_t) method_list;
	int method_count;

} tuber_object_entry_t;

#define tuber_object(_object, _summary, _explanation)				\
	/* Define global object */						\
	tuber_object_entry_t __tuber_object_##_object = {			\
		.name = BOOST_PP_STRINGIZE(_object),				\
		.instance = NULL,						\
		.handle = NULL,							\
		.property_count = 0,						\
		.method_count = 0,						\
		.summary = _summary,						\
		.explanation = _explanation,					\
	};									\

/*
 * Constructor Declarations. Emit three different functions. For example:
 *
 * 	- new_TestObject: returns a singleton reference; exported
 *      - __actual_new_TestObject: actual initialization code you provide; unexported
 *	- __dlctor_new_TestObject: initialises the TuberObject structure with a call to above.
 */

#define tuber_constructor(_object, _summary, _explanation)			\
	_object *new_##_object(void) {						\
		return (_object *)__tuber_object_##_object.instance;		\
	}									\
	static _object *__actual_new_##_object(void);				\
	__attribute__((constructor(1000)))					\
	static void __dlctor_new_##_object(void) {				\
		tuber_object_entry_t *self = &__tuber_object_##_object;		\
		if(!(self->instance = __actual_new_##_object()))		\
			fatal("Error during " BOOST_PP_STRINGIZE(_object) " constructor call!"); \
										\
		memset(&self->method_htab, 0, sizeof(self->method_htab));	\
		if(hcreate_r(TUBER_MAX_NUM_METHODS*2, &self->method_htab) == 0)	\
			fatal("Error creating method hash!");			\
		LIST_INIT(&self->method_list);					\
										\
		memset(&self->property_htab, 0, sizeof(self->property_htab));	\
		if(hcreate_r(TUBER_MAX_NUM_PROPS*2, &self->property_htab) == 0)	\
			fatal("Error creating property hash!");			\
		LIST_INIT(&self->property_list);				\
	}									\
	__attribute__((destructor(2000)))					\
	static void __dldtor_delete1_##_object(void) {				\
		tuber_object_entry_t *self = &__tuber_object_##_object;		\
		tuber_property_entry_t *prop;					\
		hdestroy_r(&self->method_htab);					\
		hdestroy_r(&self->property_htab);				\
		for(prop = self->property_list.lh_first; prop; prop = prop->property_list_entry.le_next)	\
			json_decref(prop->value);				\
		self->property_count = 0;					\
		self->method_count = 0;						\
	}									\
	static _object *__actual_new_##_object(void)

/*
 * Destructor Declarations: Emits three different functions. See above.
 */

#define tuber_destructor(_object, _summary, _explanation)			\
	void delete_##_object(_object *self) {					\
		/* not deleting singleton */					\
	}									\
	static void __actual_delete_##_object(_object *);			\
	__attribute__((destructor(1000)))					\
	static void __dldtor_delete2_##_object(void) {				\
		tuber_object_entry_t *self = &__tuber_object_##_object;		\
		__actual_delete_##_object(self->instance);			\
	}									\
	void __actual_delete_##_object(_object *self)

#define tuber_property(object, _property, _value)				\
	/* Define global object */						\
	static tuber_property_entry_t __tuber_property_ ## object ## __ ## _property;	\
	/* Define constructor */						\
	__attribute__((constructor(2000)))					\
	void __dlctor_new_##object ## __ ##_property(void) {			\
		extern tuber_object_entry_t __tuber_object_##object;		\
		tuber_object_entry_t *self = &__tuber_object_##object;		\
		tuber_property_entry_t *prop = &__tuber_property_ ## object ## __ ## _property;	\
		ENTRY hent = { .key = #_property, .data=prop }, *hentp;						\
		prop->value = (_value);						\
		prop->name = #_property;					\
		if(++self->property_count >= TUBER_MAX_NUM_PROPS)		\
			fatal("Property overflow! Increase TUBER_MAX_NUM_PROPS.");\
		LIST_INSERT_HEAD(&self->property_list, prop, property_list_entry);\
		if(!hsearch_r(hent, ENTER, &hentp, &self->property_htab))	\
			fatal("Error initializing property hashtable!");	\
	}									\

/*
 * Error Objects:
 *
 * - should probably not be used in user code
 * - gives error returns a consistent look and feel.
 */

#define tuber_error_object(fmt, ...) ({						\
	char *__json_err_buf = malloc(256);                                     \
	json_t *__json_err_ret;                                                 \
	snprintf(__json_err_buf, 256, fmt, ##__VA_ARGS__);                      \
	__json_err_ret = json_pack("{s:s,s:s}", "source", __FILE__, "message", __json_err_buf); \
	free(__json_err_buf);                                                   \
	__json_err_ret;                                                         \
})

/*
 * Wrapper macro.
 */

/* These constants are only used by the preprocessor metaprogramming magic.
 * They aren't actually present in the compiled code. Basically, the choice of
 * values is irrelevant as long as they're unique (with the notable exception
 * of INTEGER.) */

#define VOID			128
#define STRING			129
#define SIGNED_INTEGER		130
#define UNSIGNED_INTEGER	131
#define DOUBLE			132
#define BOOLEAN			133
#define STRING_CONST		134
#define JSON			135
#define INTEGER			SIGNED_INTEGER

/* tuber_method: Top-level wrapper */
#define tuber_method(object, ret, func, _summary, _num_args, _args, _explanation)	\
	/* Emit prototype for the unwrapped function, in case it doesn't */	\
	/* appear in a header */			\
	nctype(ret) object ##_ ##func(object *self BOOST_PP_COMMA_IF(_num_args) BOOST_PP_ENUM(_num_args, nargdef, BOOST_PP_TUPLE_TO_LIST(_num_args, _args))); \
										\
	/* Emit the JSON wrapper function */					\
	tuber_emit_wrapper(object, func, _num_args, _args, ret)			\
										\
	/* Emit wrapper object */						\
	tuber_method_entry_t __tuber_method_ ## object ## __ ## func = {	\
		.method = __tuber_json_method_ ## object ## __ ## func,		\
		.name = #func,							\
		.summary = _summary,						\
		.explanation = _explanation,					\
		.num_args = _num_args,						\
		.args = {							\
			BOOST_PP_LIST_FOR_EACH(					\
				tuber_macro_argfiller,,				\
				BOOST_PP_TUPLE_TO_LIST(_num_args, _args)	\
			)							\
		},								\
	};									\
										\
	__attribute__((constructor(2000)))					\
	static void __dlctor_register_##object ## __ ## func(void) {		\
		extern tuber_object_entry_t __tuber_object_##object;		\
		tuber_object_entry_t *self = &__tuber_object_##object;		\
		tuber_method_entry_t *meth = &__tuber_method_##object##__##func;\
		ENTRY hent = { .key = #func, .data = meth }, *hentp;		\
		if(++self->method_count >= TUBER_MAX_NUM_METHODS)		\
			fatal("Method overflow! Increase TUBER_MAX_NUM_METHODS.");\
		LIST_INSERT_HEAD(&self->method_list, meth, method_list_entry);	\
		if(!hsearch_r(hent, ENTER, &hentp, &self->method_htab))		\
			fatal("Error initializing object hashtable!");		\
	}									\
										\
	/* Emit the definition for the unwrapped function */			\
	nctype(ret) object ##_ ##func(object *self BOOST_PP_COMMA_IF(_num_args) BOOST_PP_ENUM(_num_args, nargdef, BOOST_PP_TUPLE_TO_LIST(_num_args, _args)))

/* nargdef: generate an "ctype name" pair for an argument number (the z is
 * ignored, and is used for ENUM calls */
#define nargdef(z,argnum,args) \
	nctype(tuber_argtype(BOOST_PP_LIST_AT(args, argnum))) \
	tuber_argname(BOOST_PP_LIST_AT(args, argnum))

/* nctype: convert TYPE to ctype */
#define nctype(typeconst)							\
	BOOST_PP_IF(BOOST_PP_EQUAL(typeconst,STRING),char*,)			\
	BOOST_PP_IF(BOOST_PP_EQUAL(typeconst,STRING_CONST),const char*,)	\
	BOOST_PP_IF(BOOST_PP_EQUAL(typeconst,SIGNED_INTEGER),int,)		\
	BOOST_PP_IF(BOOST_PP_EQUAL(typeconst,UNSIGNED_INTEGER),unsigned int,)	\
	BOOST_PP_IF(BOOST_PP_EQUAL(typeconst,DOUBLE),double,)			\
	BOOST_PP_IF(BOOST_PP_EQUAL(typeconst,BOOLEAN),int,)			\
	BOOST_PP_IF(BOOST_PP_EQUAL(typeconst,VOID),void,)			\
	BOOST_PP_IF(BOOST_PP_EQUAL(typeconst,JSON),json_t*,)

#define tuber_macro_argfiller(r, data, elem)					\
	{									\
		.name=BOOST_PP_STRINGIZE(tuber_argname(elem)),			\
		.type=tuber_argtype(elem),					\
		.default_value=BOOST_PP_STRINGIZE(tuber_argdefault(elem)),	\
		.description=tuber_arghelp(elem),				\
	},


/* Fill in variable with NULLs, in case downstream setters don't work */
#define tuber_stuff_from_null(r, data, argnum, arg)				\
	__json_args[argnum] = NULL;

/* Fill in variable from positional arguments */
#define tuber_stuff_from_args(r, data, argnum, arg)				\
	__json_args[argnum] = json_array_get(json_args, argnum);

/* Ditto, kwargs */
#define tuber_stuff_from_kwargs(r, data, argnum, arg)				\
	if((__cur = json_object_get(json_kwargs, BOOST_PP_STRINGIZE(tuber_argname(arg))))) {	\
		if(__json_args[argnum] != NULL) {				\
			*json_err = tuber_error_object(				\
					"Argument "				\
					BOOST_PP_STRINGIZE(tuber_argname(arg))	\
					" was specified in both positional and keyword arguments list!");	\
			return;							\
		}								\
		__json_args[argnum] = __cur;					\
		num_used_kwargs++;						\
	}

/* Apply defaults if they're required */
#define tuber_stuff_from_defaults(r, data, argnum, arg)				\
	if(!__json_args[argnum]) {						\
		__json_args[argnum] = tuber_argdefault(arg);			\
		if(__json_args[argnum]) {					\
			if(!__tidy_stack)					\
				__tidy_stack = json_array();			\
			json_array_append_new(__tidy_stack, __json_args[argnum]);	\
		}								\
	}

/* Ensure we have JSON values for all C arguments */
#define tuber_validate_arguments(r, data, argnum, arg)				\
	if(!tuber_type_valid(argnum, arg)) {					\
		*json_err = tuber_error_object("Argument " BOOST_PP_STRINGIZE(tuber_argname(arg)) " was unspecified or wasn't the expected type!");	\
		json_decref(__tidy_stack);					\
		return;								\
	}

#define tuber_type_valid(argnum, arg)						\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),STRING),json_is_string(__json_args[argnum]),)		\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),STRING_CONST),json_is_string(__json_args[argnum]),)	\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),SIGNED_INTEGER),json_is_integer(__json_args[argnum]),)	\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),UNSIGNED_INTEGER),json_is_integer(__json_args[argnum]),)	\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),DOUBLE),json_is_number(__json_args[argnum]),)		\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),BOOLEAN),json_is_boolean(__json_args[argnum]),)		\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),JSON),(!!__json_args[argnum]),)

#define tuber_type_value(arg,ref)										\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),STRING),json_string_value(ref),)				\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),STRING_CONST),json_string_value(ref),)			\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),SIGNED_INTEGER),json_integer_value(ref),)			\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),UNSIGNED_INTEGER),json_integer_value(ref),)		\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),DOUBLE),json_number_value(ref),)				\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),BOOLEAN),json_is_true(ref),)				\
	BOOST_PP_IF(BOOST_PP_EQUAL(tuber_argtype(arg),JSON),ref,)

/* Return list of variable addresses (for unpack) */
#define tuber_enum_macro_args(z, n, args)					\
	tuber_type_value(BOOST_PP_LIST_AT(args,n),__json_args[n])

/*
 * MACROS TO ACCESS ARGUMENT TUPLES
 */

#define tuber_argtype(arg)	BOOST_PP_TUPLE_ELEM(4,0,arg)
#define tuber_argname(arg)	BOOST_PP_TUPLE_ELEM(4,1,arg)
#define tuber_argdefault(arg)	BOOST_PP_TUPLE_ELEM(4,2,arg)
#define tuber_arghelp(arg)	BOOST_PP_TUPLE_ELEM(4,3,arg)

#define tuber_help_argdef(r, data, i, arg)					\
	BOOST_PP_IF(i,",","")							\
	BOOST_PP_STRINGIZE(nctype(tuber_argtype(arg)))				\
	" "									\
	BOOST_PP_STRINGIZE(tuber_argname(arg))

#define tuber_emit_wrapper(object, func, num_args, args, ret)			\
										\
	/* Generate wrapper function */						\
	__attribute__((visibility("hidden")))					\
	void __tuber_json_method_ ## object ## __ ## func(void* self,		\
			json_t *json_args, json_t *json_kwargs,			\
			json_t **json_results, json_t **json_err) {		\
										\
		/* VARIABLE DECLARATIONS */					\
										\
		char *__error;							\
		json_t *__tidy_stack = NULL; /* only used for defaults */	\
		int num_used_kwargs = 0;					\
										\
		/* CONDITIONAL VARIABLE DECLARATIONS (to squash warnings) */	\
		BOOST_PP_IF(num_args,json_t *__cur;,)				\
		BOOST_PP_IF(num_args,json_t *__json_args[num_args];,)		\
										\
		/* Generate return variable if appropriate */			\
		BOOST_PP_IF(BOOST_PP_EQUAL(ret,VOID),,nctype(ret) __wrap_ret;)	\
										\
		/* json_null() isn't refcounted, so this is OK */		\
		*json_results = *json_err = json_null();			\
										\
		/* CODE BEGINS HERE */						\
										\
		/* Validate args */						\
		if(json_args && !json_is_array(json_args)) {			\
			*json_err = tuber_error_object("Invalid args provided to " #func "!");\
			return;							\
		}								\
										\
		/* Validate kwargs */						\
		if(json_kwargs && !json_is_object(json_kwargs)) {		\
			*json_err = tuber_error_object("Invalid kwargs provided to " #func "!");\
			return;							\
		}								\
										\
		/* Ensure we don't have too many arguments */			\
		if(json_args && json_array_size(json_args) > num_args) {	\
			*json_err = tuber_error_object("Too many positional arguments provided to " #func "! Expected ( "	\
				BOOST_PP_LIST_FOR_EACH_I(tuber_help_argdef,, BOOST_PP_TUPLE_TO_LIST(num_args, args))\
				" )");						\
			return;							\
		}								\
										\
		/* Start with NULL __json_args */				\
		BOOST_PP_LIST_FOR_EACH_I(tuber_stuff_from_null,,BOOST_PP_TUPLE_TO_LIST(num_args, args)) \
										\
		/* Initialize from positional arguments; zero the rest */	\
		if(json_args) {							\
			BOOST_PP_LIST_FOR_EACH_I(tuber_stuff_from_args,,BOOST_PP_TUPLE_TO_LIST(num_args, args)) \
		}								\
										\
		/* Initialize from kwargs arguments; complain if duplicated */	\
		if(json_kwargs) {						\
			BOOST_PP_LIST_FOR_EACH_I(tuber_stuff_from_kwargs,,BOOST_PP_TUPLE_TO_LIST(num_args, args)) \
		}								\
										\
		if(num_used_kwargs < json_object_size(json_kwargs)) {		\
			*json_err = tuber_error_object("Extra associative arguments provided to " #func "! Expected ( "	\
				BOOST_PP_LIST_FOR_EACH_I(tuber_help_argdef,, BOOST_PP_TUPLE_TO_LIST(num_args, args))\
				" )");						\
			return;							\
		}								\
										\
		/* Fill in anything that's left with defaults */		\
		BOOST_PP_LIST_FOR_EACH_I(tuber_stuff_from_defaults, __json_args, BOOST_PP_TUPLE_TO_LIST(num_args, args)) \
										\
		/* Ensure we have enough arguments, of the correct type */	\
		BOOST_PP_LIST_FOR_EACH_I(tuber_validate_arguments, __json_args, BOOST_PP_TUPLE_TO_LIST(num_args, args)) \
										\
		/* Call */							\
		tuber_error_clear();						\
		BOOST_PP_IF(BOOST_PP_EQUAL(ret,VOID),,__wrap_ret =)		\
			object##_##func(					\
			self							\
			BOOST_PP_ENUM_TRAILING(num_args, tuber_enum_macro_args, BOOST_PP_TUPLE_TO_LIST(num_args,args)) \
		);								\
										\
		if((__error = tuber_error_fetch())) {				\
			*json_results = json_null();				\
			*json_err = tuber_error_object("%s", __error);		\
			json_decref(__tidy_stack);				\
			return;							\
		}								\
										\
		/* Wrap returned value */					\
		*json_err = json_null();					\
		*json_results =							\
			BOOST_PP_IF(BOOST_PP_EQUAL(ret,VOID),json_null(),)	\
			BOOST_PP_IF(BOOST_PP_EQUAL(ret,SIGNED_INTEGER),json_integer(__wrap_ret),)	\
			BOOST_PP_IF(BOOST_PP_EQUAL(ret,UNSIGNED_INTEGER),json_integer(__wrap_ret),)	\
			BOOST_PP_IF(BOOST_PP_EQUAL(ret,DOUBLE),isfinite(__wrap_ret) ? json_real(__wrap_ret) : json_null(),)	\
			BOOST_PP_IF(BOOST_PP_EQUAL(ret,STRING),json_string(__wrap_ret),)	\
			BOOST_PP_IF(BOOST_PP_EQUAL(ret,STRING_CONST),json_string(__wrap_ret),)	\
			BOOST_PP_IF(BOOST_PP_EQUAL(ret,BOOLEAN),__wrap_ret ?  json_true() : json_false(),)	\
			BOOST_PP_IF(BOOST_PP_EQUAL(ret,JSON),__wrap_ret,)	\
			;							\
										\
		json_decref(__tidy_stack);					\
	}

#endif /* __WRAPPER_H__ */

/* vim: textwidth=0
 */
