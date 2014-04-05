#define _GNU_SOURCE

#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <stdio.h>
#include <string.h>

#include <tuber.h>

#include "iceboard.h"
#include "iceboard_hw.h"

struct iceboard_gpio *get_gpio_by_netname(const char *name) {
	int n;
	struct iceboard_gpio *gpio;

	/* Find the GPIO in our look-up table */
	for(n=0; n<ICEBOARD_GPIO_COUNT; n++) {
		gpio = iceboard_gpio+n;

		if(strcmp(name, gpio->name) == 0)
			return(gpio);
	}

	return(NULL);
}

int export_gpio_by_netname(const char *name) {
	FILE *f;
	char buf[256];
	struct iceboard_gpio *gpio;

	if(!(gpio = get_gpio_by_netname(name)))
		return(-1);

	/* See if the GPIO is already exported. */
	sprintf(buf, "/sys/class/gpio/%s", gpio->name);
	if(access(buf, R_OK|W_OK|X_OK) != 0) {
		/* Doesn't exist or permissions weird. Try exporting. If that
		 * fails too, then complain. */
		f = fopen("/sys/class/gpio/export", "w");
		if(!f)
			return(-2);
		if(fprintf(f, "%i\n", gpio->gpio_num) <= 0)
			return(-3);
		fclose(f);
	}

	/* Some GPIOs are actually dangerous (see, for example, ARM_MR). You need to 
	 * Set up the direction; open direction and value files */
	sprintf(buf, "/sys/class/gpio/%s/direction", gpio->name);
	if((gpio->dir_fd = open(buf, O_RDWR)) == -1)
		return(-4);
	dprintf(gpio->dir_fd, gpio->mode==INPUT ? "in\n" : "out\n");

	sprintf(buf, "/sys/class/gpio/%s/value", gpio->name);
	if((gpio->value_fd = open(buf, O_RDWR)) == -1)
		return(-5);

	return(0);
}

void gpio_set(struct iceboard_gpio *self, int value) {
	/* To de-glitch, use the direction and not the value interface. See
	 * kernel Documentation/gpio.txt. */
	dprintf(self->dir_fd, value ? "high" : "low");
}

int gpio_get(struct iceboard_gpio *self, int set_input) {
	char buf[4];

	if(set_input)
		dprintf(self->dir_fd, "in\n");

	lseek(self->value_fd, 0, SEEK_SET);
	read(self->value_fd, buf, sizeof(buf));
	return(buf[0]=='1');
}

