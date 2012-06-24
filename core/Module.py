#!/usr/bin/python
# Disable pylint TAB warnings (W0312) and Line too long (=C0301)
# pylint: disable=W0312,C0301 

"""
Module.py module 
  Module base class definition
#
# History:
	2011-08-03 JFC : Created from ANT.py
	2011-09-25 JFC: Added read_DRP and read_RAM 
	2012-06-23 JFC: Added bitfield_property to introduce a new way to define bitfields (allows these bitfields to be more easily referred to as function arguments, and makes pylint happier)
		Fixed class name printing when raising exception when attempting to write to a locked attribute
"""

import numpy as np
import time

class BitField(object):
	""" 
	Holds the definition of a memory-mapped variable
	It is implemented as a data descriptor shch that calls the read_field() and write_field() properties of the parent object when accessed.	
	"""
	# Page values
	CONTROL = 0
	STATUS = 1
	RAM = 2
	DRP = 3 # Dynamic Reconfiguration Port
	def __init__(self, page, addr, bit, width=1, default=None, doc=''): 
		self.page = page 
		self._addr = addr 
		self.bit = bit
		self.width = width 
		self.default = default
		self.doc = doc

	def __set__(self, obj, value):
		obj.write_field(self,value)

	def __get__(self, obj, obj_type):
		return obj.read_field(self)

	def get_addr(self):
		"""
		Returns the Memory-mapped address corresponding to the bit field
		"""
		if self.page == self.CONTROL:
			return 0x000+(self._addr & 0x07F)
		elif self.page == self.STATUS:
			return 0x080+(self._addr & 0x07F)
		elif self.page == self.RAM:
			return 0x200+(self._addr & 0x1FF)
		elif self.page == self.DRP:
			return 0x200+((self._addr<<1) & 0x1FF)

	addr = property(get_addr, doc='Returns the memory-mapped address of the current bitfield item')

#@staticmethod
def bitfield_property(*args, **kwargs):
	""" creates a property that accesses bit fields in the memory-mapped space"""
	bitfield = BitField(*args, **kwargs) # Creates a bitfield structure
	fget = lambda s, _bitfield = bitfield : s.read_field(_bitfield) # Pass bit_name as a default argument to 'close' that variable (i.e. bind it now). Otherwise the function will use the value at call time (which is the last value assigned to that variable) 
	fset = lambda s, value, _bitfield = bitfield : s.write_field(_bitfield, value)
	fdoc = bitfield.doc
	return property(fget, fset, doc=fdoc)

class Module_base(object):
	""" Implements basic interfaces to a module. It is intended to be inherited by a subclass that specializes to specific modules"""
	_locked = False # when 1, prevents the object to be modified

	CONTROL = BitField.CONTROL
	STATUS = BitField.STATUS
	DRP = BitField.DRP

	#BitDef=BitDef_base # make class accessible to subclass (somehow the class is not inherited directly)
	BITS = {} # Should be overriden by the subclass

	
	def __init__(self, fpga_instance, port_number, module_number):
		self._unlock()
		self.fpga = fpga_instance
		self.port_number = port_number 
		self.module_number = module_number
		for bit_name in self.BITS.keys():
			#print '  Defining property "%s"' % (bit_name)

			# Use function closures to create the callback function with arguments that won't be rebinded
			fget = lambda s, _bit_name = bit_name : s.read_field(_bit_name) # Pass bit_name as a default argument to 'close' that variable (i.e. bind it now). Otherwise the function will use the value at call time (which is the last value assigned to that variable) 
			fset = lambda s, value,_bit_name = bit_name : s.write_field(_bit_name,value)
#			if self.BITS[bit_name].page ==0x10:
#				setattr(self.__class__, bit_name, property(fget,doc=self.BITS[bit_name].doc))
#			else:
			setattr(self.__class__, bit_name, property(fget, fset, doc=self.BITS[bit_name].doc))

	def __setattr__(self, name, value):
		""" Prevents creating new attributes to the class when _locked==1"""
		if (not self._locked) or (hasattr(self, name)): # allow write if not locked or if attribute already exists
