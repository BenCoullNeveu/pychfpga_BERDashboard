#include <stdlib.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
#include <syslog.h>
#include <pthread.h>
#include <string.h>
#include <errno.h>

#include <boost/preprocessor.hpp>

#include <linux/i2c.h>
#include <linux/i2c-dev.h>

#include <endian.h>
#include <stdint.h>

#include "i2c_eeprom.h"

#define I2C_ADDR 0x50

#define syslog(prio, fmt, ...) \
	syslog(prio, "(" __FILE__ ":" BOOST_PP_STRINGIZE(__LINE__) ") " fmt, ##__VA_ARGS__)

struct i2c_eeprom_handle {
	int fd;
	int addr_len; /* address bytes; 1 or 2 */
};

/* MUST be called with bus locking in place! */
int i2c_eeprom_read(i2c_eeprom_handle *h, void *ptr, unsigned int offset, size_t count) {
	int i2c_addr = I2C_ADDR;
	uint16_t addr2;
	uint8_t addr1;

	/* Figure out if we're talking to the second I2C address on a
	 * multi-address chip. */
	if(h->addr_len == 2 && offset >= 65536) {
		i2c_addr = I2C_ADDR | 1;
		offset -= 65536;
	}
	ioctl(h->fd, I2C_SLAVE, i2c_addr);

	/* If the read request spans chips, truncate it to the first one only */
	if(offset + count >= 65536)
		count = 65536 - offset;

	addr1 = offset;
	addr2 = htobe16(offset);

	if(h->addr_len == 2)
		write(h->fd, &addr2, sizeof(addr2));
	else
		write(h->fd, &addr1, sizeof(addr1));

	return read(h->fd, ptr, count);
}

/* MUST be called with bus locking in place! */
int i2c_eeprom_write(i2c_eeprom_handle *h, void *ptr, unsigned int offset, size_t count) {
	int i2c_addr = I2C_ADDR;
	int n;
	int x;

	uint8_t buf[3]; /* up to 2 addresses, one data */

	/* Figure out if we're talking to the second I2C address on a
	 * multi-address chip. */
	if(h->addr_len == 2 && offset >= 65536) {
		i2c_addr = I2C_ADDR | 1;
		offset -= 65536;
	}
	ioctl(h->fd, I2C_SLAVE, i2c_addr);

	/* If the read request spans chips, truncate it to the first one only */
	if(offset + count >= 65536)
		count = 65536 - offset;

	if(h->addr_len == 1)
		buf[0] = offset;
	else
		*(uint16_t *)buf = htobe16(offset);

	/* This is a brain-dead write loop that issues 1-byte writes.
	 * If we want a faster write, it'll have to have some knowledge
	 * of page sizes. Note that we're already using chips with page
	 * sizes as small as 8 bytes. */

	for(n=0; n<count; n++) {
		buf[h->addr_len] = ((char*)ptr)[n];

		while(1) {
			x = write(h->fd, buf, h->addr_len+1);

			/* Write in progress */
			if(x == -1 && errno==EREMOTEIO)
				continue;

			if(x == h->addr_len + 1)
				break;

			syslog(LOG_ERR, "Write error (%i, %s)\n", x, strerror(errno));
			return(-1);
		}
	}

	return n;
}

/* MUST be called with bus locking in place! */
i2c_eeprom_handle *i2c_eeprom_open(const char *path) {
	i2c_eeprom_handle *h = NULL;
	char x;
	int rv;

	openlog("fastpath", LOG_CONS, LOG_USER);
	setlogmask(LOG_UPTO(LOG_DEBUG));

	if(!(h = calloc(1, sizeof(*h))))
		goto oops;

	if((h->fd = open(path, O_RDWR)) < 0) {
		syslog(LOG_ERR, "Failed to open I2C device '%s'", path);
		goto oops;
	}

	/*
	 * Probe device size. This is a little tricky: I2C EEPROMs have
	 * 8- or 16-bit addresses, and the two are *not* compatible.
	 * In particular, "set 16-bit address to 0" is identical to
	 * "set 8-bit address to 0, and write 0x00 there."
	 *
	 * To work around this, we take advantage of the fact that our
	 * FMC cards use 8-bit addressing UNLESS the EEPROMs are big
	 * enough to occupy adjacent I2C addresses. We probe the higher
	 * address first, and if it responds, we infer 16-bit treatment.
	 *
	 * There are a couple of big assumptions here, but hopefully
	 * we can live with them.
	 */

	/* Probe the higher address (I2C_ADDR|1) */
	if(ioctl(h->fd, I2C_SLAVE, I2C_ADDR|1) == -1) {
		syslog(LOG_ERR, "Failed to set I2C slave address ('%s')", path);
		goto oops;
	}

	if((rv = read(h->fd, &x, 1)) == 1) {
		h->addr_len = 2;
		syslog(LOG_INFO, "Inferred I2C EEPROM with 16-bit addressing on '%s'", path);
		return h;
	}

	/* If that didn't work, probe the lower address */
	if(ioctl(h->fd, I2C_SLAVE, I2C_ADDR) == -1) {
		syslog(LOG_ERR, "Failed to set I2C slave address ('%s')", path);
		goto oops;
	}
	if((rv = read(h->fd, &x, 1)) == 1) {
		h->addr_len = 1;
		syslog(LOG_INFO, "Inferred I2C EEPROM with 8-bit addressing on '%s'", path);
		return h;
	}

	syslog(LOG_ERR, "No I2C EEPROM found! Is the device %s absent or powered off?", path);
oops:
	if(h) {
		if(h->fd > 0)
			close(h->fd);
		free(h);
	}

	return NULL;
}

void i2c_eeprom_close(i2c_eeprom_handle *h) {
	close(h->fd);
	free(h);
}
