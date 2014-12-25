#include <stdlib.h>
#include <stdio.h>
#include <assert.h>
#include <stdarg.h>

#include "ipmi_frui.h"

/* Forward declarations */
typedef struct frui_internal frui_internal;
typedef struct frui_chassis frui_chassis;
typedef struct frui_board frui_board;
typedef struct frui_product frui_product;

/*
 * FRUI structure
 *
 * This is unencoded, so all quantities (e.g. structure offsets) are
 * measured in bytes, not in 8-byte increments.
 */
struct frui {
	uint8_t version;

	int int_off;
	int chs_off;
	int brd_off;
	int prd_off;
	int mr_off;

	frui_internal *int_blk;
	frui_chassis *chs_blk;
	frui_board *brd_blk;
	frui_product *prd_blk;
};

enum frui_parser_state {
	HEADER=0,
	INTERNAL=1,
	CHASSIS=2,
	BOARD=3,
	PRODUCT=4,
	/*MR=5,*/
	DONE=6,
	STRING=7,
};

/* FRUI parser handle. */
struct frui_parser {
	enum frui_parser_state state;

	/* Internal parser: when do we run out of internal block? */
	int internal_max_size;

	/* Temporary state for string parser */
	enum frui_parser_state state_stringret; /* what state do we return to when the strings end? */
	struct frui_stringbuf *stringbuf; /* current string */
	struct frui_stringbuf_head *stringbuf_head; /* where completed strings get attached */

	/* Temporary parsing buffer (and occupancy) */
	uint8_t buf[64]; /* big enough for the largest string length */
	int buf_occ;

	int off; /* global offset */
	int cur; /* state-defined cursor */
	uint8_t sum; /* rolling checksum */

	/* In-progress blocks; not attached until verified */
	struct frui_internal *int_blk;
	struct frui_chassis *chs_blk;
	struct frui_board *brd_blk;
	struct frui_product *prd_blk;

	struct frui *frui;

	/* Error flag */
	const char *error;

	/* Warning stack */
	TAILQ_HEAD(frui_warning_stack, frui_warning) warnings;
};

/*
 * String Type/Length Encoding
 *
 * When packed, these are not necessarily null-terminated (even when
 * they're strings). We always null-terminate them here.
 */

typedef struct frui_stringbuf {
	enum {
		FRU_STRINGBUF_BINARY=0x00,
		FRU_STRINGBUF_BCDPLUS=0x01,
		FRU_STRINGBUF_6BIT=0x02,
		FRU_STRINGBUF_LANGUAGE=0x03,
	} type;
	int len;

	TAILQ_ENTRY(frui_stringbuf) entry;

	char data[];
} frui_stringbuf;

TAILQ_HEAD(frui_stringbuf_head, frui_stringbuf);

/*
 * Internal block
 *
 * There's no "length" field for the internal block, so we don't know
 * exactly how long it needs to be. We infer maximum length by looking
 * for the block that follows it.
 */

struct frui_internal {
	uint8_t version;
	uint8_t data[];
};

struct frui_chassis {
	uint8_t version;

	enum frui_chassis_type type;
	int len;

	struct frui_stringbuf_head fields;
};

struct frui_board {
	uint8_t version;
	uint8_t lang;
	uint32_t mfg_date;

	int len;

	struct frui_stringbuf_head fields;
};

struct frui_product {
	int version;
	int len;
	int lang;

	struct frui_stringbuf_head fields;
};

struct frui_warning {
	char *msg;
	TAILQ_ENTRY(frui_warning) entries;
};

static void error(frui_parser *parser, const char *fmt) {
	/* If multiple errors occurred, defer: the first one is probably
	 * the most informative */
	if(parser->error)
		return;

	/* Since errors might be about memory allocation, we don't
	 * get clever with copies here. Errors MUST be static. */
	parser->error = fmt;
}

