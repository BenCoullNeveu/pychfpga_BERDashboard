#ifndef __ICEBOARD_IPMI_H__
#define __ICEBOARD_IPMI_H__

typedef struct ipmi_struct {
	uint8_t version;

	struct ipmi_chassis_area {
		uint8_t type;
		char *part_number;
		char *serial_number;
	} *chassis_area;

	struct ipmi_board_area {
	} *board_area;

	struct ipmi_product_area {
	} *product_area;

	struct ipmi_multirecord_area {
	} *multirecord_area;
} ipmi_struct;

#endif
