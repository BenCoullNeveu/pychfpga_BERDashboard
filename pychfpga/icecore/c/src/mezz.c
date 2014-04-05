#include <tuber.h>
#include <string.h>

#include "iceboard.h"
#include "runtime.h"
#include "support.h"
#include "iceboard_hw.h"

tuber_method(iceboard, VOID, set_mezzanine_power,
		"Turn on/off an FMC mezzanine",
		2, (
			(INTEGER, mezzanine, NULL, "Mezzanine number (1/2)"),
			(BOOLEAN, power, json_true(), "True or False")
		),
		"Rails are powered in the following order:\n"
		"   * Vadj,\n"
		"   * 3.3v,\n"
		"   * 12v\n"
		"Power-off sequencing follows the same process in reverse. "
		"FMC specifications state (Obs. 5.28) that any power "
		"sequencing is acceptable; the ICEboard's hardware is "
		"capable of accomodating arbitrary rail ordering (but "
		"software does not play along at the moment.)"
) {
	struct {
		struct iceboard_gpio *rail_12v0;
		struct iceboard_gpio *rail_3v3;
		struct iceboard_gpio *rail_vadj;
		struct iceboard_gpio *pg_c2m;
	} rails[2] = {
		{
			.rail_12v0 = get_gpio_by_netname("FMCA_EN_12V0"),
			.rail_3v3 = get_gpio_by_netname("FMCA_EN_3V3"),
			.rail_vadj = get_gpio_by_netname("FMCA_EN_VADJ"),
			.pg_c2m = get_gpio_by_netname("FMCA_PG_C2M"),
		}, {
			.rail_12v0 = get_gpio_by_netname("FMCB_EN_12V0"),
			.rail_3v3 = get_gpio_by_netname("FMCB_EN_3V3"),
			.rail_vadj = get_gpio_by_netname("FMCB_EN_VADJ"),
			.pg_c2m = get_gpio_by_netname("FMCB_PG_C2M"),
		}
	};

	VALIDATE_BETWEEN(mezzanine, 1, 2,);
	VALIDATE_ASSERT(rails[0].rail_12v0 && rails[0].rail_3v3 && rails[0].rail_vadj,);
	VALIDATE_ASSERT(rails[1].rail_12v0 && rails[1].rail_3v3 && rails[1].rail_vadj,);

	if(power) {
		gpio_set(rails[mezzanine-1].rail_12v0, 1);
		gpio_set(rails[mezzanine-1].rail_3v3, 1);
		gpio_set(rails[mezzanine-1].rail_vadj, 1);
		gpio_set(rails[mezzanine-1].pg_c2m, 1);
	} else {
		gpio_set(rails[mezzanine-1].pg_c2m, 0);
		gpio_set(rails[mezzanine-1].rail_vadj, 0);
		gpio_set(rails[mezzanine-1].rail_3v3, 0);
		gpio_set(rails[mezzanine-1].rail_12v0, 0);
	}
}

tuber_method(iceboard, BOOLEAN, get_mezzanine_power,
		"Retrieve the current power status of an FMC mezzanine",
		1, ((INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")),
		"This method only tells you whether an FMC mezzanine's power "
		"switches are ON. It does not inspect the power quality."
) {
	struct iceboard_gpio *rail_12v0[2] = {
		get_gpio_by_netname("FMCA_EN_12V0"),
		get_gpio_by_netname("FMCB_EN_12V0"),
	};

	VALIDATE_BETWEEN(mezzanine, 1, 2, 0);
	VALIDATE_ASSERT(rail_12v0[0] && rail_12v0[1], 0);
	return(gpio_get(rail_12v0[mezzanine-1], 0));
}

tuber_property(iceboard, MEZZANINE_RAIL_VCC3V3, json_string(MEZZANINE_RAIL_VCC3V3));
tuber_property(iceboard, MEZZANINE_RAIL_VCC12V0, json_string(MEZZANINE_RAIL_VCC12V0));
tuber_property(iceboard, MEZZANINE_RAIL_VADJ, json_string(MEZZANINE_RAIL_VADJ));

tuber_method(iceboard, DOUBLE, get_mezzanine_voltage,
		"Retrieve the voltage from one of the mezzanine's sensors.",
		2, (
			(INTEGER, mezzanine, NULL, "Mezzanine number (1/2)"),
			(STRING_CONST, rail, NULL, "Which rail? (See description below)")
		),
		"The following mezzanine rails are instrumented:\n"
		"	MEZZANINE_RAIL_VCC3V3,\n"
		"	MEZZANINE_RAIL_VCC12V0,\n"
		"	MEZZANINE_RAIL_VADJ.\n"
		"All the returned voltages are measured *after* the FMC "
		"power switch. So, when the FMC is switched off, you "
		"should expect to measure about 0 V."
) {
	FILE *f=NULL;
	int i;

	VALIDATE_BETWEEN(mezzanine, 1, 2, 0);

	if(mezzanine == 1) {
		if(!strcmp(MEZZANINE_RAIL_VCC12V0, rail))
			f = fopen("/sys/bus/i2c/devices/10-0040/in1_input", "r");
		else if(!strcmp(MEZZANINE_RAIL_VCC3V3, rail))
			f = fopen("/sys/bus/i2c/devices/10-0041/in1_input", "r");
		else if(!strcmp(MEZZANINE_RAIL_VADJ, rail))
			f = fopen("/sys/bus/i2c/devices/10-0042/in1_input", "r");
	} else {
		if(!strcmp(MEZZANINE_RAIL_VCC12V0, rail))
			f = fopen("/sys/bus/i2c/devices/10-0044/in1_input", "r");
		else if(!strcmp(MEZZANINE_RAIL_VCC3V3, rail))
			f = fopen("/sys/bus/i2c/devices/10-0045/in1_input", "r");
		else if(!strcmp(MEZZANINE_RAIL_VADJ, rail))
			f = fopen("/sys/bus/i2c/devices/10-0046/in1_input", "r");
	}
	if(!f) {
		oops("Unknown mezzanine power rail '%s'", rail);
		return(0);
	}

	fscanf(f, "%i", &i);
	fclose(f);

	return(i / 1000.);
}

