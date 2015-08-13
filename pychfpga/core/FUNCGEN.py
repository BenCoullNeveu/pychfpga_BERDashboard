"""
FUNCGEN.py module
 Implements interface to the internal function generator

History:
    2012-10-01 JFC : Created from SRCSEL.py
    2012-10-17 JFC: Sets ramp as default function
"""

from Module import Module_base, BitField
import numpy as np

class FUNCGEN_base(Module_base):
    """ Implements interface to the function generator within a procecessor
    pipeline"""
    # Create local variables for page numbers tomake the table more readable
    CONTROL = BitField.CONTROL
    STATUS = BitField.STATUS

    DATA_SOURCE_NAMES = {
        'adc' : 0, # Data comes from the ADC
        'funcgen' : 1, # Data comes from the function generator
        # 'inject' : 2, # Data is injected by the user
        }

    FUNCTION_NAMES = {
        '4bit_split_ramp': 0,  # Generates 0x0000, 0x0010, 0x0020, .. 0x00F0, 0x1000, 0x1010 ...
        'a': 1,  # All bytes are Byte A
        'b': 2,  # All bytes are Byte B
        'ab': 3,  # Bytes alternate between A and B.
        'ramp': 4,  # Successive bytes generate a repeating ramp from 0 to 255.
        'real_ramp': 5,  # Generates the ramp: 0,0,0,1,0,2,0,3,0... If the data is read as (8+8)-bit complex value pairs, we obtain (0,0j), (1+0j)... (255+0j)
        '4bit_ramp': 6,  # Generates the ramp 0x00, 0x10, 0x20, ... 0xF0.
        '4bit_real_ramp': 7,  # Generates the ramp: 0x00, 0x00, 0x10, 0x00, 0x20, 0x00 ... 0xF0, 0x00
        'buffer': 8,  # (9,10 and 11 reserved for page selection) Sends the frame stored in the buffer
        'noise': 12,  # Noise generator
        }

    # Memory-mapped register definition
    RESET            = BitField(CONTROL, 0x00, 7, doc='Resets this module')
    # USE_OVERFLOW     = BitField(CONTROL, 0x00, 6, doc="when '1', overflow flags are generated when the outputs is 0x7F or 0x80")
    ENABLE           = BitField(CONTROL, 0x00, 5, doc="doc")
    SOURCE           = BitField(CONTROL, 0x00, 4, doc="0=ADC, 1=FUNCGEN")
    FUNCTION         = BitField(CONTROL, 0x00, 0, width=4, doc="Selects the waveform to be generated")
    BYTE_A           = BitField(CONTROL, 0x01, 0, width=8, doc="Byte A to be used by the function generator")
    BYTE_B           = BitField(CONTROL, 0x02, 0, width=8, doc="Byte B to be used by the function generator")
    NUMBER_OF_FRAMES = BitField(CONTROL, 0x03, 0, width=8, doc="Number of frames to send. If 0, send continuously.")

    RAMP_CTR   = BitField(STATUS, 0x00, 0, width=8, doc="Last 8 bits of the ramp counter (for debuging)")
    FRAME_CTR  = BitField(STATUS, 0x01, 0, width=8, doc="Frame counter")
    SEND_FRAME = BitField(STATUS, 0x02, 0, doc="debug")

    def __init__(self, fpga_instance, base_address, instance_number):
        # self.ant = ant_ch_instance
        # fpga = ant_ch_instance.fpga
        super(self.__class__, self).__init__(fpga_instance, base_address, instance_number)
        self._lock() # Prevent accidental addition of attributes (if, for example, a value is assigned to a wrongly-spelled property)
    # Specialized functions

    def reset(self):
        """ Resets the function generator"""
        self.pulse_bit('RESET')

    def set_data_source(self, source_name):
        """
        Sets the data source to be selected by the the SOURCE selector.

        You may need to sync after changing the data source as packet
        transmission might be interrupted and might confuse the downstream
        logic (FFT, crossbars, packet aligner etc.)
        """
        if source_name not in self.DATA_SOURCE_NAMES:
            raise Exception('Invalid data source name')
        else:
            self.SOURCE = self.DATA_SOURCE_NAMES[source_name]

    def get_data_source(self):
        """
        Gets the data source currently selected by the the SOURCE selector.
        """
        data_source_number = self.SOURCE  # make sure we read this only once
        return [key for (key,value) in self.DATA_SOURCE_NAMES.items() if value == data_source_number][0]


    def set_function(self, function_name, a=None, b=None, buffer_data=None, seed=None):
        """
        Sets the function to be generated  by the the function generator.

        The bytes 'a' and 'b' can optionnally be specified, otherwise their
        current value is used.
        ``seed`` is a 16-bit value used with the noise generators.
        """
        if function_name not in self.FUNCTION_NAMES:
            raise Exception('Invalid function name')
        if a is not None:
            self.BYTE_A = a
        if b is not None:
            self.BYTE_B = b
        if seed is not None:
            self.BYTE_A = seed & 0xff
            self.BYTE_B = (seed >> 8) & 0xff

        if buffer_data is not None:
            data = np.array(buffer_data, np.uint8)
            for page in range(4):
                self.FUNCTION = self.FUNCTION_NAMES['buffer'] + page
                self.write_ram(0, data[page * 512: (page + 1) * 512])
        self.FUNCTION = self.FUNCTION_NAMES[function_name]

    def init(self):
        """ Initializes the function generator """
        self.set_function('ramp')
        # self.USE_OVERFLOW = 1
        pass

    def status(self):
        """ Displays the status of the function generator module """
        print '-------------- ANT[%i].FUNCGEN STATUS --------------' % self.instance_number
        print ' Function number: %i' % self.FUNCTION
        print ' Ramp counter status:'
        print '    RAMP_CTR: %i' % self.RAMP_CTR


