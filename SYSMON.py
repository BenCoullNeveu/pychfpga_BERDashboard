#!/usr/bin/python

"""
SYSMON.py module 
 Implements the System Monitor interface
#
# History:
# 2011-07-08 : JFC : Created from test code in chFPGA.py
"""
import numpy as np

class SYSMON_base(object):
	# Registers
	TEMP_ADDR=0x00
	TEMP_MIN_ADDR=0x24
	TEMP_MAX_ADDR=0x20

	VCCINT_ADDR=0x01
	VCCINT_MIN_ADDR=0x25
	VCCINT_MAX_ADDR=0x21

	VCCAUX_ADDR=0x02
	VCCAUX_MIN_ADDR=0x26
	VCCAUX_MAX_ADDR=0x22

	VAUX_VPVN_ADDR=0x03
	VAUX_VREFP_ADDR=0x04
	VAUX_VREFN_ADDR=0x05


	VAUX_VOLT_ADDR=0x1C
	VAUX_CURR_ADDR=0x1D
	
	CONFIG1_ADDR=0x40
	CONFIG2_ADDR=0x41
	CONFIG3_ADDR=0x42
	SEQ_ADC_SEL1_ADDR=0x48
	SEQ_ADC_SEL2_ADDR=0x49
	SEQ_ADC_AVG1_ADDR=0x4A
	SEQ_ADC_AVG2_ADDR=0x4B
	SEQ_ADC_MODE1_ADDR=0x4C
	SEQ_ADC_MODE2_ADDR=0x4D
	SEQ_ADC_ACQTIME1_ADDR=0x4E
	SEQ_ADC_ACQTIME2_ADDR=0x4F



	def __init__(self,fpga,verbose=1):
		self.fpga_instance=fpga
		self.verbose=verbose


	def read(self,addr):
		""" Reads a 16-bit register of the FPGA system monitor at specified word address 
		"""
		fpga=self.fpga_instance
		#fpga.write_bit(fpga.SYSTEM_PORT,fpga.SYSTEM_SYSMON_MODULE,0x00,0,bool(addr>=0x40))
		return fpga.Read(fpga.SYSTEM_PORT,fpga.SYSTEM_SYSMON_MODULE,0x200+2*(addr),type=np.dtype('<u2')); # Sysmon data is read LSB first

	def write(self,addr,data):
		""" Writes a 16-bit register of the FPGA system monitor at specified word address 
		"""
		fpga=self.fpga_instance
		#fpga.write_bit(fpga.SYSTEM_PORT,fpga.SYSTEM_SYSMON_MODULE,0x00,0,bool(addr>=0x40))
		fpga.Write(fpga.SYSTEM_PORT,fpga.SYSTEM_SYSMON_MODULE,0x200+2*(addr),[data &0xFF, data>>8]); # Sysmon data is LSB first

	def init(self):
		self.write(self.CONFIG1_ADDR,0x0000)
		self.write(self.CONFIG2_ADDR,0x0000)
		self.write(self.SEQ_ADC_SEL1_ADDR,0x3F01) # Enable all ADC channels
		self.write(self.SEQ_ADC_SEL2_ADDR,0xFFFF)
		self.write(self.SEQ_ADC_AVG1_ADDR,0x3F01) # All averaging
		self.write(self.SEQ_ADC_AVG2_ADDR,0xFFFF)
		self.write(self.SEQ_ADC_MODE1_ADDR,0x0000) # All external channels set to single-ended
		self.write(self.SEQ_ADC_MODE2_ADDR,0x0000)
		self.write(self.SEQ_ADC_ACQTIME1_ADDR,0x0000) # all set to normal acq time
		self.write(self.SEQ_ADC_ACQTIME2_ADDR,0x0000)
		self.write(self.CONFIG1_ADDR,0x3000) # 256 averages
		self.write(self.CONFIG2_ADDR,0x2000) # Enable ADC channel auto sequencing


	def temperature(self,addr):
		""" Reads a registers of the FPGA system monitor and convert the result in Celcius """
		lsb=self.read(addr);
		temp=lsb/64.*503.975/1024.-273.15;
		return temp;

	def voltage(self,addr,vref=3.0):
		""" Reads a registers of the FPGA system monitor and convert the result in Volts """
		lsb=self.read(addr);
		volt=lsb/64.0*vref/1024;
		return volt;
	
	def status(self):
		print 'Temperature: %.1f C (%.2f C min, %.1f C max)' % (self.temperature(self.TEMP_ADDR),self.temperature(self.TEMP_MIN_ADDR),self.temperature(self.TEMP_MAX_ADDR))
		print 'VccINT: %.2f V (%.2f V min, %.2f V max)' % (self.voltage(self.VCCINT_ADDR),self.voltage(self.VCCINT_MIN_ADDR),self.voltage(self.VCCINT_MAX_ADDR))
		print 'VccAUX: %.2f V (%.2f V min, %.2f V max)' % (self.voltage(self.VCCAUX_ADDR),self.voltage(self.VCCAUX_MIN_ADDR),self.voltage(self.VCCAUX_MAX_ADDR))
		print 'ML605 12V Supply voltage: %.2f V (ADC input=%.2f V )' % (self.voltage(self.VAUX_VOLT_ADDR,vref=1.0)*24,self.voltage(self.VAUX_VOLT_ADDR,vref=1.0))
		print 'ML605 12V Supply current: %.2f A(?) (ADC input=%.2f V )' % (self.voltage(self.VAUX_CURR_ADDR,vref=1.0)/(0.001*50),self.voltage(self.VAUX_CURR_ADDR,vref=1.0))
		print 'VREFP: %.2f V, VREFN: %.2f V' % (self.voltage(self.VAUX_VREFP_ADDR),self.voltage(self.VAUX_VREFN_ADDR))
		print 'VCCInt Current: %.2f A, (ADC input= %.2f V' % (self.voltage(self.VAUX_VPVN_ADDR,vref=1.0)/0.005,self.voltage(self.VAUX_VPVN_ADDR,vref=1.0))

