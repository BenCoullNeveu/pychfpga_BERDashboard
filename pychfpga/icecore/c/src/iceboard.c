#include <tuber.h>

#include "iceboard.h"
#include "iceboard_hw.h"
#include "runtime.h"

#include <string.h>

tuber_object(iceboard,
		"Hardware wrapper for the McGill ICEboard.",
		"");

tuber_constructor(iceboard,
		"Create a new ICEboard object.",
		"") {

	iceboard *self = NULL;
	int n;
	const struct iceboard_gpio *gpio;

	if(!((self = calloc(1, sizeof(*self)))))
		fatal("Out of memory!");

	/* Set up GPIOs. Note that this happens every time an iceboard object
	 * is created, which may have side-effects for some GPIOs. */
	for(n=0; n<ICEBOARD_GPIO_COUNT; n++) {
		gpio = iceboard_gpio+n;

		if(export_gpio_by_netname(gpio->name) != 0)
			fatal("Unable to export GPIO %s (number %i)",
					gpio->name, gpio->gpio_num);
	}

	return(self);
}

tuber_destructor(iceboard,
		"Clean up after an ICEboard reference.",
		"") {
	free(self);
}