static void warn(frui_parser *parser, const char *fmt, ...) {
	struct frui_warning *w;
	va_list ap;
	int n;

	if(!(w = calloc(1, sizeof(*w)))) {
		error(parser, "Error allocating memory for a warning!");
		if(w)
			free(w);
		return;
	}

	if(!(w->msg = calloc(1, 256))) {
		free(w);
		error(parser, "Error allocating memory for a warning!");
		return;
	}

	n = sprintf(w->msg, "at 0x%04x: ", parser->off);

	va_start(ap, fmt);
	n = vsnprintf(w->msg+n, 255-n, fmt, ap);
	va_end(ap);

	if(n < 0) {
		free(w->msg);
		free(w);
		error(parser, "Error formatting a warning!");
		return;
	}

	TAILQ_INSERT_TAIL(&parser->warnings, w, entries);
}

frui_parser *frui_parser_new(void) {
	frui_parser *parser;

	if(!(parser = calloc(1, sizeof(*parser))))
		return(NULL);

	*parser = (struct frui_parser){
		.off = -1,
	};

	TAILQ_INIT(&parser->warnings);

	return(parser);
}

void frui_parser_free(frui_parser *parser) {
	char *w;

	if(parser->frui)
		frui_free(parser->frui);

	while((w = frui_parser_get_warning(parser)))
		free(w);

	free(parser);
}

static enum frui_parser_state get_next_state(frui_parser *p) {
	struct frui *frui = p->frui;

	if(frui->int_off && !p->int_blk)
		return INTERNAL;

	if(frui->chs_off && !p->chs_blk)
		return CHASSIS;

	if(frui->brd_off && !p->brd_blk)
		return BOARD;

	if(frui->prd_off && !p->prd_blk)
		return PRODUCT;

	return(DONE);
}

