# This file is for specifying the entries in the configuration file

n_antenna = integer(min = 1)
n_freq    = integer(min = 1)

[fpga]
  ip_address = ip_addr
  port = integer(min = 1)
  samp_freq  = float(min = 1)
  ref_freq = float(min = 1)
  int_period = float(min = 0)
  [[adc_delay]]

[acq]
  base_path = string
  frames_per_file = integer(min = 1)
  len_frame_buf = integer(min = 1)
  [[udp]]
    port = integer(min = 1)
    max_len = integer(min = 1)
    buf_len = integer(min = 1)
  [[serial]]
    path = string
    n_adc = integer(min = 1)
    [[[channel]]]
  [[cal]]
