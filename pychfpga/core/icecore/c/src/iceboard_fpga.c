#include <tuber.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>

#include <linux/spi/spidev.h>
#include <sys/ioctl.h>

#include "iceboard.h"
#include "base64.h"
#include "runtime.h"
#include "iceboard_hw.h"

tuber_method(BOOLEAN, IceBoard, is_fpga_programmed,
		"Returns the state of the FPGA's DONE signal",
		0, (),
		1, (CATEGORY_ICEBOARD),
		""
) {
	struct iceboard_gpio *done_gpio = get_gpio_by_netname("DONE");

	if(!done_gpio) {
		oops("Unable to look up GPIO 'DONE'");
		return 0;
	}

	/* We can't continue if DONE isn't set */
	return gpio_get(done_gpio, 1);
}

tuber_method(VOID, IceBoard, clear_fpga_bitstream,
		"Disable the FPGA",
		0, (),
		1, (CATEGORY_ICEBOARD),
		""
) {
	struct iceboard_gpio *program_b_gpio = get_gpio_by_netname("PROGRAM_B");

	if(!program_b_gpio) {
		oops("Unable to look up GPIO 'PROGRAM_B'");
		return;
	}

	/* Strobe PROGRAM_B low and release */
	gpio_set(program_b_gpio, 0);
	usleep(10000);
	(void)gpio_get(program_b_gpio, 1);
}

tuber_method(VOID, IceBoard, _set_fpga_bitstream_base64,
		"Loads the FPGA's bitstream",
		1, ((STRING_CONST, b64, NULL, "Bitstream contents (base64 encoded)")),
		1, (CATEGORY_ICEBOARD),
		"The bitstream hash is now ignored -- it was a silly idea, "
		"since the bitstream is checksummed both at the TCP level, "
		"and by the FPGA itself."
) {
	char *buf = NULL;
	int slen, blen;

	if((slen = base64_validate_string(b64)) == -1) {
		oops("Invalid base-64 bitstream supplied!");
		goto out;
	}

	blen = base64_size_blob(slen);
	buf = malloc(blen+1);
	if(!buf) {
		oops("Unable to allocate %i bytes for bitstream!", blen);
		goto out;
	}

	if(base64_decode_string(slen, b64, blen, buf) == -1) {
		oops("Error while decoding base-64 bitstream!");
		goto out;
	}

	/* Load bitstream */
	IceBoard_load_bitstream(self, buf, blen);

out:
	if(buf)
		free(buf);
}

int IceBoard_load_bitstream(IceBoard *ib, const char* bits, int len) {
	struct iceboard_gpio *program_b_gpio = NULL,
			     *init_b_gpio = NULL,
			     *done_gpio = NULL;
	int n;
	int ret = -1;

	pthread_mutex_lock(&ib->fpga_spidev_lock);

	/* Obtain GPIO references */
	if(!(program_b_gpio = get_gpio_by_netname("PROGRAM_B")) ||
		!(init_b_gpio = get_gpio_by_netname("INIT_B")) ||
		!(done_gpio = get_gpio_by_netname("DONE"))) {
		oops("Unable to obtain PROGRAM_B, INIT_B, or DONE GPIO references!");
		ret = -3;
		goto out;
	}

	/* Make sure we aren't asserting PROGRAM_B, INIT_B, or DONE */
	(void)gpio_get(program_b_gpio, 1);
	(void)gpio_get(init_b_gpio, 1);
	(void)gpio_get(done_gpio, 1);

	/* Ensure INIT_B is high */
	for(n=100; n; n--) {
		if(gpio_get(init_b_gpio, 0))
			break;
	}
	if(!n) {
		oops("INIT_B is not high!");
		ret = -4;
		goto out;
	}

	/* Drop PROGRAM_B */
	gpio_set(program_b_gpio, 0);

	/* Wait until INIT_B and DONE are LOW too */
	for(n=100; n; n--)
		if(gpio_get(init_b_gpio, 0) == 0 && gpio_get(done_gpio, 0) == 0)
			break;
	if(!n) {
		oops("FPGA failed to drop INIT_B and DONE!");
		ret = -5;
		goto out;
	}

	/* Read back both PROGRAM_B and INIT_B; wait for them to rise */
	(void)gpio_get(program_b_gpio, 1);
	for(n=10; n; n--) {
		if(gpio_get(init_b_gpio, 0) && gpio_get(program_b_gpio, 0))
			break;
		usleep(1000);
	}
	if(!n) {
		oops("FPGA failed to raise INIT_B and PROGRAM_B!");
		ret = -6;
		goto out;
	}

	for(n=0; n<len; n+=fwrite(bits+n, 1, len-n>4096 ? 4096 : (len-n), ib->fpga_spidev))
		;

	/* The FPGA needs a few extra CCLK edges to get going.
	 * This is a pretty random number: documentation says "some". */
	fwrite((const char []){0,0,0,0,0,0,0,0}, 1, 8, ib->fpga_spidev);

	/* Flush! Otherwise we aren't guaranteed the writes will complete. */
	fflush(ib->fpga_spidev);

	/* Ensure done is HIGH */
	for(n=100; n; n--) {
		if(gpio_get(done_gpio, 0))
			break;
		usleep(1000);
	}
	if(!n) {
		oops("FPGA failed to raise DONE!");
		ret = -7;
		goto out;
	}

	/* Success! */
	ret = 0;

out:
	pthread_mutex_unlock(&ib->fpga_spidev_lock);
	return ret;
}

