# This file is for specifying the entries in the configuration file.
# This is NOT the configuration file. That file should end in .conf.

n_antenna = integer(min = 1)
n_freq    = integer(min = 1)

[fpga]
  ip_address = ip_addr
  port = integer(min = 1)
  samp_freq  = float(min = 1)
  ref_freq = float(min = 1)
  fft_shift = integer(min = 1)
  gain = integer(min = 0)
  data_width = integer(min = 4)
  group_frames = integer(min = 1 )
  host_ip = ip_addr
  [[adc_delay]]

[acq]
  base_path = string
  frames_per_file = integer(min = 1)
  len_frame_buf = integer(min = 1)
  [[udp]]
    port = integer(min = 1)
    max_len = integer(min = 1)
    buf_len = integer(min = 1)
    spf = integer(min = 1)
  [[serial]]
    path = string
    timeout = float(min = 0)
    [[[channel]]]
  [[cal]]