int scan_inc(frui_parser *p, uint8_t input) {

	struct frui_stringbuf *sb = p->stringbuf;

	p->off++;
	p->sum += input;

	switch(p->state) {
		case HEADER: {
			/* Buffer content until we fill 8 bytes */
			p->buf[p->buf_occ++] = input;
			if(p->buf_occ < 8)
				return(0);

			/* Allocate and initialize FRU structure */
			if(!(p->frui = calloc(1, sizeof(*p->frui)))) {
				error(p, "Failed to allocate memory!");
				return(-1);
			}
			*p->frui = (struct frui){
				.version = p->buf[0],
				.int_off = p->buf[1] * 8,
				.chs_off = p->buf[2] * 8,
				.brd_off = p->buf[3] * 8,
				.prd_off = p->buf[4] * 8,
				.mr_off = p->buf[5] * 8,
			};

			if(p->buf[0] != 0x01)
				warn(p, "IPMI FRU header didn't have version 0x01! (0x%02x)", p->buf[0]);

			if(p->buf[6])
				warn(p, "Header PAD character was nonzero! (0x%02x)", p->buf[6]);

			if(p->sum)
				warn(p, "Header checksum didn't validate! (0x%02x 0x%02x)",
						p->sum,
						p->buf[0] + p->buf[1] + p->buf[2] + p->buf[3] + p->buf[4] + p->buf[5]);

			/* I assume this parser is sometimes used when
			 * we aren't sure whether storage contains a
			 * valid IPMI FRU block. To counter this, we're
			 * a little pickier with the header block than
			 * with the remaining blocks: if the header
			 * isn't formatted correctly, we return an error.
			 */
			if(p->buf[0] != 0x01 || p->buf[6] || p->sum) {
				free(p->frui);
				p->frui = NULL;
				return(-1);
			}

			/* Figure out where to go next */
			p->state = get_next_state(p);
			p->buf_occ = 0;
			return(0);
		}

		case INTERNAL:
			/* Wait until we bump into the internal block */
			if(p->off < p->frui->int_off)
				return(0);

			/* Header */
			if(!p->int_blk) {
				/* Figure out how big the internal block is */
				p->internal_max_size = 0;
				if(p->frui->chs_off)
					p->internal_max_size = p->frui->chs_off - p->off - 1;
				else if(p->frui->brd_off)
					p->internal_max_size = p->frui->brd_off - p->off - 1;
				else if(p->frui->prd_off)
					p->internal_max_size = p->frui->prd_off - p->off - 1;
				else if(p->frui->mr_off)
					p->internal_max_size = p->frui->mr_off - p->off - 1;

				if(!p->internal_max_size) {
					/* Parser limitation: can't figure
					 * out where internal blocks end!
					 * We ordinarily use the following
					 * block as a terminator, but this
					 * FRUI doesn't have one. */
					error(p, "Unterminated INTERNAL block!  Can't parse this FRUI.");
					return(-1);
				}

				if(!(p->int_blk = calloc(sizeof(*p->int_blk) + p->internal_max_size, 1))) {
					error(p, "Error allocating memory!");
					return(-1);
				}
				*p->int_blk = (struct frui_internal){
					.version = 1,
				};

				p->cur = 0;
				return(0);
			}

			/* Data */
			p->int_blk->data[p->cur++] = input;
			if(p->cur == p->internal_max_size) {
				p->state = get_next_state(p);
				p->buf_occ = 0;
			}
			return(0);

		case CHASSIS:

			/* Wait until we bump into the chassis block */
			if(p->off < p->frui->chs_off)
				return(0);

			if(!p->chs_blk) {
				/* Buffer content until we fill 3 bytes */
				p->buf[p->buf_occ++] = input;
				if(p->buf_occ < 3)
					return(0);

				/* Prime rolling checksum */
				p->sum = p->buf[0] + p->buf[1] + p->buf[2];

				/* Header */
				if(!(p->chs_blk = calloc(sizeof(*p->chs_blk), 1))) {
					error(p, "Error allocating memory!");
					return(-1);
				}
				*p->chs_blk = (struct frui_chassis){
					.version = p->buf[0],
					.len = p->buf[1]*8,
					.type = p->buf[2],
				};
				TAILQ_INIT(&p->chs_blk->fields);

				/* Validate header */
				if(p->chs_blk->version != 0x1) {
					p->chs_blk->version = 0x1;
					warn(p, "Clobbered unexpected version byte 0x%02x with 0x%02x",
							p->buf[0],
							p->chs_blk->version);
				}

				if(!p->chs_blk->type || p->chs_blk->type > FRU_CHASSIS_LAST) {
					p->chs_blk->type = FRU_CHASSIS_OTHER;
					warn(p, "Clobbered unexpected type 0x%02x with FRU_CHASSIS_OTHER",
							p->buf[2]);
				}

				/* Read strings */
				p->state_stringret = p->state;
				p->stringbuf = NULL;
				p->stringbuf_head = &p->chs_blk->fields;
				p->state = STRING;

				return(0);
			}

			/* Finished parsing strings; wait for checksum */
			if(p->off < p->frui->chs_off + p->chs_blk->len - 1)
				return(0);

			p->state = get_next_state(p);
			p->buf_occ = 0;
			return(0);

		case BOARD:

			/* Wait until we bump into the board block */
			if(p->off < p->frui->brd_off)
				return(0);

			if(!p->brd_blk) {
				/* Buffer content until we fill 6 bytes */
				p->buf[p->buf_occ++] = input;
				if(p->buf_occ < 6)
					return(0);

				/* Prime rolling checksum */
				p->sum = p->buf[0] + p->buf[1] + p->buf[2] + p->buf[3] + p->buf[4] + p->buf[5];

				/* Header */
				if(!(p->brd_blk = calloc(sizeof(*p->brd_blk), 1))) {
					error(p, "Error allocating memory!");
					return(-1);
				}
				*p->brd_blk = (struct frui_board){
					.version = p->buf[0],
					.len = p->buf[1]*8,
					.lang = p->buf[2],
					.mfg_date = p->buf[3] | p->buf[4]<<8 | p->buf[5]<<16,
				};
				TAILQ_INIT(&p->brd_blk->fields);

				/* Validate header */
				if(p->brd_blk->version != 0x1) {
					p->brd_blk->version = 0x1;
					warn(p, "Clobbered unexpected version byte 0x%02x with 0x%02x",
							p->buf[0],
							p->brd_blk->version);
				}

				/* Read strings */
				p->state_stringret = p->state;
				p->stringbuf = NULL;
				p->stringbuf_head = &p->brd_blk->fields;
				p->state = STRING;

				return(0);
			}

			/* Finished parsing strings; wait for checksum */
			if(p->off < p->frui->brd_off + p->brd_blk->len - 1)
				return(0);

			p->state = get_next_state(p);
			p->buf_occ = 0;
			return(0);

		case PRODUCT:

			/* Wait until we bump into the board block */
			if(p->off < p->frui->prd_off)
				return(0);

			if(!p->prd_blk) {
				/* Buffer content until we fill 3 bytes */
				p->buf[p->buf_occ++] = input;
				if(p->buf_occ < 3)
					return(0);

				/* Prime rolling checksum */
				p->sum = p->buf[0] + p->buf[1] + p->buf[2];

				/* Header */
				if(!(p->prd_blk = calloc(sizeof(*p->prd_blk), 1))) {
					error(p, "Error allocating memory!");
					return(-1);
				}
				*p->prd_blk = (struct frui_product){
					.version = p->buf[0],
					.len = p->buf[1]*8,
					.lang = p->buf[2],
				};
				TAILQ_INIT(&p->prd_blk->fields);

				/* Validate header */
				if(p->prd_blk->version != 0x1) {
					p->prd_blk->version = 0x1;
					warn(p, "Clobbered unexpected version byte 0x%02x with 0x%02x",
							p->buf[0],
							p->prd_blk->version);
				}

				/* Read strings */
				p->state_stringret = p->state;
				p->stringbuf = NULL;
				p->stringbuf_head = &p->prd_blk->fields;
				p->state = STRING;

				return(0);
			}

			/* Finished parsing strings; wait for checksum */
			if(p->off < p->frui->prd_off + p->prd_blk->len - 1)
				return(0);

			p->state = get_next_state(p);
			p->buf_occ = 0;
			return(0);

		case STRING: {
			int len;

			/* We always enter this state at the beginning
			 * of the string (on the format/size byte), and
			 * leave it at the end of the string. */
			if(!sb) {
				/* 0xc1 flags end of strings */
				if(input == 0xc1) {
					p->state = p->state_stringret;
					return 0;
				}

				len = input & 0x3f;

				sb = calloc(1, sizeof(*p->stringbuf)+len+1); /* 1-byte null padding */
				*sb = (struct frui_stringbuf){
					.len = len,
					.type = input >> 6,
				};

				p->cur=0;

				if(!len) {
					/* Empty string: queue immediately */
					TAILQ_INSERT_TAIL(p->stringbuf_head, sb, entry);
					p->stringbuf = NULL;
				} else
					p->stringbuf = sb;
				return 0;
			}

			sb->data[p->cur++] = input;
			if(p->cur == sb->len) {
				p->cur = 0;
				TAILQ_INSERT_TAIL(p->stringbuf_head, sb, entry);
				p->stringbuf = NULL;
				return 0;
			}
			return 0;
		}

		case DONE:
			/* Do nothing but chew bytes */
			return(0);
	}

	error(p, "Invalid state!");
	return(-1);
}

