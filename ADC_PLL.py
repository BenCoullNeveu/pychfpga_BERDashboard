#!/usr/bin/python

"""
ADC_PLL.py module 
 Implements the ADC PLL interface
#
# History:
# 2011-07-08 : JFC : Created from test code in chFPGA.py
"""
import numpy as np

class ADC_PLL_base(object):

	def __init__(self,fpga,verbose=1):
		self.fpga_instance=fpga
		self.verbose=verbose

	def write(self,data):
		""" Writes a 32-bit word to PLL (MSB first). The register address is contained in the word."""
		spi=self.fpga_instance.SPI
		spi.read_write(spi.SPI_PLL1_ADDR, data)

	def init(self,fout=1600, fref=25, **args):
		""" Initializes the ADC PLL to provide an adequate clock to the ADC.
			fout: ADC reference frequency in MHz. Sampling rate is fout/2.
			fref: PLL reference frequency in MHZ (typically 10 or 25 MHz)

		"""
		
		#fref=25 # MHz - PLL reference frequency (fixed)
		#fout=1600 # MHz - ADC Reference Frequency. Sampling rate is fout/2
		fdiv=2 if fout<2200 else 1 # Output division factor


		if self.verbose:
			print ' --- PLL Set-up ---'
			print ' Using reference frequency of %.0f MHz' % fref 
			print ' Target ADC refernece frequency: %.0f MHz' % fout 
			print ' Using RF frequency division ratio of %i' % fdiv 

		# REGISTER 5
		LD_pin_mode=1 # 0=LOW, 1=Lock Detect, 2=Low, 3= High

		# REGISTER 4
		FB_select=1 # 0=feedback from output divided, 1=feedback from VCO directly
		RF_div= int(np.log2(fdiv)) # Output divider: 0=/1, 1=/2, 2=/4, 3=/8, 4=/16
		band_sel_div=fref*8 #1-255. R counter output / band_sel_div < 125 kHz.
		vco_power_down=0 # 0-1
		mute_until_lock_detect=0 # 0-1
		AUX_sel=0 #  0=use output divider output, 1=use VCO output directly,
		AUX_enable=1 #0-1
		AUX_power=2 # 0=-4 dBm, 1=-1 dBm, 2=2 dBm, 3=5 dBm
		RF_enable=1		#0-1
		RF_power=2 # 0=-4 dBm, 1=-1 dBm, 2=2 dBm, 3=5 dBm

		# REGISTER 3
		cycle_slip_reduction=0 # 0-1. Needs 50% duty cycle and lowest CP current
		clock_div_mode=0 # 0=clock divider off, 1=fast lock, 2=resync enable, 3=reserved
		clock_div=1 # 0-4095

		
		# REGISTER 2
		noise_mode=0 # 0=low noise, 1-2: reserved, 3=low spur
		muxout=0 # !using 4 interferes with the locking process! 0=Hi-Z, 1=Vdd, 2=GND, 3=R Divider out, 4= N divider out, 5=Analog lock detect, 6= Digital lock detect, 7=reserved
		ref_doubler=0 # 0=disabled, 1=enabled
		rdiv2=0 # 0=disabled, 1=enabled
		R_counter=1 #1-1023
		double_buf=0 # 0=disabled, 1=enabled
		CP_current=0 # 0-15
		LDF=0 # 0 = frac-N, 1=INT-N
		LDP=1 # 0=10 ns, 1 = 6ns
		PD_polarity=1 # 0=negative, 1=positive
		power_down=0 # 0=disabled, 1=enabled
		CP_three_state=0 # 0=disabled, 1=enabled
		counter_reset=0 # 0=disabled, 1=enabled

		# REGISTER 1
		prescaler=0 # 0=4/5. 1=8/9
		phase=1 # 0-4095
		modulus=4095 # 0-4095

		# REGISTER 0
		int_div=fdiv*fout/fref; #23-65535
		frac_div=0; #0-4095

		# Override variable names if any is specified in the function call
		for (varname,value) in args.items():
			if varname in locals():
				print 'Setting %s = %i' % (varname, value)
				exec('%s=%i' % (varname, value))
			else:
				print '"%s" is not a PLL variable' % varname

		PLL_reg5=np.uint32((LD_pin_mode<<22)+(0x3<<19)+5);
		PLL_reg4=np.uint32((FB_select<<23)+(RF_div<<20)+(band_sel_div<<12)+(vco_power_down<<11)+(mute_until_lock_detect<<10)+(AUX_sel<<9)+(AUX_enable<<8)+(AUX_power<<6)+(RF_enable<<5)+(RF_power<<3)+4)
		PLL_reg3=np.uint32((cycle_slip_reduction<<18)+(clock_div_mode<<15)+(clock_div<<3)+3);
		PLL_reg2=np.uint32((noise_mode<<29)+(muxout<<26)+(ref_doubler<<25)+(rdiv2<<24)+(R_counter<<14)+(double_buf<<13)+(CP_current<<9)+(LDF<<8)+(LDP<<7)+(PD_polarity<<6)+(power_down<<5)+(CP_three_state<<4)+(counter_reset<<3)+2)
#		PLL_reg2_tristate=(noise_mode<<29)+(muxout<<26)+(ref_doubler<<25)+(rdiv2<<24)+(R_counter<<14)+(double_buf<<13)+(CP_current<<9)+(LDF<<8)+(LDP<<7)+(PD_polarity<<6)+(power_down<<5)+(1<<4)+(counter_reset<<3)+2
		PLL_reg1=np.uint32((prescaler<<27)+(phase<<15)+(modulus<<3)+1)
		PLL_reg0=np.uint32((int_div<<15)+(frac_div<<3)+0)
		
		self.write(np.uint32(PLL_reg5)); # write Reg 5: 
		self.write(np.uint32(PLL_reg4)); # write Reg 4: 
		self.write(np.uint32(PLL_reg3)); # write Reg 3: 
		self.write(np.uint32(PLL_reg2)); # write Reg 2: 
		self.write(np.uint32(PLL_reg1)); # write Reg 1: 
		self.write(np.uint32(PLL_reg0)); # write Reg 0: 
		
		return (PLL_reg0,PLL_reg1,PLL_reg2,PLL_reg3,PLL_reg4,PLL_reg5);

