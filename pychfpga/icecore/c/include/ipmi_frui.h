#ifndef __IPMI_FRUI__
#define __IPMI_FRUI__

#include <sys/queue.h>
#include <stdint.h>

/*
 * Accessible structures
 */

typedef struct frui_parser frui_parser;
typedef struct frui frui;

/*
 * Parsing and reference management
 */

frui_parser *frui_parser_new(void);
frui *frui_parser_loadf(frui_parser *, FILE *);
frui *frui_parser_loadb(frui_parser *, size_t, const uint8_t *);
void frui_parser_free(frui_parser *);
void frui_free(frui *);

const char *frui_parser_get_error(frui_parser *);
char *frui_parser_get_warning(frui_parser *);

/*
 * Internal block
 */

int frui_has_internal_info(frui *);
const uint8_t *frui_get_internal_data(frui *);

/*
 * Chassis block
 */

int frui_has_chassis_info(frui *);
enum frui_chassis_type frui_get_chassis_type(frui *);
const char *frui_get_chassis_field(frui *, int);

#define frui_get_chassis_part_number(frui)	frui_get_chassis_field(frui, 0)
#define frui_get_chassis_serial_number(frui)	frui_get_chassis_field(frui, 1)

/*
 * Board block
 */

int frui_has_board_info(frui *);
uint8_t frui_get_board_language_code(frui *);
uint32_t frui_get_board_timestamp(frui *);
const char *frui_get_board_field(frui *, int);

#define frui_get_board_manufacturer(frui)	frui_get_board_field(frui, 0)
#define frui_get_board_name(frui)		frui_get_board_field(frui, 1)
#define frui_get_board_serial_number(frui)	frui_get_board_field(frui, 2)
#define frui_get_board_part_number(frui)	frui_get_board_field(frui, 3)
#define frui_get_board_fru_file_id(frui)	frui_get_board_field(frui, 4)

/*
 * Product block
 */

int frui_has_product_info(frui *);
uint8_t frui_get_product_language_code(frui *);
const char *frui_get_product_field(frui *, int);

#define frui_get_product_manufacturer(frui)	frui_get_product_field(frui, 0)
#define frui_get_product_name(frui)		frui_get_product_field(frui, 1)
#define frui_get_product_part_number(frui)	frui_get_product_field(frui, 2)
#define frui_get_product_version_number(frui)	frui_get_product_field(frui, 3)
#define frui_get_product_serial_number(frui)	frui_get_product_field(frui, 4)
#define frui_get_product_asset_tag(frui)	frui_get_product_field(frui, 5)
#define frui_get_product_fru_file_id(frui)	frui_get_product_field(frui, 6)

/*
 * Chassis types
 */

enum frui_chassis_type {
	FRU_CHASSIS_OTHER=0x01,
	FRU_CHASSIS_UNKNOWN=0x02,
	FRU_CHASSIS_DESKTOP=0x03,
	FRU_CHASSIS_DESKTOP_LOW_PROFILE=0x04,
	FRU_CHASSIS_PIZZA_BOX=0x05,
	FRU_CHASSIS_MINI_TOWER=0x06,
	FRU_CHASSIS_TOWER=0x07,
	FRU_CHASSIS_PORTABLE=0x08,
	FRU_CHASSIS_LAPTOP=0x09,
	FRU_CHASSIS_NOTEBOOK=0x0A,
	FRU_CHASSIS_HANDHELD=0x0B,
	FRU_CHASSIS_DOCKING_STATION=0x0C,
	FRU_CHASSIS_ALL_IN_ONE=0x0D,
	FRU_CHASSIS_SUBNOTEBOOK=0x0E,
	FRU_CHASSIS_SPACE_SAVING=0x0F,
	FRU_CHASSIS_LUNCH_BOX=0x10,
	FRU_CHASSIS_MAIN_SERVER=0x11,
	FRU_CHASSIS_EXPANSION=0x12,
	FRU_CHASSIS_SUBCHASSIS=0x13,
	FRU_CHASSIS_BUS_EXPANSION=0x14,
	FRU_CHASSIS_PERIPHERAL=0x15,
	FRU_CHASSIS_RAID=0x16,
	FRU_CHASSIS_RACK_MOUNT=0x17,
	FRU_CHASSIS_SEALED_CASE_PC=0x18,
	FRU_CHASSIS_MULTI=0x19,
	FRU_CHASSIS_COMPACT_PCI=0x1a,
	FRU_CHASSIS_ADVANCED_TCA=0x1b,
	FRU_CHASSIS_BLADE=0x1c,
	FRU_CHASSIS_BLADE_ENCLOSURE=0x1d,
};
#define FRU_CHASSIS_LAST FRU_CHASSIS_BLADE_ENCLOSURE

#endif
