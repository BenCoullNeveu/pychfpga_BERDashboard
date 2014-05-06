#ifndef __ICEBOARD_H__
#define __ICEBOARD_H__

#include "runtime.h"
#include "support.h"
#include "iceboard_constants.h"

#include <stdint.h>

typedef struct IceBoard IceBoard;

/*
 * Types
 */

typedef int bool;

struct IceBoard {
	uint32_t (*rread)(IceBoard *, uint32_t);
	void (*rwrite)(IceBoard *, uint32_t, uint32_t);
	void (*randeq)(IceBoard *, uint32_t, uint32_t);
	void (*roreq)(IceBoard *, uint32_t, uint32_t);
};

/*
 * IceBoard-wide methods
 */

IceBoard *new_IceBoard(void);
void delete_IceBoard(IceBoard *);

void IceBoard_set_mezz_power(IceBoard *self, int mezzanine, bool power);
bool IceBoard_get_mezz_power(IceBoard *self, int mezzanine);

double IceBoard_get_motherboard_temperature(IceBoard *, const char *);
double IceBoard_get_motherboard_voltage(IceBoard *, const char *);

double IceBoard_get_mezz_temperature(IceBoard *, int, const char *);
double IceBoard_get_mezz_voltage(IceBoard *, int, const char *);

bool IceBoard_is_fpga_programmed(IceBoard *);
void IceBoard_disable_fpga(IceBoard *);

/*
 * Register access.
 */

uint32_t fpga_spi_rread(IceBoard *, uint32_t);
void fpga_spi_rwrite(IceBoard *, uint32_t, uint32_t);
void fpga_spi_randeq(IceBoard *, uint32_t, uint32_t);
void fpga_spi_roreq(IceBoard *, uint32_t, uint32_t);

#endif
