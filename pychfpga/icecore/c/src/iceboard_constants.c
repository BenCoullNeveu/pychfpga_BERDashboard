#include "iceboard_constants.h"
#include "tuber.h"
#include "runtime.h"

/* Units */
const char *HZ="Hz";
const char *RAW="RAW";
const char *VOLTS="Volts";
const char *AMPS="Amps";
const char *WATTS="Watts";
const char *DAC_COUNTS="DAC Counts";
const char *ADC_COUNTS="ADC Counts";
const char *NORMALIZED="Normalized";
const char *DEGREES="Degrees";
const char *RADIANS="Radians";
const char *OHMS="Ohms";

tuber_property(IceBoard, UNITS, json_pack(
		"{"
		" s:s, s:s, s:s, s:s, s:s,"
		" s:s, s:s, s:s, s:s, s:s,"
		" s:s "
		"}",
		"HZ", HZ,
		"RAW", RAW,
		"VOLTS", VOLTS,
		"AMPS", AMPS,
		"WATTS", WATTS,
		"DAC_COUNTS", DAC_COUNTS,
		"ADC_COUNTS", ADC_COUNTS,
		"NORMALIZED", NORMALIZED,
		"DEGREES", DEGREES,
		"RADIANS", RADIANS,
		"OHMS", OHMS
));

/* Temperature sensors */
const char *MOTHERBOARD_TEMPERATURE_POWER = "MOTHERBOARD_TEMPERATURE_POWER";
const char *MOTHERBOARD_TEMPERATURE_ARM = "MOTHERBOARD_TEMPERATURE_ARM";
const char *MOTHERBOARD_TEMPERATURE_FPGA = "MOTHERBOARD_TEMPERATURE_FPGA";
const char *MOTHERBOARD_TEMPERATURE_PHY = "MOTHERBOARD_TEMPERATURE_PHY";

tuber_property(IceBoard, TEMPERATURE_SENSOR, json_pack(
		"{"
		" s:s, s:s, s:s, s:s"
		"}",
		"MB_POWER", MOTHERBOARD_TEMPERATURE_POWER,
		"MB_ARM", MOTHERBOARD_TEMPERATURE_ARM,
		"MB_FPGA", MOTHERBOARD_TEMPERATURE_FPGA,
		"MB_PHY", MOTHERBOARD_TEMPERATURE_PHY
));

/* Motherboard power rails */
const char *MOTHERBOARD_RAIL_VCC3V3 = "MOTHERBOARD_RAIL_VCC3V3";
const char *MOTHERBOARD_RAIL_VCC12V0 = "MOTHERBOARD_RAIL_VCC12V0";
const char *MOTHERBOARD_RAIL_VCC5V5 = "MOTHERBOARD_RAIL_VCC5V5";
const char *MOTHERBOARD_RAIL_VCC1V0_GTX = "MOTHERBOARD_RAIL_VCC1V0_GTX";
const char *MOTHERBOARD_RAIL_VCC1V0 = "MOTHERBOARD_RAIL_VCC1V0";
const char *MOTHERBOARD_RAIL_VCC1V2 = "MOTHERBOARD_RAIL_VCC1V2";
const char *MOTHERBOARD_RAIL_VCC1V5 = "MOTHERBOARD_RAIL_VCC1V5";
const char *MOTHERBOARD_RAIL_VCC1V8 = "MOTHERBOARD_RAIL_VCC1V8";
const char *MOTHERBOARD_RAIL_VADJ = "MOTHERBOARD_RAIL_VADJ";

/* Mezzanine power rails */
const char *MEZZANINE_RAIL_VCC3V3 = "MEZZANINE_RAIL_VCC3V3";
const char *MEZZANINE_RAIL_VCC12V0 = "MEZZANINE_RAIL_VCC12V0";
const char *MEZZANINE_RAIL_VADJ = "MEZZANINE_RAIL_VADJ";

tuber_property(IceBoard, VOLTAGE_SENSOR, json_pack(
		"{"
		" s:s, s:s, s:s, s:s, s:s"
		" s:s, s:s, s:s, s:s, s:s"
		" s:s, s:s"
		"}",
		"MB_VCC3V3", MOTHERBOARD_RAIL_VCC3V3,
		"MB_VCC12V0", MOTHERBOARD_RAIL_VCC12V0,
		"MB_VCC5V5", MOTHERBOARD_RAIL_VCC5V5,
		"MB_VCC1V0_GTX", MOTHERBOARD_RAIL_VCC1V0_GTX,
		"MB_VCC1V0", MOTHERBOARD_RAIL_VCC1V0,
		"MB_VCC1V2", MOTHERBOARD_RAIL_VCC1V2,
		"MB_VCC1V5", MOTHERBOARD_RAIL_VCC1V5,
		"MB_VCC1V8", MOTHERBOARD_RAIL_VCC1V8,
		"MB_VADJ", MOTHERBOARD_RAIL_VADJ,
		"MEZZ_VCC3V3", MEZZANINE_RAIL_VCC3V3,
		"MEZZ_VCC12V0", MEZZANINE_RAIL_VCC12V0,
		"MEZZ_VADJ", MEZZANINE_RAIL_VADJ
));

/* Mezzanine types */
const char *MEZZ_TYPE_UNSPECIFIED = "unspecified mezzanine type!";

tuber_property(IceBoard, MEZZ_TYPE, json_pack(
		"{ s:s }",
		"UNSPECIFIED", MEZZ_TYPE_UNSPECIFIED
));
