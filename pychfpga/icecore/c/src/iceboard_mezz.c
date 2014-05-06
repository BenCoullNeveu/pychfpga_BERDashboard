#include <tuber.h>
#include <string.h>

#include "iceboard.h"
#include "runtime.h"
#include "support.h"
#include "iceboard_hw.h"

#include "i2c_eeprom.h"
#include "base64.h"
#include "ipmi_frui.h"

tuber_method(IceBoard, VOID, set_mezz_power,
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

tuber_method(IceBoard, BOOLEAN, get_mezz_power,
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

tuber_method(IceBoard, DOUBLE, get_mezz_voltage,
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

tuber_method(IceBoard, VOID, mezz_probe,
		"Probe mezzanine.",
		1, ((INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")),
		""
) {
	uint8_t buf[2048]; /* Not quite as big as possible, but pretty big */

	i2c_eeprom_handle *h=NULL;
	frui_parser *p=NULL;
	frui *frui=NULL;

	/* Read raw data from EEPROM */
	if(!(h = i2c_eeprom_open("/dev/i2c-5"))) {
		oops("Unable to open I2C EEPROM! Is there a mezzanine present?");
		goto out;
	}
	if(i2c_eeprom_read(h, buf, 0, sizeof(buf)) != sizeof(buf)) {
		oops("Error reading raw data from EEPROM!");
		goto out;
	}
	i2c_eeprom_close(h);
	h = NULL;

	/* Try to parse into FRUI structure */
	if(!(p = frui_parser_new()))
		goto out;
	if(!(frui = frui_parser_loadb(p, sizeof(buf), buf))) {
		oops("Failed to parse IPMI FRU block! (Is this an uninitialized mezzanine?)");
		goto out;
	}
	frui_parser_free(p);
	p = NULL;

	/* TODO: something, anything */

	frui_free(frui);

out:
	if(h)
		i2c_eeprom_close(h);
	if(p)
		frui_parser_free(p);
	if(frui)
		frui_free(frui);
}

tuber_method(IceBoard, VOID, mezz_eeprom_write,
		"Write the I2C EEPROM associated with a mezzanine.",
		3, (
			(INTEGER, mezzanine, NULL, "Mezzanine number (1/2)"),
			(STRING_CONST, b64, NULL, "EEPROM contents (base64 encoded)"),
			(INTEGER, offset, json_integer(0), "Offset (default: 0)")
		),
		"The 'offset' parameter specifies where the data begins on the "
		"EEPROM. IPMI blocks must begin at offset 0. There is no way, "
		"apart from reading back contents, to verify that you didn't "
		"overrun the EEPROM. If you did, you probably wrote data to the "
		"wrong place."
) {
	char *buf = NULL;
	int slen, blen;
	i2c_eeprom_handle *h = NULL;

	VALIDATE_BETWEEN(mezzanine, 1, NUM_MEZZ,);
	VALIDATE_BETWEEN(offset, 0, 131072,);

	if(!(h = i2c_eeprom_open("/dev/i2c-5"))) {
		oops("Unable to open I2C device file!");
		goto out;
	}

	if((slen = base64_validate_string(b64)) == -1) {
		oops("Invalid base-64 string supplied!");
		goto out;
	}

	blen = base64_size_blob(slen);
	if(!(buf = malloc(blen + 1))) {
		oops("Unable to allocate %i bytes for EEPROM block!", blen);
		goto out;
	}

	if(base64_decode_string(slen, b64, blen, buf) == -1) {
		oops("Error while decoding base-64 block!");
		goto out;
	}

	/* Write EEPROM */
	if(i2c_eeprom_write(h, buf, offset, blen) != blen)
		oops("Error during EEPROM write!");
	i2c_eeprom_close(h);

out:
	if(buf)
		free(buf);
	if(h)
		i2c_eeprom_close(h);
}
