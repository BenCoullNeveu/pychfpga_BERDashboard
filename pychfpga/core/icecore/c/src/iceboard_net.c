#include <tuber.h>

#include "iceboard.h"

#include <sys/ioctl.h>
#include <sys/types.h>
#include <net/if.h>
#include <unistd.h>
#include <netinet/in.h>
#include <string.h>
#include <ifaddrs.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <netdb.h>

tuber_method(STRING, IceBoard, _get_arm_ip,
		"Retrieves the IP address associated with the ARM.",
		1, ((STRING_CONST, interface, json_string("eth0"), "Which Ethernet interface?")),
		1, (CATEGORY_ICEBOARD),
		""
) {
	struct ifaddrs *ifa, *cur;
	char *out = NULL;

	if(getifaddrs(&ifa) == -1) {
		oops("Unable to retrieve IP addresses!");
		return NULL;
	}

	for(cur=ifa; cur; cur=cur->ifa_next) {
		if(strcmp(interface, cur->ifa_name) != 0)
			continue;

		if(!cur->ifa_addr || cur->ifa_addr->sa_family != AF_INET)
			continue;

		if(!(out = malloc(NI_MAXHOST))) {
			oops("Error allocating memory!");
			goto err;
		}
		if(getnameinfo(cur->ifa_addr, sizeof(struct sockaddr_in),
					out, NI_MAXHOST,
					NULL, 0,
					NI_NUMERICHOST) != 0) {
			oops("Error calling getnameinfo()!");
			goto err;
		}
		freeifaddrs(ifa);
		return out;
	}
	oops("Didn't find an IPv4 entry for interface '%s'!", interface);
err:
	if(out)
		free(out);
	freeifaddrs(ifa);
	return NULL;
}

tuber_method(STRING, IceBoard, _get_arm_mac,
		"Retrieves the MAC address associated with the ARM.",
		1, ((STRING_CONST, interface, json_string("eth0"), "Which Ethernet interface?")),
		1, (CATEGORY_ICEBOARD),
		""
) {
	struct ifreq ifr;
	int sock = -1;
	char *out = NULL;

	if((sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP)) == -1) {
		oops("Error requesting ARM MAC address! (1)");
		goto err;
	}

	stpncpy(ifr.ifr_name, interface, IFNAMSIZ);
	if (ioctl(sock, SIOCGIFHWADDR, &ifr) != 0) {
		oops("Error requesting ARM MAC address! (2)");
		goto err;
	}

	if(!(out = malloc(18))) {
		/* Unlikely to work, but try anyway */
		oops("Error allocating memory!");
		goto err;
	}

	sprintf(out, "%02x:%02x:%02x:%02x:%02x:%02x",
		ifr.ifr_addr.sa_data[0],
		ifr.ifr_addr.sa_data[1],
		ifr.ifr_addr.sa_data[2],
		ifr.ifr_addr.sa_data[3],
		ifr.ifr_addr.sa_data[4],
		ifr.ifr_addr.sa_data[5]);

	close(sock);
	return(out);

err:
	if(sock > 0)
		close(sock);
	if(out)
		free(out);
	return(NULL);
}