void frui_free(frui *frui) {
	frui_stringbuf *sb;

	if(frui) {
		if(frui->int_blk)
			free(frui->int_blk);

		if(frui->chs_blk) {
			while(frui->chs_blk->fields.tqh_first) {
				sb = frui->chs_blk->fields.tqh_first;
				TAILQ_REMOVE(&frui->chs_blk->fields, sb, entry);
				free(sb);
			}
			free(frui->chs_blk);
		}

		if(frui->brd_blk) {
			while(frui->brd_blk->fields.tqh_first) {
				sb = frui->brd_blk->fields.tqh_first;
				TAILQ_REMOVE(&frui->brd_blk->fields, sb, entry);
				free(sb);
			}
			free(frui->brd_blk);
		}

		if(frui->prd_blk) {
			while(frui->prd_blk->fields.tqh_first) {
				sb = frui->prd_blk->fields.tqh_first;
				TAILQ_REMOVE(&frui->prd_blk->fields, sb, entry);
				free(sb);
			}
			free(frui->prd_blk);
		}

		free(frui);
	}
}

struct frui *frui_parser_loadb(frui_parser *parser, size_t len, const uint8_t *buf) {
	frui *frui;
	const uint8_t *cur;

	for(cur=buf; cur<buf+len; cur++)
		if(scan_inc(parser, *cur) != 0)
			return NULL;

