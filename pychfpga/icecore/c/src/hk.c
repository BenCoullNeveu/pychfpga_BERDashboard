#include <tuber.h>
#include <string.h>

#include "iceboard.h"
#include "runtime.h"
#include "support.h"

tuber_property(iceboard, MOTHERBOARD_TEMPERATURE_POWER, json_string(MOTHERBOARD_TEMPERATURE_POWER));
tuber_property(iceboard, MOTHERBOARD_TEMPERATURE_ARM, json_string(MOTHERBOARD_TEMPERATURE_ARM));
tuber_property(iceboard, MOTHERBOARD_TEMPERATURE_FPGA, json_string(MOTHERBOARD_TEMPERATURE_FPGA));
tuber_property(iceboard, MOTHERBOARD_TEMPERATURE_PHY, json_string(MOTHERBOARD_TEMPERATURE_PHY));

tuber_method(iceboard, DOUBLE, get_motherboard_temperature,
	"Retrieve the temperature from one of the motherboard's sensors.",
	1, ((STRING_CONST, sensor, NULL, "Which sensor? (See description below)")),
	"The following motherboard temperature sensors are recognized:\n"
	"	U34: MOTHERBOARD_TEMPERATURE_POWER, between the two 1.0V bucks,\n"
	"	U35: MOTHERBOARD_TEMPERATURE_FPGA, near USER SMA A,\n"
	"	U36: MOTHERBOARD_TEMPERATURE_ARM, under the CPU shield, and\n"
	"	U37: MOTHERBOARD_TEMPERATURE_PHY, also under the CPU shield.\n"
) {
	FILE *f=NULL;
	int i;

	if(!strcmp(MOTHERBOARD_TEMPERATURE_POWER, sensor))
		f = fopen("/sys/bus/i2c/devices/12-0048/temp1_input", "r");
	else if(!strcmp(MOTHERBOARD_TEMPERATURE_ARM, sensor))
		f = fopen("/sys/bus/i2c/devices/12-004a/temp1_input", "r");
	else if(!strcmp(MOTHERBOARD_TEMPERATURE_FPGA, sensor))
		f = fopen("/sys/bus/i2c/devices/12-004b/temp1_input", "r");
	else if(!strcmp(MOTHERBOARD_TEMPERATURE_PHY, sensor))
		f = fopen("/sys/bus/i2c/devices/12-004c/temp1_input", "r");
	else {
		oops("Unknown motherboard temperature sensor '%s'", sensor);
		return(0);
	}

	fscanf(f, "%i", &i);
	fclose(f);

	return(i / 1000.);
}

tuber_property(iceboard, MOTHERBOARD_RAIL_VCC3V3, json_string(MOTHERBOARD_RAIL_VCC3V3));
tuber_property(iceboard, MOTHERBOARD_RAIL_VCC12V0, json_string(MOTHERBOARD_RAIL_VCC12V0));
tuber_property(iceboard, MOTHERBOARD_RAIL_VCC5V5, json_string(MOTHERBOARD_RAIL_VCC5V5));
tuber_property(iceboard, MOTHERBOARD_RAIL_VCC1V0_GTX, json_string(MOTHERBOARD_RAIL_VCC1V0_GTX));
tuber_property(iceboard, MOTHERBOARD_RAIL_VCC1V0, json_string(MOTHERBOARD_RAIL_VCC1V0));
tuber_property(iceboard, MOTHERBOARD_RAIL_VCC1V2, json_string(MOTHERBOARD_RAIL_VCC1V2));
tuber_property(iceboard, MOTHERBOARD_RAIL_VCC1V5, json_string(MOTHERBOARD_RAIL_VCC1V5));
tuber_property(iceboard, MOTHERBOARD_RAIL_VCC1V8, json_string(MOTHERBOARD_RAIL_VCC1V8));
tuber_property(iceboard, MOTHERBOARD_RAIL_VADJ, json_string(MOTHERBOARD_RAIL_VADJ));

tuber_method(iceboard, DOUBLE, get_motherboard_voltage,
	"Retrieve the voltage from one of the motherboard's sensors.",
	1, ((STRING_CONST, rail, NULL, "Which rail? (See description below)")),
	"The following motherboard rails are instrumented:\n"
	"	MOTHERBOARD_RAIL_VCC3V3,\n"
	"	MOTHERBOARD_RAIL_VCC12V0,\n"
	"	MOTHERBOARD_RAIL_VCC5V5,\n"
	"	MOTHERBOARD_RAIL_VCC1V0_GTX,\n"
	"	MOTHERBOARD_RAIL_VCC1V0,\n"
	"	MOTHERBOARD_RAIL_VCC1V2,\n"
	"	MOTHERBOARD_RAIL_VCC1V5,\n"
	"	MOTHERBOARD_RAIL_VCC1V8, and\n"
	"	MOTHERBOARD_RAIL_VADJ."
) {
	FILE *f=NULL;
	int i;

	if(!strcmp(MOTHERBOARD_RAIL_VCC12V0, rail))
		f = fopen("/sys/bus/i2c/devices/10-0047/in1_input", "r");
	else if(!strcmp(MOTHERBOARD_RAIL_VCC5V5, rail))
		f = fopen("/sys/bus/i2c/devices/10-0048/in1_input", "r");
	else if(!strcmp(MOTHERBOARD_RAIL_VCC3V3, rail))
		f = fopen("/sys/bus/i2c/devices/10-0049/in1_input", "r");
	else if(!strcmp(MOTHERBOARD_RAIL_VADJ, rail))
		f = fopen("/sys/bus/i2c/devices/10-0043/in1_input", "r");
	else if(!strcmp(MOTHERBOARD_RAIL_VCC1V8, rail))
		f = fopen("/sys/bus/i2c/devices/10-004b/in1_input", "r");
	else if(!strcmp(MOTHERBOARD_RAIL_VCC1V5, rail))
		f = fopen("/sys/bus/i2c/devices/10-004c/in1_input", "r");
	else if(!strcmp(MOTHERBOARD_RAIL_VCC1V2, rail))
		f = fopen("/sys/bus/i2c/devices/10-004d/in1_input", "r");
	else if(!strcmp(MOTHERBOARD_RAIL_VCC1V0, rail))
		f = fopen("/sys/bus/i2c/devices/10-004e/in1_input", "r");
	else if(!strcmp(MOTHERBOARD_RAIL_VCC1V0_GTX, rail))
		f = fopen("/sys/bus/i2c/devices/10-004f/in1_input", "r");
	else {
		oops("Unknown motherboard power rail '%s'", rail);
		return(0);
	}


	fscanf(f, "%i", &i);
	fclose(f);

	return(i / 1000.);
}