uint32_t fpga_spi_rread(IceBoard *self, void *addr) {
	struct spi_ioc_transfer xfer[2];
	uint32_t data=0;
	struct iceboard_gpio *done_gpio = get_gpio_by_netname("DONE");

	memset(xfer, 0, sizeof(xfer));
	xfer[0].tx_buf = (unsigned long)&addr;
	xfer[0].len = 4;

	xfer[1].rx_buf = (unsigned long)&data;
	xfer[1].len = 4;

	if(!done_gpio || !gpio_get(done_gpio, 0)) {
		oops("FPGA is not programmed! Can't read registers.");
		return 0;
	}

	pthread_mutex_lock(&self->fpga_spidev_lock);
	if(ioctl(fileno(self->fpga_spidev), SPI_IOC_MESSAGE(2), &xfer) < 0)
		oops("Error during ioctl()");
	pthread_mutex_unlock(&self->fpga_spidev_lock);
	return data;
}

void fpga_spi_rwrite(IceBoard *self, void *addr, uint32_t data) {
	struct spi_ioc_transfer xfer[2];
	uint32_t addr_ent = (uint32_t)addr | 1;
	struct iceboard_gpio *done_gpio = get_gpio_by_netname("DONE");

	memset(xfer, 0, sizeof(xfer));
	xfer[0].tx_buf = (unsigned long)&addr_ent;
	xfer[0].len = 4;

	xfer[1].tx_buf = (unsigned long)&data;
	xfer[1].len = 4;

	if(!done_gpio || !gpio_get(done_gpio, 0)) {
		oops("FPGA is not programmed! Can't write registers.");
		return;
	}

	pthread_mutex_lock(&self->fpga_spidev_lock);
	if(ioctl(fileno(self->fpga_spidev), SPI_IOC_MESSAGE(2), &xfer) < 0)
		oops("Error during ioctl()");
	pthread_mutex_unlock(&self->fpga_spidev_lock);
}

void fpga_spi_roreq(IceBoard *self, void *addr, uint32_t data) {
	fpga_spi_rwrite(self, addr,
			fpga_spi_rread(self, addr) | data);
}

void fpga_spi_randeq(IceBoard *self, void *addr, uint32_t data) {
	fpga_spi_rwrite(self, addr,
			fpga_spi_rread(self, addr) & data);
}

tuber_method(INTEGER, IceBoard, _fpga_spi_peek,
		"Peek.",
		1, (
			(INTEGER, addr, NULL, "single word (must be word-aligned)")
		),
		1, (CATEGORY_ICEBOARD),
		""
) {
	if(addr & 3) {
		oops("Address wasn't word-aligned!");
		return(-1);
	}

	return fpga_spi_rread(self, (void*)addr);
}

tuber_method(VOID, IceBoard, _fpga_spi_poke,
		"Poke.",
		2, (
			(INTEGER, addr, NULL, "single word (must be word-aligned)"),
			(INTEGER, data, NULL, "single data word")
		),
		1, (CATEGORY_ICEBOARD),
		""
) {
	if(addr & 3) {
		oops("Address wasn't word-aligned!");
		return;
	}

	fpga_spi_rwrite(self, (void*)addr, data);
}