	if(parser->state == DONE) {
		frui = parser->frui;

		frui->int_blk = parser->int_blk;
		frui->chs_blk = parser->chs_blk;
		frui->brd_blk = parser->brd_blk;
		frui->prd_blk = parser->prd_blk;

		parser->int_blk = NULL;
		parser->chs_blk = NULL;
		parser->brd_blk = NULL;
		parser->prd_blk = NULL;

		parser->frui = NULL;
		return(frui);
	}

	error(parser, "Ran out of data before the FRUI ended!");
	return NULL;
}

struct frui *frui_parser_loadf(frui_parser *parser, FILE *f) {
	frui *frui;
	uint8_t x;

	while(!feof(f)) {
		x = fgetc(f);
		if(scan_inc(parser, x) != 0)
			return NULL;
	}

	if(parser->state == DONE) {
		frui = parser->frui;

		frui->int_blk = parser->int_blk;
		frui->chs_blk = parser->chs_blk;
		frui->brd_blk = parser->brd_blk;
		frui->prd_blk = parser->prd_blk;

		parser->int_blk = NULL;
		parser->chs_blk = NULL;
		parser->brd_blk = NULL;
		parser->prd_blk = NULL;

		parser->frui = NULL;
		return(frui);
	}

	error(parser, "Ran out of data before the FRUI ended!");
	return NULL;
}

/*
 * Field retrieval functions. Since the chassis, board, and product
 * blocks look pretty similar, we generate three functions using
 * a single macro. The functions defined are:
 *
 *    const char *frui_get_chassis_field(frui *frui, int index);
 *    const char *frui_get_board_field(frui *frui, int index);
 *    const char *frui_get_product_field(frui *frui, int index);
 *
 * In all three cases, the index is 0-based and includes mandatory
 * fields.
 */

#define __BLOCK_RETRIEVAL_FUNCTION(__name, __blkname)		\
const char *__name(frui *frui, int index) {			\
	int i=0;						\
	struct frui_stringbuf *sb;				\
								\
	if(!frui || !frui->__blkname || index < 0)		\
		return NULL;					\
								\
	for(sb=frui->__blkname->fields.tqh_first;		\
			sb;					\
			sb=sb->entry.tqe_next)			\
								\
		if(i++ == index)				\
			return sb->data;			\
								\
	return(NULL);						\
}

__BLOCK_RETRIEVAL_FUNCTION(frui_get_chassis_field, chs_blk)
__BLOCK_RETRIEVAL_FUNCTION(frui_get_board_field, brd_blk)
__BLOCK_RETRIEVAL_FUNCTION(frui_get_product_field, prd_blk)

int frui_has_internal_info(frui *frui)	{ return !!frui->int_blk; }
int frui_has_chassis_info(frui *frui)	{ return !!frui->chs_blk; }
int frui_has_board_info(frui *frui)	{ return !!frui->brd_blk; }
int frui_has_product_info(frui *frui)	{ return !!frui->prd_blk; }

const uint8_t *frui_get_internal_data(frui *frui) {
	if(!frui || !frui->int_blk)
		return 0;
	return frui->int_blk->data;
}

enum frui_chassis_type frui_get_chassis_type(frui *frui) {
	if(!frui || !frui->chs_blk)
		return 0;
	return frui->chs_blk->type;
}

