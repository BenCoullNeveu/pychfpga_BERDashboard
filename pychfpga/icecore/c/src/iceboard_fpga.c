#include <tuber.h>
#include <string.h>
#include <openssl/md5.h>
#include <unistd.h>
#include <stdint.h>

/* For setting the SPI port speed */
#include <linux/spi/spidev.h>
#include <sys/ioctl.h>

#include "iceboard.h"
#include "base64.h"
#include "runtime.h"
#include "iceboard_hw.h"

json_t * load_bitstream(const char* bits, int len);

static const char *fpga_spidev = "/dev/spidev4.1";

tuber_method(IceBoard, BOOLEAN, is_fpga_programmed,
		"Returns the state of the FPGA's DONE signal",
		0, (), ""
) {
	struct iceboard_gpio *done_gpio = get_gpio_by_netname("DONE");

	if(!done_gpio) {
		oops("Unable to look up GPIO 'DONE'");
		return 0;
	}

	/* We can't continue if DONE isn't set */
	return gpio_get(done_gpio, 1);
}

tuber_method(IceBoard, VOID, disable_fpga,
		"Disable the FPGA",
		0, (), ""
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

tuber_method(IceBoard, JSON, load_fpga_bitstream,
		"Loads the FPGA's bitstream",
		1, ((STRING_CONST, b64, NULL, "Bitstream contents (base64 encoded)")),
		""
) {
	char *buf = NULL;
	int slen, blen;
	json_t *result=NULL;

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
	result = load_bitstream(buf, blen);

out:
	if(buf)
		free(buf);
	return(result);
}

json_t *load_bitstream(const char* bits, int len) {
	FILE *spidev = NULL;
	struct iceboard_gpio *program_b_gpio = NULL,
			     *init_b_gpio = NULL,
			     *done_gpio = NULL;
	int n;
	int speed;
	json_t *result = json_null();

	if(!(spidev = fopen(fpga_spidev, "w"))) {
		oops("Unable to load SPI device!");
		goto out;
	}

	/* Make go fast now! (16 MHz) */
	speed = 16000000;
	if(ioctl(fileno(spidev), SPI_IOC_WR_MAX_SPEED_HZ, &speed) == -1) {
		oops("Can't set speed to %f MHz", speed/1e6);
		goto out;
	}

	/* Obtain GPIO references */
	if(!(program_b_gpio = get_gpio_by_netname("PROGRAM_B")) ||
		!(init_b_gpio = get_gpio_by_netname("INIT_B")) ||
		!(done_gpio = get_gpio_by_netname("DONE"))) {
		oops("Unable to obtain PROGRAM_B, INIT_B, or DONE GPIO references!");
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
		goto out;
	}

	for(n=0; n<len; n+=fwrite(bits+n, 1, len-n>4096 ? 4096 : (len-n), spidev))
		;

	/* The FPGA needs a few extra CCLK edges to get going.
	 * This is a pretty random number: documentation says "some". */
	fwrite((const char []){0,0,0,0,0,0,0,0}, 1, 8, spidev);

	fclose(spidev);
	spidev = NULL;

	/* Ensure done is HIGH */
	for(n=10; n; n--) {
		if(gpio_get(done_gpio, 0))
			break;
		usleep(1000);
	}
	if(!n) {
		oops("FPGA failed to raise DONE!");
		goto out;
	}

out:
	if(spidev)
		fclose(spidev);

	return(result);
}

uint32_t fpga_spi_rread(IceBoard *self, uint32_t addr) {
	FILE *spidev;
	struct spi_ioc_transfer xfer[2];
	int speed;
	uint8_t mode;
	uint32_t data=0;

	if(!(spidev = fopen(fpga_spidev, "w"))) {
		oops("Unable to load SPI device!");
		goto out;
	}

	memset(xfer, 0, sizeof(xfer));
	xfer[0].tx_buf = (unsigned long)&addr;
	xfer[0].len = 4;

	xfer[1].rx_buf = (unsigned long)&data;
	xfer[1].len = 4;

	/* Make go fast now! (16 MHz) */
	speed = 16000000;
	if(ioctl(fileno(spidev), SPI_IOC_WR_MAX_SPEED_HZ, &speed) == -1) {
		oops("Can't set speed to %f MHz", speed/1e6);
		goto out;
	}

	/* Set polarity */
	mode = 0;
	if(ioctl(fileno(spidev), SPI_IOC_WR_MODE, &mode) < 0) {
		oops("Error setting SPI mode");
		goto out;
	}

	if(ioctl(fileno(spidev), SPI_IOC_MESSAGE(2), &xfer) < 0) {
		oops("Error during ioctl()");
		goto out;
	}

out:
	if(spidev)
		fclose(spidev);

	return data;
}

void fpga_spi_rwrite(IceBoard *self, uint32_t addr, uint32_t data) {
	FILE *spidev;
	struct spi_ioc_transfer xfer[2];
	int speed;
	uint8_t mode;

	if(!(spidev = fopen(fpga_spidev, "w"))) {
		oops("Unable to load SPI device!");
		goto out;
	}

	memset(xfer, 0, sizeof(xfer));
	xfer[0].tx_buf = (unsigned long)&addr;
	xfer[0].len = 4;

	xfer[1].tx_buf = (unsigned long)&data;
	xfer[1].len = 4;

	/* Make go fast now! (16 MHz) */
	speed = 16000000;
	if(ioctl(fileno(spidev), SPI_IOC_WR_MAX_SPEED_HZ, &speed) == -1) {
		oops("Can't set speed to %f MHz", speed/1e6);
		goto out;
	}

	/* Set polarity */
	mode = 0;
	if(ioctl(fileno(spidev), SPI_IOC_WR_MODE, &mode) < 0) {
		oops("Error setting SPI mode");
		goto out;
	}

	if(ioctl(fileno(spidev), SPI_IOC_MESSAGE(2), &xfer) < 0) {
		oops("Error during ioctl()");
		goto out;
	}

out:
	if(spidev)
		fclose(spidev);
}

void fpga_spi_roreq(IceBoard *self, uint32_t addr, uint32_t data) {
	fpga_spi_rwrite(self, addr,
			fpga_spi_rread(self, addr) | data);
}

void fpga_spi_randeq(IceBoard *self, uint32_t addr, uint32_t data) {
	fpga_spi_rwrite(self, addr,
			fpga_spi_rread(self, addr) & data);
}

tuber_method(IceBoard, INTEGER, fpga_spi_peek,
		"Peek.",
		1, (
			(INTEGER, addr, NULL, "single word (must be word-aligned)")
		),
		""
) {
	if(addr & 3) {
		oops("Address wasn't word-aligned!");
		return(-1);
	}

	return fpga_spi_rread(self, addr);
}

tuber_method(IceBoard, VOID, fpga_spi_poke,
		"Poke.",
		2, (
			(INTEGER, addr, NULL, "single word (must be word-aligned)"),
			(INTEGER, data, NULL, "single data word")
		),
		""
) {
	if(addr & 3) {
		oops("Address wasn't word-aligned!");
		return;
	}

	fpga_spi_rwrite(self, addr, data);
}
