chFPGA\_controller\.chFPGA\_controller
======================================

.. currentmodule:: pychfpga.core.chFPGA_controller

.. autoclass:: chFPGA_controller(...)
   :show-inheritance:


Method Summary (in alphabetical order)
--------------------------------------

.. autosummary::

      ~chFPGA_controller.__init__
      ~chFPGA_controller.init
      ~chFPGA_controller.capture_adc_eye_diagram
      ~chFPGA_controller.capture_frame_time
      ~chFPGA_controller.capture_refclk_time
      ~chFPGA_controller.check_adc_data_acquisition
      ~chFPGA_controller.check_command_count
      ~chFPGA_controller.check_ramp_errors
      ~chFPGA_controller.check_tuber_version
      ~chFPGA_controller.close
      ~chFPGA_controller.close_core
      ~chFPGA_controller.close_hw
      ~chFPGA_controller.compute_adc_delay_offsets
      ~chFPGA_controller.compute_adc_delays
      ~chFPGA_controller.compute_corr_output
      ~chFPGA_controller.configure_crossbar
      ~chFPGA_controller.fpga_i2c_set_port
      ~chFPGA_controller.fpga_i2c_write_read
      ~chFPGA_controller.get_FFT_bypass
      ~chFPGA_controller.get_FFT_shift
      ~chFPGA_controller.get_adc_board
      ~chFPGA_controller.get_adc_delays
      ~chFPGA_controller.get_adc_mode
      ~chFPGA_controller.get_crate_id
      ~chFPGA_controller.get_data_receiver
      ~chFPGA_controller.get_data_source
      ~chFPGA_controller.get_data_width
      ~chFPGA_controller.get_default_channels
      ~chFPGA_controller.get_fft_bypass
      ~chFPGA_controller.get_fft_shift
      ~chFPGA_controller.get_fpga_application_cookie
      ~chFPGA_controller.get_fpga_bitstream
      ~chFPGA_controller.get_fpga_core_cookie
      ~chFPGA_controller.get_fpga_firmware_cookie
      ~chFPGA_controller.get_fpga_firmware_timestamp
      ~chFPGA_controller.get_fpga_firmware_version
      ~chFPGA_controller.get_fpga_serial_number
      ~chFPGA_controller.get_frame_number
      ~chFPGA_controller.get_gains
      ~chFPGA_controller.get_handler_name
      ~chFPGA_controller.get_id
      ~chFPGA_controller.get_local_data_port_number
      ~chFPGA_controller.get_next_gain_bank
      ~chFPGA_controller.get_scaler_bypass
      ~chFPGA_controller.get_shuffle_status
      ~chFPGA_controller.get_slot_number
      ~chFPGA_controller.get_string_id
      ~chFPGA_controller.get_sync_source
      ~chFPGA_controller.get_temperatures
      ~chFPGA_controller.get_user_output_source
      ~chFPGA_controller.get_version
      ~chFPGA_controller.init_crossbars
      ~chFPGA_controller.is_core_open
      ~chFPGA_controller.is_fmc_present
      ~chFPGA_controller.is_fmc_present_for_channel
      ~chFPGA_controller.is_open
      ~chFPGA_controller.load_gains
      ~chFPGA_controller.mmi_read
      ~chFPGA_controller.mmi_write
      ~chFPGA_controller.open
      ~chFPGA_controller.open_core
      ~chFPGA_controller.open_hw
      ~chFPGA_controller.ping_fpga
      ~chFPGA_controller.print_tuber_methods
      ~chFPGA_controller.pulse_ant_reset
      ~chFPGA_controller.pulse_bit
      ~chFPGA_controller.read_bit
      ~chFPGA_controller.register_fpga_bitstream
      ~chFPGA_controller.reset
      ~chFPGA_controller.set_ADCDAQ_mode
      ~chFPGA_controller.set_FFT_bypass
      ~chFPGA_controller.set_FFT_shift
      ~chFPGA_controller.set_adc_delays
      ~chFPGA_controller.set_adc_mask
      ~chFPGA_controller.set_adc_mode
      ~chFPGA_controller.set_adcdaq_mode
      ~chFPGA_controller.set_ant_reset
      ~chFPGA_controller.set_cache
      ~chFPGA_controller.set_channelizer
      ~chFPGA_controller.set_channelizer_outputs
      ~chFPGA_controller.set_corr_reset
      ~chFPGA_controller.set_data_source
      ~chFPGA_controller.set_data_width
      ~chFPGA_controller.set_default_channels
      ~chFPGA_controller.set_fft_bypass
      ~chFPGA_controller.set_fft_shift
      ~chFPGA_controller.set_fpga_bitstream_crc
      ~chFPGA_controller.set_fpga_control_networking_parameters
      ~chFPGA_controller.set_funcgen_function
      ~chFPGA_controller.set_gains
      ~chFPGA_controller.set_global_trigger
      ~chFPGA_controller.set_local_data_port_number
      ~chFPGA_controller.set_offset_binary_encoding
      ~chFPGA_controller.set_pwm
      ~chFPGA_controller.set_scaler_bypass
      ~chFPGA_controller.set_send_flags
      ~chFPGA_controller.set_sync_source
      ~chFPGA_controller.set_trig
      ~chFPGA_controller.set_user_output_source
      ~chFPGA_controller.start_corr_capture
      ~chFPGA_controller.start_correlator
      ~chFPGA_controller.start_data_capture
      ~chFPGA_controller.status
      ~chFPGA_controller.stop_correlator
      ~chFPGA_controller.stop_data_capture
      ~chFPGA_controller.switch_gains
      ~chFPGA_controller.sync
      ~chFPGA_controller.test_correlator
      ~chFPGA_controller.test_correlator_output
      ~chFPGA_controller.test_speed
      ~chFPGA_controller.tuber_context
      ~chFPGA_controller.tune_adc_delays
      ~chFPGA_controller.update_config
      ~chFPGA_controller.write_bit
      ~chFPGA_controller.write_mask
      ~chFPGA_controller.arm_exec
      ~chFPGA_controller.arm_scp
      ~chFPGA_controller.fpga_mmi_read
      ~chFPGA_controller.fpga_mmi_write
      ~chFPGA_controller.get_config
      ~chFPGA_controller.get_fpga_bitstream_crc
      ~chFPGA_controller.get_status
      ~chFPGA_controller.get_total_power
      ~chFPGA_controller.set_fpga_bitstream
      ~chFPGA_controller.set_irigb_source
      ~chFPGA_controller.set_irigb_trigger_time

