#ifndef __BASE64_H__
#define __BASE64_H__

#include <sys/types.h>

size_t base64_size_string(size_t blob_sz);
size_t base64_encode_blob(size_t blob_sz, const void *blob, char *s);
ssize_t base64_validate_string(const char *s);
size_t base64_size_blob(size_t s_sz);
ssize_t base64_decode_string(size_t s_sz, const char *s, size_t blob_sz, void *blob);

#endif
