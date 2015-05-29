#include "iceboard.h"

/* IPMI structure documented in:
 *
 *    http://www.intel.com/content/dam/www/public/us/en/documents/product-briefs/platform-management-fru-document-rev-1-2-feb-2013.pdf
 *
 * We replace offsets with charater pointers, which are more convenient
 * to use in C. Otherwise, content is reasonably consistent with the
 * underlying IPMI structures.
 */

static char *parse_typed_string(const uint8_t *buf, const int buflen) {
	uint8_t type = buf[0] >> 6;
	uint8_t len = buf[0] & 0x3f;
	char *self;

	if(buflen <= 0 || *buf == 0xc1 || len==0)
		return NULL;

	if(len > buflen-1)
		return(NULL);

	switch(type) {
		case 0: /* Binary or unspecified */
		case 3: /* Assume 8-bit ASCII */
			self = malloc(len + 1);
			if(self) {
				memcpy(self, buf+1, len);
				self[len] = '\0';
			}
			return(self);
	}

	/* Other types (BCD plus, 6-bit packed ASCII) are unsupported */
	return NULL;
}

ipmi_struct *parse_ipmi(const uint8_t *buf, int buflen) {

	ipmi_struct *self;
	int i;
	uint8_t sum;
	uint8_t *tok, *cur; /* cursor points to head of current area; token is current data point */
	int len;

	/* Arbitrary: don't allow insane IPMI blocks, since we make
	 * complete copies of them. */
	if(buflen >= 65536)
		return(NULL);

	/* Parse common header. If these checks fail, we probably don't
	 * have a valid, populated IPMI structure. */
	if(buflen < 8 || buf[0] != 0x01 || buf[7] != 0x00)
		return NULL;

	/* Validate checksum */
	for(i=sum=0; i<8; i++)
		sum += buf[i];
	if(sum)
		return(NULL);

	/* We've passed some basic sanity-check stuff; it's time to
	 * allocate a structure to return. From here on, we try to be
	 * accepting of corrupted IPMI structures (we return only the
	 * sections that validate correctly) */
	if(!(self = calloc(sizeof(*self), 1)))
		goto error;

	/* Internal area is not currently supported */
	self->internal_area = NULL;

	/* Chassis Info Area */
	if(self->raw[2] && self->raw[2]*8+7 <= buflen) {
		cur = buf + self->raw[2]*8;
		len = cur[1] * 8;

		/* Validate version number and length */
		if(cur[0] == 0x01 && cur + len < buf + buflen)
			self->chassis_area = calloc(sizeof(*chassis_area), 1);

		if(self->chassis_area) {
			self->chassis_area->type = cur[2];

			/* fast-forward to the first type/length field */
			self->chassis_area->part_number = parse_typed_string(cur+3, len-3);
			tok = cur + 3;
		}
	}

	return(self);

error:
	if(self)
		free(self);

	return NULL;
}