.. rubric:: IRIG-B

.. autosummary::

      ~chFPGA_controller.get_irigb_source
      ~chFPGA_controller.get_irigb_time


Class attributes (by category)
------------------------------

.. rubric:: Memory map addressing

The following define the chFPGA memory map fo the registers accessed through the direct FPGA UDP-Ethernet interface. This addresss space is separate from the ARM-FPGA SPI memory map. The addresses are hard-coded in the FPGA firmware and are essentially constants that must match with it.

More details on the UDP MMI protocol  can be found in the :class:`FpgaMmi` class. In a nutshell, read/write commands consist in a 3 bit operation code, 2-bit encoded length field for read operations, and 19 bits of address. The address space is divided hierarchically where address bits 19:17 select the top system (CHANNELIZER, CROSSBAR1,2 or 3, CORRELATOR etc.), with each of these system assigning address bits to sub- and sub-subsystem (each subsystems can subdivine memory differently). Within this single address space coexist three actual type of storage, which is determined by the operation code:

      - Control registers can be written and always read back. Masked writes are possible for efficient bitfield operations.
      - Status registers are read only
      - RAM/DRP access block RAMs or  Xilinx embedded blocks that offer their own memory map interface such as PLLs, GTXes etc.

-------

.. autosummary::

   ~chFPGA_controller._SYSTEM_BASE_ADDR
   ~chFPGA_controller._CHAN_BASE_ADDR
   ~chFPGA_controller._CROSSBAR1_BASE_ADDR
   ~chFPGA_controller._GPU_LINK_BASE_ADDR
   ~chFPGA_controller._CROSSBAR3_BASE_ADDR
   ~chFPGA_controller._CORR_BASE_ADDR
   ~chFPGA_controller._BP_SHUFFLE_BASE_ADDR
   ~chFPGA_controller._CROSSBAR2_BASE_ADDR
   ~chFPGA_controller._CHAN_ADDR_INCREMENT
   ~chFPGA_controller._CROSSBAR_ADDR_INCREMENT
   ~chFPGA_controller._GPU_LINK_ADDR_INCREMENT
   ~chFPGA_controller._CORR_ADDR_INCREMENT
   ~chFPGA_controller._BP_SHUFFLE_ADDR_INCREMENT
   ~chFPGA_controller._CHAN_SUBMODULE_ADDR_INCREMENT
   ~chFPGA_controller._SYSTEM_GPIO_BASE_ADDR
   ~chFPGA_controller._SYSTEM_SYSMON_BASE_ADDR
   ~chFPGA_controller._SYSTEM_FREQ_CTR_BASE_ADDR
   ~chFPGA_controller._SYSTEM_SPI_BASE_ADDR
   ~chFPGA_controller._SYSTEM_REFCLK_BASE_ADDR

