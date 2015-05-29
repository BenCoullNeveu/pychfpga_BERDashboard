#include "iceboard_hw.h"
#include <string.h>

int fpga_jtag_transact(const uint32_t tms, const uint32_t tdi, uint32_t *tdo, const int num_bits) {

	struct iceboard_gpio *fpga_tms = get_gpio_by_netname("FPGA_TMS");
	struct iceboard_gpio *fpga_tck = get_gpio_by_netname("FPGA_TCK");
	struct iceboard_gpio *fpga_tdo = get_gpio_by_netname("FPGA_TDO");
	struct iceboard_gpio *fpga_tdi = get_gpio_by_netname("FPGA_TDI");

	int n;

	if(!fpga_tms || !fpga_tck || !fpga_tdo || !fpga_tdi)
		return -1;

	/* Enforce input on TDO */
	gpio_get(fpga_tdo, 1); /* input */

	/* Zero output array */
	if(tdo)
		*tdo=0;

	for(n=0; n<num_bits; n++) {
		gpio_set(fpga_tck, 0);
		gpio_set(fpga_tms, (tms >> n) & 1);
		gpio_set(fpga_tdi, (tdi >> n) & 1);
		gpio_set(fpga_tck, 1);

		if(tdo)
			*tdo |= gpio_get(fpga_tdo, 0)<<n;
	}

	return 0;
}

#if 0
/* MUST be called with mutex held */
int xadc_init(void) {

	static const struct {
		uint8_t addr;
		uint16_t data;
	} inits[] = {
		{ 0x40, 0xb000 }, /* temperature sensor, lots of averaging */
		{ 0x41, 0x2ef0 }, /* continuous seq, enable calibration */
		{ 0x42, 0x0800 }, /* Set DCLK divides */
		{ 0x48, 0x4701 }, /* enable temperature, vccint, vccaux, vccbram, calibration */
		{ 0x49, 0x0000 }, /* disabled */
		{ 0x4a, 0x0000 }, /* SEQAVG1 disabled */
		{ 0x4b, 0x0000 }, /* SEQAVG2 disabled */
		{ 0x4c, 0x0000 }, /* SEQINMODE0 */
		{ 0x4d, 0x0000 }, /* SEQINMODE1 */
		{ 0x4e, 0x0000 }, /* SEQACQ0 */
		{ 0x4f, 0x0000 }, /* SEQACQ1 */
		{ 0x50, 0xb5ed }, /* Temp upper alarm trigger 85'C */
		{ 0x51, 0x5999 }, /* Vccint upper alarm limit 1.05V */
		{ 0x52, 0xa147 }, /* Vccaux upper alarm limit 1.89V */
		{ 0x53, 0xdddd }, /* OT upper alarm limit 125'C */
		{ 0x54, 0xa93a }, /* Temp lower alarm reset 60'C */
		{ 0x55, 0x5111 }, /* Vccint lower alarm limit 0.95V */
		{ 0x56, 0x91eb }, /* Vccaux lower alarm limit 1.71V */
		{ 0x57, 0xae4e }, /* OT lower alarm reset 70'C */
		{ 0x58, 0x5999 }, /* VCCBRAM upper alarm limit 1.05V */
	};
	int n;

	/* xxx -> RTI, RTI -> SIR, shift in XADC_DRP, EIR -> SDR */
	fpga_jtag_transact(0x380df, 0x0dc00, NULL, 20);

	for(n=0; n<sizeof(inits)/sizeof(*inits); n++) {
		fpga_jtag_transact(0x80000000, (0x2<<26) | (inits[n].addr << 16) | inits[n].data, NULL, 32);

		if(n < sizeof(inits)/sizeof(*inits)-1)
			fpga_jtag_transact(0x11, 0, NULL, 7); /* EDR -> RTI, tick twice, RTI -> SDR */
		else
			fpga_jtag_transact(0x71, 0, NULL, 7); /* EDR -> RTI, tick twice, RTI -> TLR */
	}

	return 0;
}
#endif

/* MUST be called with mutex held and XADC initialized */
double xadc_read_temperature(void) {
	uint32_t temp;

	/* xxx -> RTI, RTI -> SIR, shift in XADC_DRP, EIR -> SDR */
	fpga_jtag_transact(0x380df, 0x0dc00, NULL, 20);

	fpga_jtag_transact(0x80000000, 0x1<<26, NULL, 32); /* initiate temperature read */
	fpga_jtag_transact(0x11, 0, NULL, 7); /* EDR -> RTI, tick twice, RTI -> SDR */
	fpga_jtag_transact(0x80000000, 0x1<<26, &temp, 32); /* retrieve results */
	fpga_jtag_transact(0xf, 0, NULL, 4); /* EDR -> TLR */

	return (double)temp * 503.975 / 65536 - 273.15;
}
