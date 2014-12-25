#include <tuber.h>
#include <string.h>
#include <syslog.h>

#include "iceboard.h"
#include "runtime.h"
#include "support.h"
#include "iceboard_hw.h"

#include "i2c_eeprom.h"
#include "base64.h"

tuber_method(BOOLEAN, IceBoard, is_mezzanine_present,
		"Determines if a mezzanine is present.",
		1, ((INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")),
		2, (CATEGORY_ICEBOARD, CATEGORY_MEZZANINE),
		""
) {
	struct iceboard_gpio *present[2] = {
		get_gpio_by_netname("FMCA_PRSNT_M2C_L"),
		get_gpio_by_netname("FMCB_PRSNT_M2C_L"),
	};

	VALIDATE_BETWEEN(mezzanine, 1, 2, 0);
	VALIDATE_ASSERT(present[0] && present[1], 0);
	return gpio_get(present[mezzanine-1], 0) == 0;
}

tuber_method(VOID, IceBoard, set_mezzanine_power,
		"Turn on/off an FMC mezzanine",
		2, (
			(BOOLEAN, power, NULL, "True or False"),
			(INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")
		),
		2, (CATEGORY_ICEBOARD, CATEGORY_MEZZANINE),
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

	if(!IceBoard_is_mezzanine_present(self, mezzanine)) {
		oops("Mezzanine not present!");
		return;
	}

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

tuber_method(BOOLEAN, IceBoard, get_mezzanine_power,
		"Retrieve the current power status of an FMC mezzanine",
		1, ((INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")),
		2, (CATEGORY_ICEBOARD, CATEGORY_MEZZANINE),
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

tuber_method(DOUBLE, IceBoard, get_mezzanine_voltage,
		"Retrieve the voltage from one of the mezzanine's sensors.",
		2, (
			(STRING_CONST, rail, NULL, "Which rail? (See description below)"),
			(INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")
		),
		2, (CATEGORY_ICEBOARD, CATEGORY_MEZZANINE),
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

tuber_method(DOUBLE, IceBoard, get_mezzanine_current,
		"Retrieve the voltage from one of the mezzanine's sensors.",
		2, (
			(STRING_CONST, rail, NULL, "Which rail? (See description below)"),
			(INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")
		),
		2, (CATEGORY_ICEBOARD, CATEGORY_MEZZANINE),
		"The following mezzanine rails are instrumented:\n"
		"	MEZZANINE_RAIL_VCC3V3,\n"
		"	MEZZANINE_RAIL_VCC12V0,\n"
		"	MEZZANINE_RAIL_VADJ.\n"
		"All the returned currents are measured *after* the FMC "
		"power switch. So, when the FMC is switched off, you "
		"should expect to measure about 0 A."
) {
	FILE *f=NULL;
	int i;

	VALIDATE_BETWEEN(mezzanine, 1, 2, 0);

	if(!strcmp(MEZZANINE_RAIL_VCC12V0, rail))
		f = fopen(mezzanine==1 ?
				"/sys/bus/i2c/devices/10-0040/curr1_input" :
				"/sys/bus/i2c/devices/10-0044/curr1_input", "r");
	else if(!strcmp(MEZZANINE_RAIL_VCC3V3, rail))
		f = fopen(mezzanine==1 ?
				"/sys/bus/i2c/devices/10-0041/curr1_input" :
				"/sys/bus/i2c/devices/10-0045/curr1_input", "r");
	else if(!strcmp(MEZZANINE_RAIL_VADJ, rail))
		f = fopen(mezzanine==1 ?
				"/sys/bus/i2c/devices/10-0042/curr1_input" :
				"/sys/bus/i2c/devices/10-0046/curr1_input", "r");
	if(!f) {
		oops("Unknown mezzanine power rail '%s'", rail);
		return(0);
	}

	fscanf(f, "%i", &i);
	fclose(f);

	return(i / 1000.);
}

tuber_method(VOID, IceBoard, _mezzanine_eeprom_write_base64,
		"Write the I2C EEPROM associated with a mezzanine.",
		3, (
			(INTEGER, mezzanine, NULL, "Mezzanine number (1/2)"),
			(STRING_CONST, b64, NULL, "EEPROM contents (base64 encoded)"),
			(INTEGER, offset, json_integer(0), "Offset (default: 0)")
		),
		2, (CATEGORY_ICEBOARD, CATEGORY_MEZZANINE),
		"The 'offset' parameter specifies where the data begins on the "
		"EEPROM. IPMI blocks must begin at offset 0. There is no way, "
		"apart from reading back contents, to verify that you didn't "
		"overrun the EEPROM. If you did, you probably wrote data to the "
		"wrong place."
) {
	char *buf = NULL;
	int slen, blen;
	i2c_eeprom_handle *h = NULL;

	VALIDATE_BETWEEN(mezzanine, 1, NUM_MEZZANINES,);
	VALIDATE_BETWEEN(offset, 0, 131072,);

	pthread_mutex_lock(&self->mezz_i2c_lock);
	if(!(h = i2c_eeprom_open(mezzanine==1 ? "/dev/i2c-5" : "/dev/i2c-6"))) {
		oops("Unable to open I2C EEPROM! Is there a mezzanine present?");
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

out:
	pthread_mutex_unlock(&self->mezz_i2c_lock);

	if(buf)
		free(buf);
	if(h)
		i2c_eeprom_close(h);
}

tuber_method(INTEGER, IceBoard, _mezzanine_lock_ipmi_cache,
		"Increment IPMI cache lock counter; return new value",
		0, (),
		1, (CATEGORY_ICEBOARD),
		"This is an internal method. Don't use it."
) {
	int count;

	pthread_mutex_lock(&self->mezz_i2c_lock);
	count = ++self->mezz_frui_refcount;
	pthread_mutex_unlock(&self->mezz_i2c_lock);

	return count;
}

tuber_method(INTEGER, IceBoard, _mezzanine_unlock_ipmi_cache,
		"Increment IPMI cache lock counter; return new value",
		0, (),
		1, (CATEGORY_ICEBOARD),
		"This is an internal method. Don't use it."
) {
	int count;

	pthread_mutex_lock(&self->mezz_i2c_lock);
	count = --self->mezz_frui_refcount;
	pthread_mutex_unlock(&self->mezz_i2c_lock);

	return count;
}

frui *IceBoard_get_mezzanine_ipmi_raw(IceBoard *self, const int mezzanine) {
	/* MUST be called with mezz_frui_lock */

	uint8_t buf[2048]; /* Not quite as big as possible, but pretty big */
	char *warning;
	VALIDATE_BETWEEN(mezzanine, 1, 2, NULL);

	i2c_eeprom_handle *h=NULL;
	frui_parser *p=NULL;

	if(self->mezz_frui[mezzanine-1]) {
		/* We have a cached value. If the mezzanine is powered, or if
		 * we're in the middle of something, return it. (Expectation:
		 * that only a maniac would hot-swap a powered mezz.) */
		if(self->mezz_frui_refcount || IceBoard_get_mezzanine_power(self, mezzanine))
			return(self->mezz_frui[mezzanine-1]);

		/* Otherwise, invalidate the cached copy. We'll replace it. */
		frui_free(self->mezz_frui[mezzanine-1]);
		self->mezz_frui[mezzanine-1] = NULL;
	}

	/* Read raw data from EEPROM */
	pthread_mutex_lock(&self->mezz_i2c_lock);
	if(!(h = i2c_eeprom_open(mezzanine==1 ? "/dev/i2c-5" : "/dev/i2c-6"))) {
		oops("Unable to open I2C EEPROM! Is there a mezzanine present?");
		goto out;
	}
	if(i2c_eeprom_read(h, buf, 0, sizeof(buf)) != sizeof(buf)) {
		oops("Error reading raw data from EEPROM!");
		goto out;
	}

	/* Try to parse into FRUI structure */
	if(!(p = frui_parser_new()))
		goto out;
	if(!(self->mezz_frui[mezzanine-1] = frui_parser_loadb(p, sizeof(buf), buf))) {
		oops("Failed to parse IPMI FRU block! (Is this an uninitialized mezzanine?)");
		goto out;
	}

	/* Any warnings? Log them. */
	while((warning = frui_parser_get_warning(p)))
		syslog(LOG_WARNING, "IPMI parser: %s", warning);

out:
	pthread_mutex_unlock(&self->mezz_i2c_lock);

	if(h)
		i2c_eeprom_close(h);
	if(p)
		frui_parser_free(p);

	return self->mezz_frui[mezzanine-1];
}

tuber_method(JSON, IceBoard, _get_mezzanine_ipmi,
		"Read the I2C EEPROM, and interpret it as an IPMI descriptor.",
		1, ((INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")),
		2, (CATEGORY_ICEBOARD, CATEGORY_MEZZANINE),
		"The FMC specs state that EEPROMs should be formatted "
		"according to IPMI standards. This method attempts to "
		"retrieve and parse this data, returning it as a JSON "
		"object if it can be correctly identified."
) {
	json_t *result = json_object();
	frui *frui;

	VALIDATE_BETWEEN(mezzanine, 1, 2, NULL);

	pthread_mutex_lock(&self->mezz_frui_lock);
	if((frui = IceBoard_get_mezzanine_ipmi_raw(self, mezzanine))) {
		if(frui_has_board_info(frui))
			json_object_set_new(result, "board", json_pack(
					"{s:s,s:s,s:s,s:s,s:s}",
					"manufacturer", frui_get_board_manufacturer(frui),
					"name", frui_get_board_name(frui),
					"serial_number", frui_get_board_serial_number(frui),
					"part_number", frui_get_board_part_number(frui),
					"frui_file_id", frui_get_board_fru_file_id(frui)));

		if(frui_has_product_info(frui))
			json_object_set_new(result, "product", json_pack(
					"{s:s,s:s,s:s,s:s,s:s,s:s,s:s}",
					"manufacturer", frui_get_product_manufacturer(frui),
					"name", frui_get_product_name(frui),
					"part_number", frui_get_product_part_number(frui),
					"version_number", frui_get_product_version_number(frui),
					"serial_number", frui_get_product_serial_number(frui),
					"asset_tag", frui_get_product_asset_tag(frui),
					"frui_file_id", frui_get_product_fru_file_id(frui)));
	}
	pthread_mutex_unlock(&self->mezz_frui_lock);

	return result;
}

tuber_method(STRING, IceBoard, _get_mezzanine_type,
	"Get mezzanine type.",
	1, ((INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")),
	2, (CATEGORY_ICEBOARD, CATEGORY_MEZZANINE),
	"The mezzanine type is a new parameter for K7-based boards. "
) {
	/* This function returns a malloc()'d string that MUST be free()d! */
	frui *frui;
	const char *t=NULL;

	VALIDATE_BETWEEN(mezzanine, 1, NUM_MEZZANINES, NULL);

	/* Refresh the cached value and return that. */
	pthread_mutex_lock(&self->mezz_frui_lock);
	if((frui = IceBoard_get_mezzanine_ipmi_raw(self, mezzanine)))
		t = frui_get_product_part_number(frui);
	pthread_mutex_unlock(&self->mezz_frui_lock);

	if(!t) {
		oops("Unknown mezzanine type! Is the IPMI block valid?");
		return NULL;
	}

	return strdup(t);
}

tuber_method(STRING, IceBoard, _get_mezzanine_version,
	"Get mezzanine version.",
	1, ((INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")),
	2, (CATEGORY_ICEBOARD, CATEGORY_MEZZANINE),
	"The mezzanine type is a new parameter for K7-based boards. "
) {
	/* This function returns a malloc()'d string that MUST be free()d! */
	frui *frui;
	const char *t=NULL;

	VALIDATE_BETWEEN(mezzanine, 1, NUM_MEZZANINES, NULL);

	/* Refresh the cached value and return that. */
	pthread_mutex_lock(&self->mezz_frui_lock);
	if((frui = IceBoard_get_mezzanine_ipmi_raw(self, mezzanine)))
		t = frui_get_product_version_number(frui);
	pthread_mutex_unlock(&self->mezz_frui_lock);

	if(!t) {
		oops("Unknown mezzanine version! Is the IPMI block valid?");
		return NULL;
	}

	return strdup(t);
}

tuber_method(STRING, IceBoard, _get_mezzanine_serial,
	"Get mezzanine serial number.",
	1, ((INTEGER, mezzanine, NULL, "Mezzanine number (1/2)")),
	2, (CATEGORY_ICEBOARD, CATEGORY_MEZZANINE),
	"The mezzanine serial number is embedded in IPMI data in an on-board "
	"EEPROM (which must be programmed during quality control testing.)"
) {
	/* This function returns a malloc()'d string that MUST be free()d! */
	frui *frui;
	const char *s=NULL;

	VALIDATE_BETWEEN(mezzanine, 1, NUM_MEZZANINES, NULL);

	/* Refresh the cached value and return that. */
	pthread_mutex_lock(&self->mezz_frui_lock);
	if((frui = IceBoard_get_mezzanine_ipmi_raw(self, mezzanine)))
		s = frui_get_product_serial_number(frui);
	pthread_mutex_unlock(&self->mezz_frui_lock);

	if(!s) {
		oops("Unspecified mezzanine serial number! Is the IPMI block valid?");
		return NULL;
	}

	return strdup(s);
}
