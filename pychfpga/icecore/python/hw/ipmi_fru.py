'''A Generator for IPMI Field Replaceable Unit (FRU) Descriptors.

This module is intended to create EEPROM data formatted according to IPMI FRU
documentation available here:

	http://www.intel.com/content/www/us/en/servers/ipmi/information-storage-definition.html

This data is mandated, for example, in the FPGA Mezzanine Card (FMC) standard.
Since we run into similar requirements elsewhere, we re-use this structure
where it makes sense.

You can create a fully-populated (if meaningless) FRU as follows:

	x = FRU(
		Internal("internal_data"),
		Chassis(CHASSIS_OTHER,
			"part_number",
			"serial_number"
		),
		Board(datetime.now(),
			"manufacturer",
			"product_name",
			"serial_number",
			"part_number",
			"fru_file"
		),
		Product("manufacturer",
			"product_name",
			"part_number",
			"product_version",
			"serial_number",
			"asset_tag",
			"fru_file"
		),
		#Multi(...), when it's supported by this code
	)

Since these binary blobs are machine-parsed and used by on-board code to
identify and bring up hardware, it's important that you provide meaningful
and exact data. Do not rely on the example above -- there should be canonical
examples for each type of board under version control (most likely with the
board's QC scripts.)
'''

import struct
from datetime import datetime

# Chassis type codes
CHASSIS_OTHER=0x01
CHASSIS_UNKNOWN=0x02
CHASSIS_DESKTOP=0x03
CHASSIS_DESKTOP_LOW_PROFILE=0x04
CHASSIS_PIZZA_BOX=0x05
CHASSIS_MINI_TOWER=0x06
CHASSIS_TOWER=0x07
CHASSIS_PORTABLE=0x08
CHASSIS_LAPTOP=0x09
CHASSIS_NOTEBOOK=0x0A
CHASSIS_HANDHELD=0x0B
CHASSIS_DOCKING_STATION=0x0C
CHASSIS_ALL_IN_ONE=0x0D
CHASSIS_SUBNOTEBOOK=0x0E
CHASSIS_SPACE_SAVING=0x0F
CHASSIS_LUNCH_BOX=0x10
CHASSIS_MAIN_SERVER=0x11
CHASSIS_EXPANSION=0x12
CHASSIS_SUBCHASSIS=0x13
CHASSIS_BUS_EXPANSION=0x14
CHASSIS_PERIPHERAL=0x15
CHASSIS_RAID=0x16
CHASSIS_RACK_MOUNT=0x17
CHASSIS_SEALED_CASE_PC=0x18
CHASSIS_MULTI=0x19
CHASSIS_COMPACT_PCI=0x1a
CHASSIS_ADVANCED_TCA=0x1b
CHASSIS_BLADE=0x1c
CHASSIS_BLADE_ENCLOSURE=0x1d

def Internal(data):
	return struct.pack('B %is 0q' % len(data), 0x01, data)

def Chassis(type_code,
		part_number,
		serial_number):

	lprt = len(part_number)
	lser = len(serial_number)

	# Work out the structure length, including padding to 8-byte alignment
	length = 7 + lprt + lser
	length += -length%8

	# Build up the structure.
	x = struct.pack('BBB B%is B%is B x 0q' % (lprt, lser),
			0x01,		# version
			length/8,	# length
			type_code,	# language code (english)
			0xc0 | lprt, part_number,
			0xc0 | lser, serial_number,
			0xc1
	)

	# Replace last byte with checksum
	return x[:-1] + chr(0x100 - (sum(map(ord, x)) & 0xff))

def Board(mfg_date,
		manufacturer,
		product_name,
		serial_number,
		part_number,
		fru_file):

	# Convert mfg_date from a Python datetime() object to an IPMI minutes count
	mfg_date = mfg_date - datetime(1996, 1, 1)
	mfg_date = int(round(mfg_date.total_seconds() / 60))

	lman = len(manufacturer)
	lprd = len(product_name)
	lser = len(serial_number)
	lprt = len(part_number)
	lfru = len(fru_file)

	# Work out the structure length, including padding to 8-byte alignment
	length = 13 + lman + lprd + lser + lprt + lfru
	length += -length%8

	# Build up the structure.
	x = struct.pack('BBB BBB B%is B%is B%is B%is B%is B x 0q' % (
				lman, lprd, lser, lprt, lfru
			),
			0x01,		# version
			length/8,	# length
			0x00,		# language code (english)
			mfg_date >> 16, (mfg_date >> 8) & 0xff, mfg_date & 0xff,
			0xc0 | lman, manufacturer,
			0xc0 | lprd, product_name,
			0xc0 | lser, serial_number,
			0xc0 | lprt, part_number,
			0xc0 | lfru, fru_file,
			0xc1
	)

	# Replace last byte with checksum
	return x[:-1] + chr(0x100 - (sum(map(ord, x)) & 0xff))

def Product(manufacturer,
		product_name,
		part_number,
		product_version,
		serial_number,
		asset_tag,
		fru_file):

	lman = len(manufacturer)
	lprd = len(product_name)
	lprt = len(part_number)
	lver = len(product_version)
	lser = len(serial_number)
	ltag = len(asset_tag)
	lfru = len(fru_file)

	# Work out the structure length, including padding to 8-byte alignment
	length = 12 + lman + lprd + lprt + lver + lser + ltag + lfru
	length += -length%8

	# Build up the structure.
	x = struct.pack('BBB B%is B%is B%is B%is B%is B%is B%is B x 0q' % (
				lman, lprd, lprt, lver, lser, ltag, lfru
			),
			0x01,		# version
			length/8,	# length
			0x00,		# language code (english)
			0xc0 | lman, manufacturer,
			0xc0 | lprd, product_name,
			0xc0 | lprt, part_number,
			0xc0 | lver, product_version,
			0xc0 | lser, serial_number,
			0xc0 | ltag, asset_tag,
			0xc0 | lfru, fru_file,
			0xc1
	)

	# Replace last byte with checksum
	return x[:-1] + chr(0x100 - (sum(map(ord, x)) & 0xff))

def FRU(internal=None, chassis=None, board=None, product=None, multi=None):

	# Zero offsets indicate "block not present"
	internal_offset = 0x00
	chassis_offset = 0x00
	board_offset = 0x00
	product_offset = 0x00
	multi_offset = 0x00

	# Pack structures
	offset = 8

	internal_offset = offset if internal else 0x00
	internal = internal or ""
	offset += len(internal)

	chassis_offset = offset if chassis else 0x00
	chassis = chassis or ""
	offset += len(chassis)

	board_offset = offset if board else 0x00
	board = board or ""
	offset += len(board)

	product_offset = offset if product else 0x00
	product = product or ""
	offset += len(product)

	multi_offset = offset if multi else 0x00
	multi = multi or ""
	offset += len(multi)

	header = struct.pack("B BBBBB x B",
			0x01,	# version
			internal_offset/8,
			chassis_offset/8,
			board_offset/8,
			product_offset/8,
			multi_offset/8,
			0x00,	# checksum placeholder
	)

	# Replace last header byte with checksum
	header = header[:-1] + chr(0x100 - (sum(map(ord, header)) & 0xff))

	# Append data
	return header + internal + chassis + board + product + multi
