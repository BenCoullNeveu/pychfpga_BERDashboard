#!/usr/bin/python

"""
Module.py module 
  Module base class definition
#
# History:
# 2011-08-03 : JFC : Created from ANT.py
"""

import numpy as np

class BitDef:
	""" Holds the definition of a memory-mapped variable"""
	def __init__(self,addr, bit, width=1, default=None, doc=''): 
		self.addr=addr 
		self.bit=bit
		self.width=width 
		self.default=default
		self.doc=doc

class Module_base(object):
	""" Implements basic interfaces to a module. It is intended to be inherited by a subclass that specializes to specific modules"""
	_locked=False # when 1, prevents the object to be modified

	#BitDef=BitDef_base # make class accessible to subclass (somehow the class is not inherited directly)
	BITS={} # Should be overriden by the subclass
	
	def __init__(self,fpga_instance,port_number,module_number):
		self._unlock()
		self.fpga=fpga_instance;
		self.port_number=port_number 
		self.module_number=module_number;
		for bit_name in self.BITS.keys():
			print '  Defining property "%s"' % (bit_name)

			# Use function closures to create the callback function with arguments that won't be rebinded
			fget=lambda s,_bit_name=bit_name:s.read_field(_bit_name) # Pass bit_name as a default argument to 'close' that variable (i.e. bind it now). Otherwise the function will use the value at call time (which is the last value assigned to that variable) 
			fset=lambda s,value,_bit_name=bit_name:s.write_field(_bit_name,value)
			if (self.BITS[bit_name].addr & 0xF0)==0x10:
				setattr(self.__class__, bit_name, property(fget,doc=self.BITS[bit_name].doc))
			else:
				setattr(self.__class__, bit_name, property(fget, fset,doc=self.BITS[bit_name].doc))

	def __setattr__(self, name, value):
		""" Prevents creating new attributes to the class when _locked==1"""
		if (not self._locked) or (hasattr(self,name)): # allow write if not locked or if attribute already exists
			object.__setattr__(self,name,value)
		else:
			raise AttributeError('Class is locked: cannot assign new attributes')

	def __getitem__(self, index):
		if index in self.BITS:
			index=self.BITS[index].addr
		return self.read(index)

	def __setitem__(self, index, value):
		if index in self.BITS:
			index=self.BITS[index].addr
		self.write(index,value)
	def _unlock(self):
		self.__dict__['_locked']=False
		
	def _lock(self):
		self.__dict__['_locked']=True

	def read(self,addr,*args,**kwargs): return self.fpga.Read(self.port_number, self.module_number,addr,*args,**kwargs)

	def read_bit(self,addr,bit): return bool(self.fpga.Read(self.port_number, self.module_number,addr)& (1<<bit))

	def read_field(self,bit_name):
		""" Reads the field identified by the name 'bit_name' which is looked up in the BITS table to find the bit definition (port, bit position etc). Returns a boolean."""  
		bit_def=self.BITS[bit_name]
		first_byte=int(bit_def.bit/8)
		last_byte=int((bit_def.bit+bit_def.width-1)/8)
		bytes=last_byte-first_byte+1
		type={1:np.uint8, 2:np.uint16}[bytes]
		data= self.read(bit_def.addr+first_byte, type=type)
		
		#print 'Read ,bit "%s" at port %i, bit=%i, data: %X' % (bit_name,  bit_def.addr,bit_def.bit, data)
		return data>>bit_def.bit & ((1<<bit_def.width)-1)

	def write_field(self,bit_name,data):
		""" Writes the field identified by the name 'bit_name' which is looked up in the BITS table to find the bit definition (port, bit position etc). Returns a boolean."""  
		bit_def=self.BITS[bit_name]
		if (data>=2**bit_def.width) or data<0:
			raise Exception('Bad value %i for memory-mapped property %s' % (data, bit_name))
		first_byte=int(bit_def.bit/8)
		last_byte=int((bit_def.bit+bit_def.width-1)/8)
		bytes=last_byte-first_byte+1
		type={1:np.uint8, 2:np.uint16}[bytes]
		
		old_data= self.read(bit_def.addr+first_byte, type=type)
		mask=(2**bit_def.width-1)<<bit_def.bit
		new_data = old_data & ~mask
		new_data |= ((data << bit_def.bit) & mask) 
		#print 'Read ,bit "%s" at port %i, bit=%i, data: %X' % (bit_name,  bit_def.port,bit_def.bit, data)
		#print 'old data, new_data=', hex(old_data), hex(new_data)
		#print 'type=',type(new_data)
		new_data=np.array([type(new_data)])
		new_data.dtype=np.uint8
		#print new_data
		self.write(bit_def.addr+first_byte, new_data)

	def write(self,addr,data,*args,**kwargs): 
		self.fpga.write(self.port_number, self.module_number,addr,data,*args,**kwargs)

	def write_ram(self,addr,data,*args,**kwargs): 
		"""
		Writes within the RAM/FIFO address space of the module. Simply calls the write() function with the appropriate address offset.
		"""
		self.fpga.write(self.port_number, self.module_number,addr+0x200,data,*args,**kwargs)

	def write_bit(self,addr,bit): 
		mask=(1<<bit)
		old_value=self.read(addr)
		self.write(addr,old_value & ~mask)
		self.write(addr,old_value | mask)

	def write_mask(self,addr,mask,data): 
		old_value=self.read(addr)
		self.write(addr,(old_value & ~mask) | (data & mask))

	def pulse_bit(self,addr,bit=0): 
		"""
		Pulses the specified bit to '1' then back to '0'. 
		if 'addr' is numeric, the bit 'bit' at address 'addr' is pulsed.
		If 'addr' is a string containing the name of a bit field, then this bit is pulsed.
		"""

		if addr in self.BITS:
			field_def=self.BITS[addr]
			if field_def.width!=1:
				raise Exception('The bit field must be a single bit (width=1)')
			(addr,bit)=(field_def.addr,field_def.bit)

		mask=(1<<bit)
		old_value=self.read(addr)
		self.write(addr,old_value | mask) # Set bit to '1'
		self.write(addr,old_value & ~mask) # Set bit to '0'

	def init(self):
		pass