uint8_t frui_get_board_language_code(frui *frui) {
	if(!frui || !frui->brd_blk)
		return 0;
	return frui->brd_blk->lang;
}

uint32_t frui_get_board_timestamp(frui *frui) {
	if(!frui || !frui->brd_blk)
		return 0;
	return frui->brd_blk->mfg_date;
}

uint8_t frui_get_product_language_code(frui *frui) {
	if(!frui || !frui->prd_blk)
		return 0;
	return frui->prd_blk->lang;
}

/*
 * Error handling
 */

/* Errors are statically allocated, since some of them correspond to
 * memory-allocation bugs. They do not need to be free()d. */
const char *frui_parser_get_error(frui_parser *parser) {
	return parser->error;
}

/* Warnings do need to be free()d, since there are multiple ones. This
 * function pulls a single warning off the stack and returns a copy. */
char *frui_parser_get_warning(frui_parser *parser) {
	struct frui_warning *w;
	char *msg;

	if((w = parser->warnings.tqh_first)) {
		msg = w->msg;
		TAILQ_REMOVE(&parser->warnings, w, entries);
		free(w);
		return msg;
	}

	return NULL;
}

#ifdef __FRUI_TESTCODE
void frui_dump(frui *frui, FILE *f) {

	if(frui_has_chassis_info(frui)) {
		fprintf(f, "Chassis block\n------------\n\n");
		fprintf(f, " -> Part number:\t%s\n", frui_get_chassis_part_number(frui));
		fprintf(f, " -> Serial number:\t%s\n", frui_get_chassis_serial_number(frui));
		fprintf(f, "\n");
	}

	if(frui_has_board_info(frui)) {
		fprintf(f, "Board block\n-----------\n\n");
		fprintf(f, "Language 0x%02x, date 0x%06x\n",
				frui_get_board_language_code(frui),
				frui_get_board_timestamp(frui));
		fprintf(f, " -> Manufacturer:\t%s\n", frui_get_board_manufacturer(frui));
		fprintf(f, " -> Product Name:\t%s\n", frui_get_board_name(frui));
		fprintf(f, " -> Serial Number:\t%s\n", frui_get_board_serial_number(frui));
		fprintf(f, " -> Part Number:\t%s\n", frui_get_board_part_number(frui));
		fprintf(f, " -> FRU File ID:\t%s\n", frui_get_board_fru_file_id(frui));
		fprintf(f, "\n");
	}

	if(frui_has_product_info(frui)) {
		fprintf(f, "Product block\n-------------\n\n");
		fprintf(f, "Language 0x%02x\n", frui_get_product_language_code(frui));
		fprintf(f, " -> Manufacturer:\t%s\n", frui_get_product_manufacturer(frui));
		fprintf(f, " -> Product Name:\t%s\n", frui_get_product_name(frui));
		fprintf(f, " -> Part Number:\t%s\n", frui_get_product_part_number(frui));
		fprintf(f, " -> Version Number:\t%s\n", frui_get_product_version_number(frui));
		fprintf(f, " -> Serial Number:\t%s\n", frui_get_product_serial_number(frui));
		fprintf(f, " -> Asset Tag:  \t%s\n", frui_get_product_asset_tag(frui));
		fprintf(f, " -> FRU File ID:\t%s\n", frui_get_product_fru_file_id(frui));
		fprintf(f, "\n");
	}
}

int main(void) {
	frui_parser *parser;
	frui *frui;
	char *warning;

	parser = frui_parser_new();
	assert(parser);

	if(!(frui = frui_parser_loadf(parser, stdin))) {
		puts(frui_parser_get_error(parser));
		frui_parser_free(parser);
		return(-1);
	}

	while((warning = frui_parser_get_warning(parser))) {
		printf("Got warning '%s'\n", warning);
		free(warning);
	}

	frui_dump(frui, stdout);

	frui_free(frui);
	frui_parser_free(parser);

	return(0);
}
#endif
