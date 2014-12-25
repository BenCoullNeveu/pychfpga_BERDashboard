#ifndef __ICEBOARD_H__
#define __ICEBOARD_H__

#include "runtime.h"
#include "support.h"
#include "iceboard_constants.h"
#include "ipmi_frui.h"

#include <stdint.h>
#include <pthread.h>
#include <jansson.h>

typedef struct IceBoard IceBoard;

#define FPGA_SPIDEV "/dev/spidev4.1"
#define FPGA_SPIDEV_CLK 16e6

/*
 * Types
 */

typedef int bool;

struct IceBoard {
	uint32_t (*rread)(IceBoard *, void*);
	void (*rwrite)(IceBoard *, void*, uint32_t);
	void (*randeq)(IceBoard *, void*, uint32_t);
	void (*roreq)(IceBoard *, void*, uint32_t);

	/* We keep IPMI data around *only* while the mezzanine is turned on.
	 * When it's off, it's conceivable that the board will be hotplugged. */
	frui *mezz_frui[NUM_MEZZANINES];

	/* Only permit freeing of FRUI structures when this equals 0. Prevents
	 * use-after-free of string elements when the cache is replaced
	 * (typically when the mezzanine is powered OFF, or being powered up. */
	int mezz_frui_refcount;
	pthread_mutex_t mezz_frui_lock;

	char *personality;

	pthread_mutex_t fpga_spidev_lock;
	pthread_mutex_t mezz_i2c_lock;
	FILE *fpga_spidev;

	pthread_mutex_t fpga_jtag_lock;
};

/*
 * IceBoard-wide methods
 */

IceBoard *new_IceBoard(void);
void delete_IceBoard(IceBoard *);

void IceBoard_set_mezzanine_power(IceBoard *self, bool power, int mezzanine);
bool IceBoard_get_mezzanine_power(IceBoard *self, int mezzanine);
bool IceBoard_is_mezzanine_present(IceBoard *self, int mezzanine);

char *IceBoard_get_motherboard_serial(IceBoard *self);
char *IceBoard__get_mezzanine_type(IceBoard *self, int mezzanine);
char *IceBoard__get_mezzanine_version(IceBoard *self, int mezzanine);
char *IceBoard__get_mezzanine_serial(IceBoard *self, int mezzanine);

double IceBoard_get_motherboard_temperature(IceBoard *, const char *);
double IceBoard_get_motherboard_voltage(IceBoard *, const char *);
double IceBoard_get_motherboard_current(IceBoard *, const char *);

/*double IceBoard_get_mezzanine_temperature(IceBoard *, const char *, int);*/
double IceBoard_get_mezzanine_voltage(IceBoard *, const char *, int);
double IceBoard_get_mezzanine_current(IceBoard *, const char *, int);

void IceBoard__set_fpga_bitstream_base64(IceBoard *, const char *);
bool IceBoard_is_fpga_programmed(IceBoard *);
void IceBoard_clear_fpga_bitstream(IceBoard *);
int IceBoard_load_bitstream(IceBoard *ib, const char* bits, int len);

char *IceBoard__get_arm_ip(IceBoard *, const char *);
char *IceBoard__get_arm_mac(IceBoard *, const char *);

const char *IceBoard__get_personality(IceBoard *);
void IceBoard__set_personality(IceBoard *, const char *);

/*
 * IPMI methods
 */

frui *IceBoard_get_mezzanine_ipmi_raw(IceBoard *self, const int mezzanine);
json_t *IceBoard__get_mezzanine_ipmi(IceBoard *self, const int mezzanine);

frui *IceBoard_get_motherboard_ipmi_raw(void);
FILE *get_motherboard_ipmi_file(const char *fopen_mode);
int IceBoard__mezzanine_lock_ipmi_cache(IceBoard *self);
int IceBoard__mezzanine_unlock_ipmi_cache(IceBoard *self);

/*
 * Register access.
 */

uint32_t fpga_spi_rread(IceBoard *, void*);
void fpga_spi_rwrite(IceBoard *, void*, uint32_t);
void fpga_spi_randeq(IceBoard *, void*, uint32_t);
void fpga_spi_roreq(IceBoard *, void*, uint32_t);

#endif
