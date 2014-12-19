#ifndef __I2C_EEPROM_H__
#define __I2C_EEPROM_H__

/* These functions MUST be called with some kind of I2C bus locking in
 * place! */

typedef struct i2c_eeprom_handle i2c_eeprom_handle;

i2c_eeprom_handle *i2c_eeprom_open(const char *path);
void i2c_eeprom_close(i2c_eeprom_handle *);

int i2c_eeprom_read(i2c_eeprom_handle *h, void *ptr, unsigned int offset, size_t size);
int i2c_eeprom_write(i2c_eeprom_handle *h, void *ptr, unsigned int offset, size_t size);

#endif
