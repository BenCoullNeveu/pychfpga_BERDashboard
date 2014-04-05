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

tuber_method(iceboard, JSON, load_fpga_bitstream,
		"Loads the FPGA's bitstream",
		2, (
			(STRING_CONST, b64, NULL, "Bitstream contents (base64 encoded)"),
			(STRING_CONST, md5sum, NULL, "MD5 checksum")
		),
		""
) {
	char *buf = NULL;
	int slen, blen;
	json_t *result=NULL;
	MD5_CTX c;
	char h[3];
	int n;
	unsigned char our_md5sum[MD5_DIGEST_LENGTH];

	/* base-64 decoding */

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

	/* md5sum check */

	if(strlen(md5sum) != MD5_DIGEST_LENGTH * 2) {
		oops("Reference md5sum had an unexpected length (%i)!",
				strlen(md5sum));
		goto out;
	}

	MD5_Init(&c);
	MD5_Update(&c, buf, blen);
	MD5_Final(our_md5sum, &c);

	for(n=0; n<MD5_DIGEST_LENGTH; n++) {
		sprintf(h, "%02x", our_md5sum[n]);
		if(strncmp(h, md5sum+2*n, 2)) {
			oops("Bitstream md5sum didn't match reference md5sum!");
			goto out;
		}
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
