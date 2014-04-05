#ifndef __ICEBOARD_HW__
#define __ICEBOARD_HW__

int export_gpio_by_netname(const char*);
struct iceboard_gpio *get_gpio_by_netname(const char*);

/* These are the names and GPIO numbers of all GPIOs on the iceboard. They
 * need to match with arch/arm/mach-omap2/board-ti8148evm.c in the Linux
 * sources. Additionally, for sanity's sake, *both* of these sources need to
 * match with the schematics we're using as a reference. That way there's only
 * one net naming scheme to keep in mind.
 *
 * Mess this up at your peril! And, if things will appear messed-up to a
 * sleepy/uncaffeinated reader, please document them.
 */

void gpio_set(struct iceboard_gpio *self, int value);
int gpio_get(struct iceboard_gpio *self, int set_input);

static struct iceboard_gpio {
	int gpio_num;
	enum { INPUT, OUTPUT } mode;
	enum { LOW, HIGH } dfl;
	const char *name;
	int dir_fd, value_fd;
} iceboard_gpio[] = {
	{ .gpio_num = 1, .name="PROGRAM_B", .mode=INPUT, .dfl=HIGH }, /* GP01 */
	{ .gpio_num = 2, .name="INIT_B", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 3, .name="DONE", .mode=INPUT, .dfl=HIGH },

	{ .gpio_num = 8, .name="FMCA_TMS", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 9, .name="FMCA_TCK", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 10, .name="FMCA_TDO", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 11, .name="FMCA_TDI", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 15, .name="FMCA_TRST", .mode=INPUT, .dfl=HIGH },

	{ .gpio_num = 16, .name="FMCB_TMS", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 17, .name="FMCB_TCK", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 18, .name="FMCB_TDO", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 19, .name="FMCB_TDI", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 20, .name="FMCB_TRST", .mode=INPUT, .dfl=HIGH },

	{ .gpio_num = 24, .name="FPGA_TMS", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 25, .name="FPGA_TCK", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 26, .name="FPGA_TDO", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 27, .name="FPGA_TDI", .mode=INPUT, .dfl=HIGH },

	{ .gpio_num = 32, .name="PHYA_IRQ_N", .mode=INPUT, .dfl=HIGH },	/* GP10 */
	{ .gpio_num = 33, .name="PHYA_RESET_N", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 39, .name="PHYB_IRQ_N", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 40, .name="PHYB_RESET_N", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 41, .name="ARM_IRQ", .mode=INPUT, .dfl=HIGH }, /* errata: wrong in rev0 boards */
	{ .gpio_num = 42, .name="GPIO_IRQ", .mode=INPUT, .dfl=HIGH },

	{ .gpio_num = 66, .name="ARMClkSel0", .mode=INPUT, .dfl=HIGH }, /* GP22 */
	{ .gpio_num = 67, .name="ARMClkSel1", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 68, .name="EnFPGARef", .mode=INPUT, .dfl=HIGH },

	{ .gpio_num = 96, .name="BP_ARM_GPIO0", .mode=INPUT, .dfl=HIGH }, /* GP30 */
	{ .gpio_num = 97, .name="BP_ARM_GPIO1", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 98, .name="BP_ARM_GPIO2", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 99, .name="BP_ARM_GPIO3", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 100, .name="BP_ARM_GPIO4", .mode=INPUT, .dfl=HIGH },
	{ .gpio_num = 101, .name="BP_ARM_GPIO5", .mode=INPUT, .dfl=HIGH },

	{ .gpio_num = 192, .name="FMCA_EN_12V0", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 193, .name="FMCA_EN_3V3", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 194, .name="FMCA_EN_VADJ", .mode=OUTPUT, .dfl=LOW },

	{ .gpio_num = 195, .name="FMCA_PG_M2C", .mode=INPUT, },
	{ .gpio_num = 196, .name="FMCA_PG_C2M", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 197, .name="FMCA_PRSNT_M2C_L", .mode=INPUT, },
	{ .gpio_num = 198, .name="FMCA_CLK_DIR", .mode=INPUT, },
	{ .gpio_num = 199, .name="SFP_LOS", .mode=INPUT, },
	{ .gpio_num = 200, .name="FMCB_EN_12V0", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 201, .name="FMCB_EN_3V3", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 202, .name="FMCB_EN_VADJ", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 203, .name="FMCB_PG_M2C", .mode=INPUT, },
	{ .gpio_num = 204, .name="FMCB_PG_C2M", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 205, .name="FMCB_PRSNT_M2C_L", .mode=INPUT, },
	{ .gpio_num = 206, .name="FMCB_CLK_DIR", .mode=INPUT, },
	{ .gpio_num = 207, .name="SFP_ModPrsL", .mode=INPUT, },
	{ .gpio_num = 208, .name="QSFPA_ModPrsL", .mode=INPUT, },
	{ .gpio_num = 209, .name="QSFPA_IntL", .mode=INPUT, },
	{ .gpio_num = 210, .name="QSFPA_ResetL", .mode=OUTPUT, .dfl=HIGH },
	{ .gpio_num = 211, .name="QSFPA_ModSelL", .mode=OUTPUT, .dfl=HIGH },
	{ .gpio_num = 212, .name="QSFPA_LPMode", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 213, .name="QSFPB_ModPrsL", .mode=INPUT, },
	{ .gpio_num = 214, .name="QSFPB_IntL", .mode=INPUT, },
	{ .gpio_num = 215, .name="QSFPB_ResetL", .mode=OUTPUT, .dfl=HIGH },
	{ .gpio_num = 216, .name="SFP_TxFault", .mode=INPUT, },
	{ .gpio_num = 217, .name="SFP_TxDisable", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 218, .name="SFP_RS0", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 219, .name="SFP_RS1", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 220, .name="QSFPB_ModSelL", .mode=OUTPUT, .dfl=HIGH },
	{ .gpio_num = 221, .name="QSFPB_LPMode", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 222, .name="SEL_SFP", .mode=OUTPUT, .dfl=HIGH },
	/*{ .gpio_num = 223, .name="ARM_MR", .mode=OUTPUT, .dfl=HIGH|CLOBBER },*/
	{ .gpio_num = 224, .name="GP_SW1", .mode=INPUT, },
	{ .gpio_num = 225, .name="GP_SW2", .mode=INPUT, },
	{ .gpio_num = 226, .name="GP_SW3", .mode=INPUT, },
	{ .gpio_num = 227, .name="GP_SW4", .mode=INPUT, },
	{ .gpio_num = 228, .name="GP_SW5", .mode=INPUT, },
	{ .gpio_num = 229, .name="GP_SW6", .mode=INPUT, },
	{ .gpio_num = 230, .name="GP_SW7", .mode=INPUT, },
	{ .gpio_num = 231, .name="GP_SW8", .mode=INPUT, },
	{ .gpio_num = 232, .name="GP_LED1", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 233, .name="GP_LED2", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 234, .name="GP_LED3", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 235, .name="GP_LED4", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 236, .name="GP_LED5", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 237, .name="GP_LED6", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 238, .name="GP_LED7", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 239, .name="GP_LED8", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 240, .name="GTX_MUX_FMCB_01", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 241, .name="GTX_MUX_FMCB_23", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 242, .name="GTX_MUX_FMCB_45", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 243, .name="GTX_MUX_FMCB_67", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 244, .name="GTX_MUX_FMCA_01", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 245, .name="GTX_MUX_FMCA_23", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 246, .name="GTX_MUX_FMCA_45", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 247, .name="GTX_MUX_FMCA_67", .mode=OUTPUT, .dfl=LOW },
	{ .gpio_num = 248, .name="BP_SLOW_GPIO0", .mode=INPUT, },
	{ .gpio_num = 249, .name="BP_SLOW_GPIO1", .mode=INPUT, },
	{ .gpio_num = 250, .name="BP_SLOW_GPIO2", .mode=INPUT, },
	{ .gpio_num = 251, .name="BP_SLOW_GPIO3", .mode=INPUT, },
	{ .gpio_num = 252, .name="BP_SLOW_GPIO4", .mode=INPUT, },
	{ .gpio_num = 253, .name="BP_SLOW_GPIO5", .mode=INPUT, },
};
static const int ICEBOARD_GPIO_COUNT = sizeof(iceboard_gpio)/sizeof(*iceboard_gpio);

#endif