#			print 'setting ',name
			object.__setattr__(self, name, value)
		else:
			print "Class '%s' is locked: cannot assign new attribute '%s'" % (self, name)
			raise AttributeError("This instance of class '%s' is locked: cannot assign new attribute '%s'" % (self.__class__.__name__, name)) # 120623 JFC

	def __getitem__(self, index):
		if index in self.BITS:
			index = self.BITS[index].addr
		return self.read(index)

	def __setitem__(self, index, value):
		if index in self.BITS:
			index = self.BITS[index].addr
		self.write(index, value)
	def _unlock(self):
		self.__dict__['_locked'] = False
		
	def _lock(self):
		self.__dict__['_locked'] = True

	def read(self, addr, *args, **kwargs):
		if isinstance(addr, int):
			return self.fpga.read(self.port_number, self.module_number, addr, *args, **kwargs)
		elif isinstance(addr, str):
			return self.fpga.read(self.port_number, self.module_number, self.BITS[addr].addr, *args, **kwargs)

	def read_bit(self, addr, bit): 
		return bool(self.fpga.Read(self.port_number, self.module_number, addr) & (1<<bit))

	def read_DRP(self, addr):
		"""
		Reads a DRP (Dynamic Reconfigurable Port) from one of the FPGA internal devices (PLL, SYSMON, MGT etc). 'addr' is the 16-bit DRP register address.
		"""
		return self.read(0x200+2*addr, type=np.dtype('<u2'))

	def read_RAM(self, addr, *args, **kwargs):
		"""
		Reads a byte from the RAM space
		"""
		return self.read(0x200+2*addr,*args,**kwargs)

	def read_field(self, bit_name):
		""" Reads the field identified by the name 'bit_name' which is looked up in the BITS table to find the bit definition (port, bit position etc). Returns a boolean."""  
		if isinstance(bit_name, BitField):
			bit_def = bit_name
			bit_name = '(unspecified)'
		else:
			bit_def=self.BITS[bit_name]

		if bit_def.page==BitField.DRP:
			data= self.read_DRP(bit_def.addr) # read 16-bit value
			return (data>>bit_def.bit) & ((1<<bit_def.width)-1)

		word_width=8
		first_byte = int(bit_def.bit/word_width)
		last_byte = int((bit_def.bit+bit_def.width-1)/word_width)
		number_of_bytes = last_byte - first_byte+1
		data_type = {1:np.uint8, 2:np.uint16}[number_of_bytes]
		data= self.read(bit_def.addr + first_byte, type=data_type)
		
		#print 'Read ,bit "%s" at port %i, bit=%i, data: %X' % (bit_name,  bit_def.addr,bit_def.bit, data)
		return (data>>bit_def.bit) & ((1<<bit_def.width)-1)

	def write_field(self, bit_name, data):
		""" Writes the field identified by the name 'bit_name' which is looked up in the BITS table to find the bit definition (port, bit position etc). Returns a boolean."""  
		if isinstance(bit_name,BitField):
			bit_def = bit_name
			bit_name = '(unspecified)'
		else:
			bit_def=self.BITS[bit_name]
		#print 'Writing field',bit_name

		if (data>=2**bit_def.width) or data<0:
			raise Exception('Bad value %i for memory-mapped property %s' % (data, bit_name))

		if bit_def.page==BitField.DRP:
			old_data= self.read_DRP(bit_def.addr) # read 16-bit value
			mask=(2**bit_def.width-1)<<bit_def.bit
			new_data = old_data & ~mask
			new_data |= ((data << bit_def.bit) & mask) 
			self.write_DRP(bit_def.addr, new_data)
			return

		first_byte=int(bit_def.bit/8)
		last_byte=int((bit_def.bit+bit_def.width-1)/8)
		number_of_bytes=last_byte-first_byte+1
		data_type={1:np.uint8, 2:np.uint16}[number_of_bytes]
		
		old_data= self.read(bit_def.addr+first_byte, type=data_type)
		mask=(2**bit_def.width-1)<<bit_def.bit
		new_data = old_data & ~mask
		new_data |= ((data << bit_def.bit) & mask) 
		#print 'Read ,bit "%s" at port %i, bit=%i, data: %X' % (bit_name,  bit_def.port,bit_def.bit, data)
		#print 'old data, new_data=', hex(old_data), hex(new_data)
		#print 'type=',type(new_data)
		new_data=np.array([data_type(new_data)])
		new_data.dtype=np.uint8
		#print new_data
		self.write(bit_def.addr+first_byte, new_data)

	def write(self, addr, data, *args, **kwargs): 
		self.fpga.write(self.port_number, self.module_number,addr,data,*args,**kwargs)

	def write_ram(self, addr, data, *args, **kwargs): 
		"""
		Writes within the RAM/FIFO address space of the module. Simply calls the write() function with the appropriate address offset.
		"""
		self.write(addr+0x200, data, *args, **kwargs)

	def write_DRP(self, addr, data):
		"""
		Writes a DRP (Dynamic Reconfigurable Port) from one of the FPGA internal devices (PLL, SYSMON, MGT etc). 'addr' is the 16-bit DRP register address.
		"""
		self.write(0x200+2*addr, [data &0xFF, (data>>8)& 0xFF])

	def write_bit(self, addr, bit): 
		mask=(1<<bit)
		old_value = self.read(addr)
		self.write(addr,old_value & ~mask)
		self.write(addr,old_value | mask)

	def write_mask(self, addr, mask, data): 
		old_value = self.read(addr)
		self.write(addr, (old_value & ~mask) | (data & mask))

	def pulse_bit(self, addr, bit=0): 
		"""
		Pulses the specified bit to '1' then back to '0'. 
		if 'addr' is numeric, the bit 'bit' at address 'addr' is pulsed.
		If 'addr' is a string containing the name of a bit field, then this bit is pulsed.
		"""

		if addr in self.BITS:
			field_def = self.BITS[addr]
			if field_def.width!=1:
				raise Exception('The bit field must be a single bit (width=1)')
			(addr,bit)=(field_def.addr,field_def.bit)

		mask = (1<<bit)
		old_value = self.read(addr)
		self.write(addr, old_value | mask) # Set bit to '1'
		self.write(addr, old_value & ~mask) # Set bit to '0'

	def wait_for_bit(self,addr,bit=0,timeout=1): 
		"""
		Wait for spoecified bit to become '1'. 
		if 'addr' is numeric, the bit 'bit' at address 'addr' is pulsed.
		If 'addr' is a string containing the name of a bit field, then this bit is pulsed.
		"""

		if addr in self.BITS:
			field_def = self.BITS[addr]
			if field_def.width!=1:
				raise Exception('The bit field must be a single bit (width=1)')
			(addr,bit)=(field_def.addr, field_def.bit)

		mask = (1<<bit)
		t0 = time.time()
		while 1:
			if self.read(addr) & mask : return
			if (time.time()-t0)>timeout:
				raise(Warning('Timeout exceeded while waiting for status bit'))

	def init(self):
		pass