The `_SYSTEM_I2C_BASE_ADDR` is defined elsewhere.


.. rubric:: Memory map addressing

.. autosummary::

      ~chFPGA_controller.ADC_MODE_NAMES
      ~chFPGA_controller.FPGA_APPLICATION_FIRMWARE_COOKIE_ADDR
      ~chFPGA_controller.FPGA_APPLICATION_FLAGS_ADDR
      ~chFPGA_controller.FPGA_CORE_FIRMWARE_COOKIE_ADDR
      ~chFPGA_controller.FPGA_FIRMWARE_CRC32_ADDR
      ~chFPGA_controller.FPGA_FIRMWARE_TIMESTAMP_ADDR
      ~chFPGA_controller.FPGA_SERIAL_NUMBER_LSW_ADDR
      ~chFPGA_controller.FPGA_SERIAL_NUMBER_MSW_ADDR
      ~chFPGA_controller.NUMBER_OF_FMC_SLOTS
      ~chFPGA_controller.crate
      ~chFPGA_controller.detect_irigb_source
      ~chFPGA_controller.fpga_ip_addr
      ~chFPGA_controller.hostname
      ~chFPGA_controller.init
      ~chFPGA_controller.interface_ip_addr
      ~chFPGA_controller.is_irigb_before_trigger_time
      ~chFPGA_controller.mezzanine
      ~chFPGA_controller.open
      ~chFPGA_controller.parent
      ~chFPGA_controller.part_number
      ~chFPGA_controller.ping
      ~chFPGA_controller.serial
      ~chFPGA_controller.slot
      ~chFPGA_controller.tuber_objname
      ~chFPGA_controller.tuber_uri
      ~chFPGA_controller.zero_target_irigb_year_and_day


chFPGA_controller Class
-----------------------

Initialization
**************

The initialization of an IceBoard and its firmware is done in 3 stages:
      1) `__init__` creates `chFPGA_controller` intance but does not attempt to communicate with the IceBoard (neitherthe ARM nor the FPGA). This allows the hardware map to be populated with `chFPGA_controller` instances even if the boards are not present or are not turned on yet. After `init`, the user can issue commands that require communication with the ARM processor only, and the connection will be established at that time.
      2) `open` establish UDP communications with the FPGA, and the FPGA configuration is read only. Python objecs are created.
      3) `init` Initializes the python objects and the chFPGA firmare registers.

.. automethod:: chFPGA_controller.__init__(*see below*)
.. automethod:: chFPGA_controller.open(*see below*)
.. automethod:: chFPGA_controller.init(*see below*)
.. automethod:: chFPGA_controller.get_config (*see below*)

