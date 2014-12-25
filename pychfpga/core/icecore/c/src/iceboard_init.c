#include <syslog.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>

#include "iceboard.h"
#include "ipmi_frui.h"

int main(void) {
	FILE *mtd = NULL;
	frui *frui = NULL;
	const char *serial;
	char hostname[64];

	openlog("iceboard_init", LOG_CONS, LOG_DAEMON);

	if(!(mtd = get_motherboard_ipmi_file("r"))) {
		syslog(LOG_WARNING, "Unable to access IPMI partition in SPI flash!");
		return(-1);
	}

	if(!(frui = IceBoard_get_motherboard_ipmi_raw())) {
		syslog(LOG_WARNING, "Unable to retrieve IPMI data from SPI flash!");
		return(-1);
	}

	serial = frui_get_board_serial_number(frui);

	memset(hostname, 0, sizeof(hostname));
	snprintf(hostname, 63, "iceboard%s", serial);
	if(sethostname(hostname, strlen(hostname)) == -1) {
		syslog(LOG_WARNING, "Unable to set hostname (%s, %s)",
				hostname, strerror(errno));
		return(-1);
	}

	return(0);
}
