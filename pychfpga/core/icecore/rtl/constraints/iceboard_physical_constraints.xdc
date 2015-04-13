###############################
# GLOBAL PROPERTIES
###############################

set_property BITSTREAM.GENERAL.COMPRESS true [current_design]
set_property BITSTREAM.CONFIG.USR_ACCESS TIMESTAMP [current_design]
set_property BITSTREAM.CONFIG.OVERTEMPPOWERDOWN ENABLE [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]

#################################
# SYSTEM RESET
#################################

# RESET is on ARM_RST_O
# NOTE: *** THIS AN ACTIVE LOW RESET ****
set_property PACKAGE_PIN V30 [get_ports cpu_reset_n]
set_property IOSTANDARD LVCMOS25 [get_ports cpu_reset_n]

#################################
# Buck regulator synchronization signals
#################################

set_property IOSTANDARD LVCMOS25 [get_ports {sync_*}]

set_property PACKAGE_PIN J24 [get_ports sync_1v0]
set_property PACKAGE_PIN A22 [get_ports sync_1v8]
set_property PACKAGE_PIN D21 [get_ports sync_1v0_gtx]
set_property PACKAGE_PIN D22 [get_ports sync_5v0]
set_property PACKAGE_PIN L17 [get_ports sync_1v2]
set_property PACKAGE_PIN H21 [get_ports sync_vadj]
set_property PACKAGE_PIN A23 [get_ports sync_1v5]
set_property PACKAGE_PIN AE28 [get_ports sync_3v3]
set_property PACKAGE_PIN AF28 [get_ports sync_12v0]

# Clocks

# Iceboard PLL Default Configuration Information
# PLL1:
#   Out 0: 20 MHz (to ARM)
#   Out 1: 100 MHz (on MGTCLKREF1_114/CLK_100MHZ_P/N, for ARM/PCI)
#   Out 2: 25 MHz ( to PHY)
#   Out 3: 125 MHz (on MGTCLKREF1_116/cfp_clk_p/n, for SFP 1000BASE-R)
#   Out 4: 200 MHz (on MGTCLKREF1_112)

# PLL2:
#   Out 0: 156.25 MHz (on MGTCLKREF0_112, for 10GE SHUFFLE/QUAD/QSFP+)
#   Out 1: 156.25 MHz (on MGTCLKREF0_114, for 10GE SHUFFLE/QUAD/QSFP+)
#   Out 2: 156.25 MHz (on MGTCLKREF0_116 / xge_refclk_p/n,  for 10GE SHUFFLE/QUAD/QSFP+)
#   Out 3: 125 MHz (on MGTCLKREF0_115, alternate 1000BASE-R or others)
#   Out 4: 10 MHz (on MGTCLKREF1_115, PLL bypass, for access to original reference, AC coupled)

# GTX Reference clock summary
# Refclk input | Description
# ---------------------------
# GTX111_0 | FMCA_GBTCLK0 (FMCA DP on GTX111 & GTX112)
# GTX111_1 | FMCA_GBTCLK1 (FMCA DP on GTX111 & GTX112)
# GTX112_0 | 156.25 MHz from PLL2, output 0 (CLK_GTX112_A) (BP Shuffle on GTX111 & GTX112)
# GTX112_1 | 200 MHz from PLL1, output 4 (CLK_GTX112_B)
# GTX113_0 | FMCB_GBTCLK0 (FMCB DP on GTX113 & GTX114)
# GTX113_1 | FMCB_GBTCLK1 (FMCB DP on GTX113 & GTX114)
# GTX114_0 | 156.25 MHz from PLL2, output 1 (CLK_GTX114_A) (BP Shuffle on GTX114 & GTX115 and BP QSFP on GTX113)
# GTX114_1 | 100 MHz from PLL1, output 1 (CLK_100MHZ_1) (PCIe on GTX115)
# GTX115_0 | 125 MHz from PLL2, output 3 (CLK_GTX115_A)
# GTX115_1 | 10 MHz from PLL2, output 4 (CLK_GTX115_B)
# GTX116_0 | 156.25 MHz from PLL2, output 2 (CLK_GTX116_A) (MB QSFP on GTX116/GTX117, and SFP+ 10GigE on GTX115)
# GTX116_1 | 125 MHz from PLL1, output 3 (CLK_GTX116_B) (SFP GigE)
# GTX117_0 | Not connected
# GTX117_1 | Not connected

# GTX Usage
# Bank   | Usage
# ---------------------------
# GTX111 | FMCA DP Lines (use GTX111_0/1 clock) or BP Shuffle (use 156.25 MHz clock from GTX112_0)
# GTX112 | FMCA DP Lines (use GTX111_0/1 clock) or BP Shuffle (use 156.25 MHz clock from GTX112_0)
# GTX113 | FMCB DP Lines (use GTX113_0/1 clock) or BP QSFP (use 156.25 MHz clock from GTX114_0)
# GTX114 | FMCB DP Lines (use GTX113_0/1 clock) or BP Shuffle (use 156.25 MHz clock from GTX114_0)
# GTX115 | GBT3: PCIe (use 100 MHz clock from GTX114_1) or SFP+ (use 125 MHz clock from GTX116_1 for Gb Ethernet, 156.215 MHz clock from GTX116_0 for 10G Ethernet)
#        | GBT0-2: BP Shuffle (use 156.25 MHz clock from GTX114_0)
# GTX116 | Motherboard QSFPA (use 156.25 MHz clock from GTX116_0)
# GTX117 | Motherboard QSFPA (use 156.25 MHz clock from GTX116_0)

# Non-dedicated GTX clock inputs (dedicated clocks are defined in their respective sections below)

# 200 MHz GTX reference clock on CLK_GTX112B (MGTREFCLK1, Bank 112)
# set_property PACKAGE_PIN AF6 [get_ports gtx112_clk200_p]
# set_property PACKAGE_PIN AF5 [get_ports gtx112_clk200_n]

# 125 MHz GTX reference clock on CLK_GTX115_A (MGTREFCLK0, Bank 115)
# set_property PACKAGE_PIN J8 [get_ports gtx115_clk125_p]
# set_property PACKAGE_PIN J7 [get_ports gtx115_clk125_n]

# 10 MHz GTX reference clock on CLK_GTX115_B (MGTREFCLK1, Bank 115)
# set_property PACKAGE_PIN L8 [get_ports gtx115_clk10_p]
# set_property PACKAGE_PIN L7 [get_ports gtx115_clk10_n]

#################################
# Motherboard SFP+ / ARM PCIe
#################################

# 125 MHz  reference clock on CLK_FPGA_B (MGTREFCLK1, Bank 116)
set_property PACKAGE_PIN H6 [get_ports sfp_clk125_p]
set_property PACKAGE_PIN H5 [get_ports sfp_clk125_n]

# 100 MHz GTX reference clock on CLK_100MHZ1 (MGTREFCLK1, Bank 114)
# set_property PACKAGE_PIN T6 [get_ports pcie_clk100_p]
# set_property PACKAGE_PIN T5 [get_ports pcie_clk100_n]

# SFP/PCIe data lines on the PCI_SFP GTX transceiver (MGT3, Bank 115)
# set_property PACKAGE_PIN J3 [get_ports pcie_sfp_rx_n]
# set_property PACKAGE_PIN J4 [get_ports pcie_sfp_rx_p]
# set_property PACKAGE_PIN F1 [get_ports pcie_sfp_tx_n]
# set_property PACKAGE_PIN F2 [get_ports pcie_sfp_tx_p]

#################################
# Motherboard QSFP+
#################################

# 156.25 MHz  reference clock on CLK_FPGA_A (MGTREFCLK0, Bank 116)
# mp_qsfp_clk156[0] on MGTREFCLK116_0 (covers GTX116, GTX117)
# set_property PACKAGE_PIN F6 [get_ports {mb_qsfp_clk156_p[0]}]

# QSFP A - GTX116
# No need to define tx_n, rx_p or rx_n as those are automatically inferred
# set_property PACKAGE_PIN D2 [get_ports {mb_qsfp_tx_p[0]}]
# set_property PACKAGE_PIN B2 [get_ports {mb_qsfp_tx_p[1]}]
# set_property PACKAGE_PIN A4 [get_ports {mb_qsfp_tx_p[2]}]
# set_property PACKAGE_PIN B6 [get_ports {mb_qsfp_tx_p[3]}]

# QSFP B - GTX117
# set_property PACKAGE_PIN C8 [get_ports {mb_qsfp_tx_p[4]}]
# set_property PACKAGE_PIN A8 [get_ports {mb_qsfp_tx_p[5]}]
# set_property PACKAGE_PIN B10 [get_ports {mb_qsfp_tx_p[6]}]
# set_property PACKAGE_PIN A12 [get_ports {mb_qsfp_tx_p[7]}]

#################################
# Backplane shuffle
#################################

# 156.25 MHz Reference clocks
# bp_shuffle_clk156[0] on MGTREFCLK112_0 (covers GTX111, GTX112)
# bp_shuffle_clk156[1] on MGTREFCLK114_0 (covers GTX114, GTX115)
# set_property PACKAGE_PIN AD6 [get_ports {bp_shuffle_clk156_p[0]}]
# set_property PACKAGE_PIN R8 [get_ports {bp_shuffle_clk156_p[1]}]

# Backplane shuffle lane assignments
# ------------------
#   | Signal_name         | Lane # |  GTX #    |  GTX LOC  |FPGA Pin # | Ref clock
#   |---------------------|--------|-----------|-----------|-----------|-----------
#   | bp_shuffle_tx_p[0]  |   1    |  GTX114_3 |  X0Y15_TX | N4        | GTX114_0
#   | bp_shuffle_tx_p[1]  |   2    |  GTX114_2 |  X0Y14_TX | P2        | GTX114_0
#   | bp_shuffle_tx_p[2]  |   3    |  GTX114_1 |  X0Y13_TX | T2        | GTX114_0
#   | bp_shuffle_tx_p[3]  |   4    |  GTX114_0 |  X0Y12_TX | V2        | GTX114_0
#   | bp_shuffle_tx_p[4]  |   5    |  GTX111_3 |  X0Y3_TX  | AG8       | GTX112_0
#   | bp_shuffle_tx_p[5]  |   6    |  GTX111_2 |  X0Y2_TX  | AJ8       | GTX112_0
#   | bp_shuffle_tx_p[6]  |   7    |  GTX111_1 |  X0Y1_TX  | AK10      | GTX112_0
#   | bp_shuffle_tx_p[7]  |   8    |  GTX111_0 |  X0Y0_TX  | AJ12      | GTX112_0
#   | bp_shuffle_tx_p[8]  |   9    |  GTX112_3 |  X0Y7_TX  | AH2       | GTX112_0
#   | bp_shuffle_tx_p[9]  |   10   |  GTX112_2 |  X0Y6_TX  | AK2       | GTX112_0
#   | bp_shuffle_tx_p[10] |   11   |  GTX112_1 |  X0Y5_TX  | AJ4       | GTX112_0
#   | bp_shuffle_tx_p[11] |   12   |  GTX112_0 |  X0Y4_TX  | AK6       | GTX112_0
#   | bp_shuffle_tx_p[12] |   13   |  GTX115_0 |  X0Y16_TX | M2        | GTX114_0
#   | bp_shuffle_tx_p[13] |   14   |  GTX115_1 |  X0Y17_TX | K2        | GTX114_0
#   | bp_shuffle_tx_p[14] |   15   |  GTX115_2 |  X0Y18_TX | H2        | GTX114_0

# The GTX are connected to the backplane shuffle lines
# only if the passive resistor network switch is configured appropriately

# set_property PACKAGE_PIN N4 [get_ports {bp_shuffle_tx_p[0]}]
# set_property PACKAGE_PIN P2 [get_ports {bp_shuffle_tx_p[1]}]
# set_property PACKAGE_PIN T2 [get_ports {bp_shuffle_tx_p[2]}]
# set_property PACKAGE_PIN V2 [get_ports {bp_shuffle_tx_p[3]}]
# set_property PACKAGE_PIN AG8 [get_ports {bp_shuffle_tx_p[4]}]
# set_property PACKAGE_PIN AJ8 [get_ports {bp_shuffle_tx_p[5]}]
# set_property PACKAGE_PIN AK10 [get_ports {bp_shuffle_tx_p[6]}]
# set_property PACKAGE_PIN AJ12 [get_ports {bp_shuffle_tx_p[7]}]
# set_property PACKAGE_PIN AH2 [get_ports {bp_shuffle_tx_p[8]}]
# set_property PACKAGE_PIN AK2 [get_ports {bp_shuffle_tx_p[9]}]
# set_property PACKAGE_PIN AJ4 [get_ports {bp_shuffle_tx_p[10]}]
# set_property PACKAGE_PIN AK6 [get_ports {bp_shuffle_tx_p[11]}]
# set_property PACKAGE_PIN M2 [get_ports {bp_shuffle_tx_p[12]}]
# set_property PACKAGE_PIN K2 [get_ports {bp_shuffle_tx_p[13]}]
# set_property PACKAGE_PIN H2 [get_ports {bp_shuffle_tx_p[14]}]

#################################
# Backplane QSFP+
#################################
# Use bp_shuffle_clk156[1] (on GTX114_0) as reference clock

# Backplane QSFP - GTX113
# No need to define tx_n, rx_p or rx_n as those are automatically inferred
# set_property PACKAGE_PIN AF2 [get_ports {bp_qsfp_tx_p[0]}]
# set_property PACKAGE_PIN AD2 [get_ports {bp_qsfp_tx_p[1]}]
# set_property PACKAGE_PIN AB2 [get_ports {bp_qsfp_tx_p[2]}]
# set_property PACKAGE_PIN Y2  [get_ports {bp_qsfp_tx_p[3]}]

#################################
# FPGA I2C
#################################
# Allows access to the motherboard, mezzanine and backplane I2C devices through an I2C switch
#set_property PACKAGE_PIN R21 [get_ports i2c_scl]
#set_property DRIVE 8 [get_ports i2c_scl]
#set_property IOSTANDARD LVCMOS25 [get_ports i2c_scl]
#set_property SLEW SLOW [get_ports i2c_scl]

#set_property PACKAGE_PIN V29 [get_ports i2c_sda]
#set_property DRIVE 8 [get_ports i2c_sda]
#set_property IOSTANDARD LVCMOS25 [get_ports i2c_sda]
#set_property SLEW SLOW [get_ports i2c_sda]

#################################
# ARM <-> FPGA SPI link
#################################

set_property IOSTANDARD LVCMOS25 [get_ports arm_spi_*]
set_property SLEW SLOW [get_ports arm_spi_miso]
set_property DRIVE 16 [get_ports arm_spi_miso]

set_property PACKAGE_PIN T22 [get_ports arm_spi_sck]
set_property PACKAGE_PIN R30 [get_ports arm_spi_miso]
set_property PACKAGE_PIN T30 [get_ports arm_spi_mosi]
set_property PACKAGE_PIN R20 [get_ports arm_spi_cs_n]

#################################
# BP IO PINS
#################################

# | port name      | FPGA pin | Schematic net name | Motherboard Connectivity | Backplane connectivity
# |----------------|----------|--------------------|--------------------------|------------------------
# | sma_a          | AG27     | BP_IO5             | SMA_A                    | ref_cap
# | sma_b_fpga_led2| W26      | BP_IO4             | SMA-B  SW8  FPGA_LED2    | slotid_cap1
# | bp_time_p      | AG30     | BP_IO0_P           |        SW1               | time_p
# | bp_time_n      | AH30     | BP_IO0_N           |        SW2               | time_n
# | bp_trig_p      | AJ29     | BP_IO1_P           |        SW3               | trig_p
# | bp_trig_n      | AK30     | BP_IO1_N           |        SW4               | trig_n
# | bp_io2_p       | AK28     | BP_IO2_P           |        SW5               | gpio_int
# | bp_io2_n       | AK29     | BP_IO2_N           |        SW6               | buck_sync
# | fpga_led1      | W24      | BP_IO3             |        SW7  FPGA_LED1    | slotid_cap0
#
# All single-ended signals are LVCMOS25
# All Differentials are LVDS_25
# Differential signals can be used as two independend single-ended lines

# SMA_A
set_property PACKAGE_PIN AG27 [get_ports sma_a]
set_property IOSTANDARD LVCMOS25 [get_ports {sma_a}]
set_property SLEW FAST [get_ports {sma_a}]
set_property DRIVE 12 [get_ports {sma_a}]

# SMA_B / FPGA LED2
set_property PACKAGE_PIN W26 [get_ports sma_b_fpga_led2]
set_property IOSTANDARD LVCMOS25 [get_ports {sma_b_fpga_led2}]
set_property SLEW FAST [get_ports {sma_b_fpga_led2}]
set_property DRIVE 12 [get_ports {sma_b_fpga_led2}]

# Backplane TIME
set_property PACKAGE_PIN AH30 [get_ports bp_time_n]
set_property PACKAGE_PIN AG30 [get_ports bp_time_p]
set_property IOSTANDARD LVDS_25 [get_ports {bp_time_*}]

# Backplane TRIG
# set_property PACKAGE_PIN AK30 [get_ports bp_trig_n]
# set_property PACKAGE_PIN AJ29 [get_ports bp_trig_p]
# set_property IOSTANDARD LVDS_25 [get_ports {bp_trig_*}]

# BP_IO2_P - Used as single ended signal
# set_property PACKAGE_PIN AK28 [get_ports bp_io2_p]
# set_property IOSTANDARD LVCMOS25 [get_ports bp_io2_p]

# BP_IO2_N - Used as single ended signal
# set_property PACKAGE_PIN AK29 [get_ports bp_io2_n]
# set_property IOSTANDARD LVCMOS25 [get_ports bp_io2_n]

# FPGA LED1
set_property PACKAGE_PIN W24 [get_ports fpga_led1]
set_property IOSTANDARD LVCMOS25 [get_ports fpga_led1]

#################################
# Unused FPGA Pins
#################################

# Connected but unused FPGA signals
# set_property PACKAGE_PIN Y23 [get_ports {UART1_TX_V}]
# set_property PACKAGE_PIN AE20 [get_ports {UART1_TX_V}]
# set_property PACKAGE_PIN Y24 [get_ports {GPIO_RST_V}]
# set_property PACKAGE_PIN W21 [get_ports {ARM_IRQ_V}]
# set_property PACKAGE_PIN E24 [get_ports {CLK_RAW}]
# set_property PACKAGE_PIN V26 [get_ports {FLASH_CS_V}]; # config
# set_property PACKAGE_PIN R18 [get_ports {GPIO_IRQ_V}]

# Unconnected FPGA pins
# set_property PACKAGE_PIN AC19 [get_ports {nc0}]
# set_property PACKAGE_PIN L22 [get_ports {nc1}]
# set_property PACKAGE_PIN M27 [get_ports {nc2}]
# set_property PACKAGE_PIN N27 [get_ports {nc3}]
# set_property PACKAGE_PIN P22 [get_ports {nc4}]
# set_property PACKAGE_PIN Y19 [get_ports {nc5}]
# set_property PACKAGE_PIN Y18 [get_ports {nc6}]
# set_property PACKAGE_PIN AB19 [get_ports {nc7}]

#################################
# FMCA Pins
#################################

#############
# FMCA Data line clocks
#############

# set_property IOSTANDARD LVDS_25 [get_ports {fmca_clk*_m2c_*}]
# set_property PACKAGE_PIN T26 [get_ports {fmca_clk0_m2c_n}]
# set_property PACKAGE_PIN T25 [get_ports {fmca_clk0_m2c_p}]
# set_property PACKAGE_PIN U23 [get_ports {fmca_clk1_m2c_n}]
# set_property PACKAGE_PIN U22 [get_ports {fmca_clk1_m2c_p}]

# The following bidir clocks use AC coupling
# set_property IOSTANDARD LVDS_25 [get_ports {fmca_clk*_bidir_*}]
# set_property PACKAGE_PIN AA26 [get_ports {fmca_clk2_bidir_n}]
# set_property PACKAGE_PIN Y26 [get_ports {fmca_clk2_bidir_p}]
# set_property PACKAGE_PIN AE16 [get_ports {fmca_clk3_bidir_n}]
# set_property PACKAGE_PIN AE15 [get_ports {fmca_clk3_bidir_p}]

################
# FMCA Data lines
################

# Select IO standard based on specific FMC
# set_property IOSTANDARD LVDS_25 [get_ports {fmca_ha* fmca_hb* fmca_la*}]
# set_property IOSTANDARD LVCMOS25 [get_ports {fmca_ha* fmca_hb* fmca_la*}]

# set_property PACKAGE_PIN AG23 [get_ports {fmca_ha00_n_cc}]
# set_property PACKAGE_PIN AG22 [get_ports {fmca_ha00_p_cc}]
# set_property PACKAGE_PIN AF23 [get_ports {fmca_ha01_n_cc}]
# set_property PACKAGE_PIN AF22 [get_ports {fmca_ha01_p_cc}]
# set_property PACKAGE_PIN AE23 [get_ports {fmca_ha02_n}]
# set_property PACKAGE_PIN AD23 [get_ports {fmca_ha02_p}]
# set_property PACKAGE_PIN AB23 [get_ports {fmca_ha03_n}]
# set_property PACKAGE_PIN AB22 [get_ports {fmca_ha03_p}]
# set_property PACKAGE_PIN AG20 [get_ports {fmca_ha04_n}]
# set_property PACKAGE_PIN AF20 [get_ports {fmca_ha04_p}]
# set_property PACKAGE_PIN Y21 [get_ports {fmca_ha05_n}]
# set_property PACKAGE_PIN Y20 [get_ports {fmca_ha05_p}]
# set_property PACKAGE_PIN AA21 [get_ports {fmca_ha06_n}]
# set_property PACKAGE_PIN AA20 [get_ports {fmca_ha06_p}]
# set_property PACKAGE_PIN AE24 [get_ports {fmca_ha07_n}]
# set_property PACKAGE_PIN AD24 [get_ports {fmca_ha07_p}]
# set_property PACKAGE_PIN AA23 [get_ports {fmca_ha08_n}]
# set_property PACKAGE_PIN AA22 [get_ports {fmca_ha08_p}]
# set_property PACKAGE_PIN AH22 [get_ports {fmca_ha09_n}]
# set_property PACKAGE_PIN AH21 [get_ports {fmca_ha09_p}]
# set_property PACKAGE_PIN AJ24 [get_ports {fmca_ha10_n}]
# set_property PACKAGE_PIN AJ23 [get_ports {fmca_ha10_p}]
# set_property PACKAGE_PIN AK21 [get_ports {fmca_ha11_n}]
# set_property PACKAGE_PIN AJ21 [get_ports {fmca_ha11_p}]
# set_property PACKAGE_PIN AH26 [get_ports {fmca_ha12_n}]
# set_property PACKAGE_PIN AH25 [get_ports {fmca_ha12_p}]
# set_property PACKAGE_PIN AC20 [get_ports {fmca_ha13_n}]
# set_property PACKAGE_PIN AB20 [get_ports {fmca_ha13_p}]
# set_property PACKAGE_PIN AE26 [get_ports {fmca_ha14_n}]
# set_property PACKAGE_PIN AD26 [get_ports {fmca_ha14_p}]
# set_property PACKAGE_PIN AF26 [get_ports {fmca_ha15_n}]
# set_property PACKAGE_PIN AE25 [get_ports {fmca_ha15_p}]
# set_property PACKAGE_PIN AC22 [get_ports {fmca_ha16_n}]
# set_property PACKAGE_PIN AC21 [get_ports {fmca_ha16_p}]
# set_property PACKAGE_PIN AH24 [get_ports {fmca_ha17_n_cc}]
# set_property PACKAGE_PIN AG24 [get_ports {fmca_ha17_p_cc}]
# set_property PACKAGE_PIN AG25 [get_ports {fmca_ha18_n_cc}]
# set_property PACKAGE_PIN AF25 [get_ports {fmca_ha18_p_cc}]
# set_property PACKAGE_PIN AD22 [get_ports {fmca_ha19_n}]
# set_property PACKAGE_PIN AD21 [get_ports {fmca_ha19_p}]
# set_property PACKAGE_PIN AK26 [get_ports {fmca_ha20_n}]
# set_property PACKAGE_PIN AJ26 [get_ports {fmca_ha20_p}]
# set_property PACKAGE_PIN AK23 [get_ports {fmca_ha21_n}]
# set_property PACKAGE_PIN AJ22 [get_ports {fmca_ha21_p}]
# set_property PACKAGE_PIN AK25 [get_ports {fmca_ha22_n}]
# set_property PACKAGE_PIN AK24 [get_ports {fmca_ha22_p}]
# set_property PACKAGE_PIN AF21 [get_ports {fmca_ha23_n}]
# set_property PACKAGE_PIN AE21 [get_ports {fmca_ha23_p}]
# set_property PACKAGE_PIN AF16 [get_ports {fmca_hb00_n_cc}]
# set_property PACKAGE_PIN AF15 [get_ports {fmca_hb00_p_cc}]
# set_property PACKAGE_PIN AD19 [get_ports {fmca_hb01_n}]
# set_property PACKAGE_PIN AD18 [get_ports {fmca_hb01_p}]
# set_property PACKAGE_PIN AH20 [get_ports {fmca_hb02_n}]
# set_property PACKAGE_PIN AG19 [get_ports {fmca_hb02_p}]
# set_property PACKAGE_PIN AK20 [get_ports {fmca_hb03_n}]
# set_property PACKAGE_PIN AK19 [get_ports {fmca_hb03_p}]
# set_property PACKAGE_PIN AK18 [get_ports {fmca_hb04_n}]
# set_property PACKAGE_PIN AJ18 [get_ports {fmca_hb04_p}]
# set_property PACKAGE_PIN AG15 [get_ports {fmca_hb05_n}]
# set_property PACKAGE_PIN AG14 [get_ports {fmca_hb05_p}]
# set_property PACKAGE_PIN AH17 [get_ports {fmca_hb06_n_cc}]
# set_property PACKAGE_PIN AH16 [get_ports {fmca_hb06_p_cc}]
# set_property PACKAGE_PIN AH15 [get_ports {fmca_hb07_n}]
# set_property PACKAGE_PIN AH14 [get_ports {fmca_hb07_p}]
# set_property PACKAGE_PIN AJ17 [get_ports {fmca_hb08_n}]
# set_property PACKAGE_PIN AJ16 [get_ports {fmca_hb08_p}]
# set_property PACKAGE_PIN AE19 [get_ports {fmca_hb09_n}]
# set_property PACKAGE_PIN AE18 [get_ports {fmca_hb09_p}]
# set_property PACKAGE_PIN AK14 [get_ports {fmca_hb10_n}]
# set_property PACKAGE_PIN AJ14 [get_ports {fmca_hb10_p}]
# set_property PACKAGE_PIN AK16 [get_ports {fmca_hb11_n}]
# set_property PACKAGE_PIN AK15 [get_ports {fmca_hb11_p}]
# set_property PACKAGE_PIN AG18 [get_ports {fmca_hb12_n}]
# set_property PACKAGE_PIN AF18 [get_ports {fmca_hb12_p}]
# set_property PACKAGE_PIN AJ19 [get_ports {fmca_hb13_n}]
# set_property PACKAGE_PIN AH19 [get_ports {fmca_hb13_p}]
# set_property PACKAGE_PIN AB18 [get_ports {fmca_hb14_n}]
# set_property PACKAGE_PIN AB17 [get_ports {fmca_hb14_p}]
# set_property PACKAGE_PIN AE14 [get_ports {fmca_hb15_n}]
# set_property PACKAGE_PIN AD14 [get_ports {fmca_hb15_p}]
# set_property PACKAGE_PIN AA18 [get_ports {fmca_hb16_n}]
# set_property PACKAGE_PIN AA17 [get_ports {fmca_hb16_p}]
# set_property PACKAGE_PIN AG17 [get_ports {fmca_hb17_n_cc}]
# set_property PACKAGE_PIN AF17 [get_ports {fmca_hb17_p_cc}]
# set_property PACKAGE_PIN AD16 [get_ports {fmca_hb18_n}]
# set_property PACKAGE_PIN AC16 [get_ports {fmca_hb18_p}]
# set_property PACKAGE_PIN AD17 [get_ports {fmca_hb19_n}]
# set_property PACKAGE_PIN AC17 [get_ports {fmca_hb19_p}]
# set_property PACKAGE_PIN AB15 [get_ports {fmca_hb20_n}]
# set_property PACKAGE_PIN AB14 [get_ports {fmca_hb20_p}]
# set_property PACKAGE_PIN AC15 [get_ports {fmca_hb21_n}]
# set_property PACKAGE_PIN AC14 [get_ports {fmca_hb21_p}]
# set_property PACKAGE_PIN U25 [get_ports {fmca_la00_n_cc}]
# set_property PACKAGE_PIN U24 [get_ports {fmca_la00_p_cc}]
# set_property PACKAGE_PIN V22 [get_ports {fmca_la01_n_cc}]
# set_property PACKAGE_PIN V21 [get_ports {fmca_la01_p_cc}]
# set_property PACKAGE_PIN T18 [get_ports {fmca_la02_n}]
# set_property PACKAGE_PIN T17 [get_ports {fmca_la02_p}]
# set_property PACKAGE_PIN R25 [get_ports {fmca_la03_n}]
# set_property PACKAGE_PIN R24 [get_ports {fmca_la03_p}]
# set_property PACKAGE_PIN T28 [get_ports {fmca_la04_n}]
# set_property PACKAGE_PIN R28 [get_ports {fmca_la04_p}]
# set_property PACKAGE_PIN V19 [get_ports {fmca_la05_n}]
# set_property PACKAGE_PIN U19 [get_ports {fmca_la05_p}]
# set_property PACKAGE_PIN T27 [get_ports {fmca_la06_n}]
# set_property PACKAGE_PIN R26 [get_ports {fmca_la06_p}]
# set_property PACKAGE_PIN T21 [get_ports {fmca_la07_n}]
# set_property PACKAGE_PIN T20 [get_ports {fmca_la07_p}]
# set_property PACKAGE_PIN T23 [get_ports {fmca_la08_n}]
# set_property PACKAGE_PIN R23 [get_ports {fmca_la08_p}]
# set_property PACKAGE_PIN W19 [get_ports {fmca_la09_n}]
# set_property PACKAGE_PIN W18 [get_ports {fmca_la09_p}]
# set_property PACKAGE_PIN W17 [get_ports {fmca_la10_n}]
# set_property PACKAGE_PIN V17 [get_ports {fmca_la10_p}]
# set_property PACKAGE_PIN V20 [get_ports {fmca_la11_n}]
# set_property PACKAGE_PIN U20 [get_ports {fmca_la11_p}]
# set_property PACKAGE_PIN U28 [get_ports {fmca_la12_n}]
# set_property PACKAGE_PIN U27 [get_ports {fmca_la12_p}]
# set_property PACKAGE_PIN U30 [get_ports {fmca_la13_n}]
# set_property PACKAGE_PIN U29 [get_ports {fmca_la13_p}]
# set_property PACKAGE_PIN V25 [get_ports {fmca_la14_n}]
# set_property PACKAGE_PIN V24 [get_ports {fmca_la14_p}]
# set_property PACKAGE_PIN W23 [get_ports {fmca_la15_n}]
# set_property PACKAGE_PIN W22 [get_ports {fmca_la15_p}]
# set_property PACKAGE_PIN U18 [get_ports {fmca_la16_n}]
# set_property PACKAGE_PIN U17 [get_ports {fmca_la16_p}]
# set_property PACKAGE_PIN AB27 [get_ports {fmca_la17_n_cc}]
# set_property PACKAGE_PIN AA27 [get_ports {fmca_la17_p_cc}]
# set_property PACKAGE_PIN AD28 [get_ports {fmca_la18_n_cc}]
# set_property PACKAGE_PIN AC27 [get_ports {fmca_la18_p_cc}]
# set_property PACKAGE_PIN Y29 [get_ports {fmca_la19_n}]
# set_property PACKAGE_PIN Y28 [get_ports {fmca_la19_p}]
# set_property PACKAGE_PIN W29 [get_ports {fmca_la20_n}]
# set_property PACKAGE_PIN W28 [get_ports {fmca_la20_p}]
# set_property PACKAGE_PIN AB30 [get_ports {fmca_la21_n}]
# set_property PACKAGE_PIN AB29 [get_ports {fmca_la21_p}]
# set_property PACKAGE_PIN AB28 [get_ports {fmca_la22_n}]
# set_property PACKAGE_PIN AA28 [get_ports {fmca_la22_p}]
# set_property PACKAGE_PIN AA30 [get_ports {fmca_la23_n}]
# set_property PACKAGE_PIN Y30 [get_ports {fmca_la23_p}]
# set_property PACKAGE_PIN AG28 [get_ports {fmca_la24_n}]
# set_property PACKAGE_PIN AF27 [get_ports {fmca_la24_p}]
# set_property PACKAGE_PIN AF30 [get_ports {fmca_la25_n}]
# set_property PACKAGE_PIN AE30 [get_ports {fmca_la25_p}]
# set_property PACKAGE_PIN AC30 [get_ports {fmca_la26_n}]
# set_property PACKAGE_PIN AC29 [get_ports {fmca_la26_p}]
# set_property PACKAGE_PIN AE29 [get_ports {fmca_la27_n}]
# set_property PACKAGE_PIN AD29 [get_ports {fmca_la27_p}]
# set_property PACKAGE_PIN AJ28 [get_ports {fmca_la28_n}]
# set_property PACKAGE_PIN AJ27 [get_ports {fmca_la28_p}]
# set_property PACKAGE_PIN AH29 [get_ports {fmca_la29_n}]
# set_property PACKAGE_PIN AG29 [get_ports {fmca_la29_p}]
# set_property PACKAGE_PIN AC25 [get_ports {fmca_la30_n}]
# set_property PACKAGE_PIN AB25 [get_ports {fmca_la30_p}]
# set_property PACKAGE_PIN AD27 [get_ports {fmca_la31_n}]
# set_property PACKAGE_PIN AC26 [get_ports {fmca_la31_p}]
# set_property PACKAGE_PIN AA25 [get_ports {fmca_la32_n}]
# set_property PACKAGE_PIN Y25 [get_ports {fmca_la32_p}]
# set_property PACKAGE_PIN AC24 [get_ports {fmca_la33_n}]
# set_property PACKAGE_PIN AB24 [get_ports {fmca_la33_p}]

#############
# FMCA Gigabit differential pairs
#############

# The following differential pairs are connected to the FPGA GTX
# only if the passive resistor network switch is configured appropriately
# set_property PACKAGE_PIN AG7 [get_ports {fmca_dp0_c2m_n}]
# set_property PACKAGE_PIN AG8 [get_ports {fmca_dp0_c2m_p}]
# set_property PACKAGE_PIN AE11 [get_ports {fmca_dp0_m2c_n}]
# set_property PACKAGE_PIN AE12 [get_ports {fmca_dp0_m2c_p}]
# set_property PACKAGE_PIN AJ7 [get_ports {fmca_dp1_c2m_n}]
# set_property PACKAGE_PIN AJ8 [get_ports {fmca_dp1_c2m_p}]
# set_property PACKAGE_PIN AF9 [get_ports {fmca_dp1_m2c_n}]
# set_property PACKAGE_PIN AF10 [get_ports {fmca_dp1_m2c_p}]
# set_property PACKAGE_PIN AK9 [get_ports {fmca_dp2_c2m_n}]
# set_property PACKAGE_PIN AK10 [get_ports {fmca_dp2_c2m_p}]
# set_property PACKAGE_PIN AG11 [get_ports {fmca_dp2_m2c_n}]
# set_property PACKAGE_PIN AG12 [get_ports {fmca_dp2_m2c_p}]
# set_property PACKAGE_PIN AJ11 [get_ports {fmca_dp3_c2m_n}]
# set_property PACKAGE_PIN AJ12 [get_ports {fmca_dp3_c2m_p}]
# set_property PACKAGE_PIN AH9 [get_ports {fmca_dp3_m2c_n}]
# set_property PACKAGE_PIN AH10 [get_ports {fmca_dp3_m2c_p}]
# set_property PACKAGE_PIN AH1 [get_ports {fmca_dp4_c2m_n}]
# set_property PACKAGE_PIN AH2 [get_ports {fmca_dp4_c2m_p}]
# set_property PACKAGE_PIN AC3 [get_ports {fmca_dp4_m2c_n}]
# set_property PACKAGE_PIN AC4 [get_ports {fmca_dp4_m2c_p}]
# set_property PACKAGE_PIN AK1 [get_ports {fmca_dp5_c2m_n}]
# set_property PACKAGE_PIN AK2 [get_ports {fmca_dp5_c2m_p}]
# set_property PACKAGE_PIN AE3 [get_ports {fmca_dp5_m2c_n}]
# set_property PACKAGE_PIN AE4 [get_ports {fmca_dp5_m2c_p}]
# set_property PACKAGE_PIN AJ3 [get_ports {fmca_dp6_c2m_n}]
# set_property PACKAGE_PIN AJ4 [get_ports {fmca_dp6_c2m_p}]
# set_property PACKAGE_PIN AG3 [get_ports {fmca_dp6_m2c_n}]
# set_property PACKAGE_PIN AG4 [get_ports {fmca_dp6_m2c_p}]
# set_property PACKAGE_PIN AK5 [get_ports {fmca_dp7_c2m_n}]
# set_property PACKAGE_PIN AK6 [get_ports {fmca_dp7_c2m_p}]
# set_property PACKAGE_PIN AH5 [get_ports {fmca_dp7_m2c_n}]
# set_property PACKAGE_PIN AH6 [get_ports {fmca_dp7_m2c_p}]

# DP8_C2M_N and DP8_C2M_P receive 10 MHz clock copied directly from the
# motherboard reference input, without going through the PLL
# Other DP8 and all DP9 are not connected

#############
# FMC Gigabit Reference Clocks
#############

# set_property PACKAGE_PIN AC7 [get_ports {fmca_gbtclk0_m2c_n}]
# set_property PACKAGE_PIN AC8 [get_ports {fmca_gbtclk0_m2c_p}]
# set_property PACKAGE_PIN AE7 [get_ports {fmca_gbtclk1_m2c_n}]
# set_property PACKAGE_PIN AE8 [get_ports {fmca_gbtclk1_m2c_p}]

#################################
# FMCB Pins
#################################

#############
# FMCB Data line clocks
#############

# set_property IOSTANDARD LVDS_25 [get_ports {fmcb_clk*_m2c_*}]
# set_property PACKAGE_PIN F26 [get_ports {fmcb_clk0_m2c_n}]
# set_property PACKAGE_PIN F25 [get_ports {fmcb_clk0_m2c_p}]
# set_property PACKAGE_PIN F28 [get_ports {fmcb_clk1_m2c_n}]
# set_property PACKAGE_PIN G28 [get_ports {fmcb_clk1_m2c_p}]

# The following bidir clocks use AC coupling
# set_property IOSTANDARD LVDS_25 [get_ports {fmcb_clk*_bidir_*}]
# set_property PACKAGE_PIN F22 [get_ports {fmcb_clk2_bidir_n}]
# set_property PACKAGE_PIN G22 [get_ports {fmcb_clk2_bidir_p}]
# set_property PACKAGE_PIN N25 [get_ports {fmcb_clk3_bidir_n}]
# set_property PACKAGE_PIN N24 [get_ports {fmcb_clk3_bidir_p}]

################
# FMCB Data lines
################
# Select IO standard based on specific FMC
# set_property IOSTANDARD LVDS_25 [get_ports {fmcb_ha* fmcb_hb* fmcb_la*}]
# set_property IOSTANDARD LVCMOS25 [get_ports {fmcb_ha* fmcb_hb* fmcb_la*}]

# set_property PACKAGE_PIN C16 [get_ports {fmcb_ha00_n_cc}]
# set_property PACKAGE_PIN C15 [get_ports {fmcb_ha00_p_cc}]
# set_property PACKAGE_PIN F15 [get_ports {fmcb_ha01_n_cc}]
# set_property PACKAGE_PIN G15 [get_ports {fmcb_ha01_p_cc}]
# set_property PACKAGE_PIN J17 [get_ports {fmcb_ha02_n}]
# set_property PACKAGE_PIN J16 [get_ports {fmcb_ha02_p}]
# set_property PACKAGE_PIN H15 [get_ports {fmcb_ha03_n}]
# set_property PACKAGE_PIN J14 [get_ports {fmcb_ha03_p}]
# set_property PACKAGE_PIN H17 [get_ports {fmcb_ha04_n}]
# set_property PACKAGE_PIN H16 [get_ports {fmcb_ha04_p}]
# set_property PACKAGE_PIN G14 [get_ports {fmcb_ha05_n}]
# set_property PACKAGE_PIN H14 [get_ports {fmcb_ha05_p}]
# set_property PACKAGE_PIN F17 [get_ports {fmcb_ha06_n}]
# set_property PACKAGE_PIN G17 [get_ports {fmcb_ha06_p}]
# set_property PACKAGE_PIN A17 [get_ports {fmcb_ha07_n}]
# set_property PACKAGE_PIN B17 [get_ports {fmcb_ha07_p}]
# set_property PACKAGE_PIN H22 [get_ports {fmcb_ha08_n}]
# set_property PACKAGE_PIN J22 [get_ports {fmcb_ha08_p}]
# set_property PACKAGE_PIN J23 [get_ports {fmcb_ha09_n}]
# set_property PACKAGE_PIN K23 [get_ports {fmcb_ha09_p}]
# set_property PACKAGE_PIN F23 [get_ports {fmcb_ha10_n}]
# set_property PACKAGE_PIN G23 [get_ports {fmcb_ha10_p}]
# set_property PACKAGE_PIN K20 [get_ports {fmcb_ha11_n}]
# set_property PACKAGE_PIN K19 [get_ports {fmcb_ha11_p}]
# set_property PACKAGE_PIN J19 [get_ports {fmcb_ha12_n}]
# set_property PACKAGE_PIN J18 [get_ports {fmcb_ha12_p}]
# set_property PACKAGE_PIN K18 [get_ports {fmcb_ha13_n}]
# set_property PACKAGE_PIN L18 [get_ports {fmcb_ha13_p}]
# set_property PACKAGE_PIN J21 [get_ports {fmcb_ha14_n}]
# set_property PACKAGE_PIN K21 [get_ports {fmcb_ha14_p}]
# set_property PACKAGE_PIN G20 [get_ports {fmcb_ha15_n}]
# set_property PACKAGE_PIN H20 [get_ports {fmcb_ha15_p}]
# set_property PACKAGE_PIN G19 [get_ports {fmcb_ha16_n}]
# set_property PACKAGE_PIN H19 [get_ports {fmcb_ha16_p}]
# set_property PACKAGE_PIN E16 [get_ports {fmcb_ha17_n_cc}]
# set_property PACKAGE_PIN F16 [get_ports {fmcb_ha17_p_cc}]
# set_property PACKAGE_PIN D16 [get_ports {fmcb_ha18_n_cc}]
# set_property PACKAGE_PIN E15 [get_ports {fmcb_ha18_p_cc}]
# set_property PACKAGE_PIN A16 [get_ports {fmcb_ha19_n}]
# set_property PACKAGE_PIN A15 [get_ports {fmcb_ha19_p}]
# set_property PACKAGE_PIN C17 [get_ports {fmcb_ha20_n}]
# set_property PACKAGE_PIN D17 [get_ports {fmcb_ha20_p}]
# set_property PACKAGE_PIN A14 [get_ports {fmcb_ha21_n}]
# set_property PACKAGE_PIN B14 [get_ports {fmcb_ha21_p}]
# set_property PACKAGE_PIN B15 [get_ports {fmcb_ha22_n}]
# set_property PACKAGE_PIN C14 [get_ports {fmcb_ha22_p}]
# set_property PACKAGE_PIN D14 [get_ports {fmcb_ha23_n}]
# set_property PACKAGE_PIN E14 [get_ports {fmcb_ha23_p}]
# set_property PACKAGE_PIN L27 [get_ports {fmcb_hb00_n_cc}]
# set_property PACKAGE_PIN L26 [get_ports {fmcb_hb00_p_cc}]
# set_property PACKAGE_PIN K29 [get_ports {fmcb_hb01_n}]
# set_property PACKAGE_PIN K28 [get_ports {fmcb_hb01_p}]
# set_property PACKAGE_PIN K30 [get_ports {fmcb_hb02_n}]
# set_property PACKAGE_PIN L30 [get_ports {fmcb_hb02_p}]
# set_property PACKAGE_PIN M30 [get_ports {fmcb_hb03_n}]
# set_property PACKAGE_PIN N30 [get_ports {fmcb_hb03_p}]
# set_property PACKAGE_PIN M29 [get_ports {fmcb_hb04_n}]
# set_property PACKAGE_PIN N29 [get_ports {fmcb_hb04_p}]
# set_property PACKAGE_PIN P29 [get_ports {fmcb_hb05_n}]
# set_property PACKAGE_PIN R29 [get_ports {fmcb_hb05_p}]
# set_property PACKAGE_PIN L25 [get_ports {fmcb_hb06_n_cc}]
# set_property PACKAGE_PIN M25 [get_ports {fmcb_hb06_p_cc}]
# set_property PACKAGE_PIN K26 [get_ports {fmcb_hb07_n}]
# set_property PACKAGE_PIN K25 [get_ports {fmcb_hb07_p}]
# set_property PACKAGE_PIN N26 [get_ports {fmcb_hb08_n}]
# set_property PACKAGE_PIN P26 [get_ports {fmcb_hb08_p}]
# set_property PACKAGE_PIN L28 [get_ports {fmcb_hb09_n}]
# set_property PACKAGE_PIN M28 [get_ports {fmcb_hb09_p}]
# set_property PACKAGE_PIN P28 [get_ports {fmcb_hb10_n}]
# set_property PACKAGE_PIN P27 [get_ports {fmcb_hb10_p}]
# set_property PACKAGE_PIN P24 [get_ports {fmcb_hb11_n}]
# set_property PACKAGE_PIN P23 [get_ports {fmcb_hb11_p}]
# set_property PACKAGE_PIN N19 [get_ports {fmcb_hb12_n}]
# set_property PACKAGE_PIN P19 [get_ports {fmcb_hb12_p}]
# set_property PACKAGE_PIN K24 [get_ports {fmcb_hb13_n}]
# set_property PACKAGE_PIN L23 [get_ports {fmcb_hb13_p}]
# set_property PACKAGE_PIN P18 [get_ports {fmcb_hb14_n}]
# set_property PACKAGE_PIN P17 [get_ports {fmcb_hb14_p}]
# set_property PACKAGE_PIN L21 [get_ports {fmcb_hb15_n}]
# set_property PACKAGE_PIN L20 [get_ports {fmcb_hb15_p}]
# set_property PACKAGE_PIN M20 [get_ports {fmcb_hb16_n}]
# set_property PACKAGE_PIN N20 [get_ports {fmcb_hb16_p}]
# set_property PACKAGE_PIN M24 [get_ports {fmcb_hb17_n_cc}]
# set_property PACKAGE_PIN M23 [get_ports {fmcb_hb17_p_cc}]
# set_property PACKAGE_PIN M17 [get_ports {fmcb_hb18_n}]
# set_property PACKAGE_PIN N17 [get_ports {fmcb_hb18_p}]
# set_property PACKAGE_PIN M22 [get_ports {fmcb_hb19_n}]
# set_property PACKAGE_PIN N22 [get_ports {fmcb_hb19_p}]
# set_property PACKAGE_PIN N21 [get_ports {fmcb_hb20_n}]
# set_property PACKAGE_PIN P21 [get_ports {fmcb_hb20_p}]
# set_property PACKAGE_PIN M19 [get_ports {fmcb_hb21_n}]
# set_property PACKAGE_PIN M18 [get_ports {fmcb_hb21_p}]
# set_property PACKAGE_PIN E26 [get_ports {fmcb_la00_n_cc}]
# set_property PACKAGE_PIN E25 [get_ports {fmcb_la00_p_cc}]
# set_property PACKAGE_PIN F27 [get_ports {fmcb_la01_n_cc}]
# set_property PACKAGE_PIN G27 [get_ports {fmcb_la01_p_cc}]
# set_property PACKAGE_PIN B25 [get_ports {fmcb_la02_n}]
# set_property PACKAGE_PIN B24 [get_ports {fmcb_la02_p}]
# set_property PACKAGE_PIN D27 [get_ports {fmcb_la03_n}]
# set_property PACKAGE_PIN D26 [get_ports {fmcb_la03_p}]
# set_property PACKAGE_PIN A26 [get_ports {fmcb_la04_n}]
# set_property PACKAGE_PIN A25 [get_ports {fmcb_la04_p}]
# set_property PACKAGE_PIN B27 [get_ports {fmcb_la05_n}]
# set_property PACKAGE_PIN C27 [get_ports {fmcb_la05_p}]
# set_property PACKAGE_PIN C26 [get_ports {fmcb_la06_n}]
# set_property PACKAGE_PIN C25 [get_ports {fmcb_la06_p}]
# set_property PACKAGE_PIN G24 [get_ports {fmcb_la07_n}]
# set_property PACKAGE_PIN H24 [get_ports {fmcb_la07_p}]
# set_property PACKAGE_PIN G25 [get_ports {fmcb_la08_n}]
# set_property PACKAGE_PIN H25 [get_ports {fmcb_la08_p}]
# set_property PACKAGE_PIN J27 [get_ports {fmcb_la09_n}]
# set_property PACKAGE_PIN J26 [get_ports {fmcb_la09_p}]
# set_property PACKAGE_PIN H27 [get_ports {fmcb_la10_n}]
# set_property PACKAGE_PIN H26 [get_ports {fmcb_la10_p}]
# set_property PACKAGE_PIN C24 [get_ports {fmcb_la11_n}]
# set_property PACKAGE_PIN D24 [get_ports {fmcb_la11_p}]
# set_property PACKAGE_PIN G30 [get_ports {fmcb_la12_n}]
# set_property PACKAGE_PIN H30 [get_ports {fmcb_la12_p}]
# set_property PACKAGE_PIN J29 [get_ports {fmcb_la13_n}]
# set_property PACKAGE_PIN J28 [get_ports {fmcb_la13_p}]
# set_property PACKAGE_PIN D28 [get_ports {fmcb_la14_n}]
# set_property PACKAGE_PIN E28 [get_ports {fmcb_la14_p}]
# set_property PACKAGE_PIN G29 [get_ports {fmcb_la15_n}]
# set_property PACKAGE_PIN H29 [get_ports {fmcb_la15_p}]
# set_property PACKAGE_PIN E30 [get_ports {fmcb_la16_n}]
# set_property PACKAGE_PIN F30 [get_ports {fmcb_la16_p}]
# set_property PACKAGE_PIN F21 [get_ports {fmcb_la17_n_cc}]
# set_property PACKAGE_PIN F20 [get_ports {fmcb_la17_p_cc}]
# set_property PACKAGE_PIN E21 [get_ports {fmcb_la18_n_cc}]
# set_property PACKAGE_PIN E20 [get_ports {fmcb_la18_p_cc}]
# set_property PACKAGE_PIN C20 [get_ports {fmcb_la19_n}]
# set_property PACKAGE_PIN C19 [get_ports {fmcb_la19_p}]
# set_property PACKAGE_PIN D23 [get_ports {fmcb_la20_n}]
# set_property PACKAGE_PIN E23 [get_ports {fmcb_la20_p}]
# set_property PACKAGE_PIN A21 [get_ports {fmcb_la21_n}]
# set_property PACKAGE_PIN A20 [get_ports {fmcb_la21_p}]
# set_property PACKAGE_PIN C22 [get_ports {fmcb_la22_n}]
# set_property PACKAGE_PIN C21 [get_ports {fmcb_la22_p}]
# set_property PACKAGE_PIN B23 [get_ports {fmcb_la23_n}]
# set_property PACKAGE_PIN B22 [get_ports {fmcb_la23_p}]
# set_property PACKAGE_PIN E19 [get_ports {fmcb_la24_n}]
# set_property PACKAGE_PIN E18 [get_ports {fmcb_la24_p}]
# set_property PACKAGE_PIN A18 [get_ports {fmcb_la25_n}]
# set_property PACKAGE_PIN B18 [get_ports {fmcb_la25_p}]
# set_property PACKAGE_PIN D19 [get_ports {fmcb_la26_n}]
# set_property PACKAGE_PIN D18 [get_ports {fmcb_la26_p}]
# set_property PACKAGE_PIN B20 [get_ports {fmcb_la27_n}]
# set_property PACKAGE_PIN B19 [get_ports {fmcb_la27_p}]
# set_property PACKAGE_PIN F18 [get_ports {fmcb_la28_n}]
# set_property PACKAGE_PIN G18 [get_ports {fmcb_la28_p}]
# set_property PACKAGE_PIN C30 [get_ports {fmcb_la29_n}]
# set_property PACKAGE_PIN C29 [get_ports {fmcb_la29_p}]
# set_property PACKAGE_PIN D29 [get_ports {fmcb_la30_n}]
# set_property PACKAGE_PIN E29 [get_ports {fmcb_la30_p}]
# set_property PACKAGE_PIN B29 [get_ports {fmcb_la31_n}]
# set_property PACKAGE_PIN B28 [get_ports {fmcb_la31_p}]
# set_property PACKAGE_PIN A30 [get_ports {fmcb_la32_n}]
# set_property PACKAGE_PIN B30 [get_ports {fmcb_la32_p}]
# set_property PACKAGE_PIN A28 [get_ports {fmcb_la33_n}]
# set_property PACKAGE_PIN A27 [get_ports {fmcb_la33_p}]

#############
# FMCB Gigabit differential pairs
#############

# The following differential pairs are connected to the FPGA GTX
# only if the passive resistor network switch is configured appropriately
# set_property PACKAGE_PIN Y1 [get_ports {fmcb_dp0_c2m_n}]
# set_property PACKAGE_PIN Y2 [get_ports {fmcb_dp0_c2m_p}]
# set_property PACKAGE_PIN W3 [get_ports {fmcb_dp0_m2c_n}]
# set_property PACKAGE_PIN W4 [get_ports {fmcb_dp0_m2c_p}]
# set_property PACKAGE_PIN AB1 [get_ports {fmcb_dp1_c2m_n}]
# set_property PACKAGE_PIN AB2 [get_ports {fmcb_dp1_c2m_p}]
# set_property PACKAGE_PIN Y5 [get_ports {fmcb_dp1_m2c_n}]
# set_property PACKAGE_PIN Y6 [get_ports {fmcb_dp1_m2c_p}]
# set_property PACKAGE_PIN AD1 [get_ports {fmcb_dp2_c2m_n}]
# set_property PACKAGE_PIN AD2 [get_ports {fmcb_dp2_c2m_p}]
# set_property PACKAGE_PIN AA3 [get_ports {fmcb_dp2_m2c_n}]
# set_property PACKAGE_PIN AA4 [get_ports {fmcb_dp2_m2c_p}]
# set_property PACKAGE_PIN AF1 [get_ports {fmcb_dp3_c2m_n}]
# set_property PACKAGE_PIN AF2 [get_ports {fmcb_dp3_c2m_p}]
# set_property PACKAGE_PIN AB5 [get_ports {fmcb_dp3_m2c_n}]
# set_property PACKAGE_PIN AB6 [get_ports {fmcb_dp3_m2c_p}]
# set_property PACKAGE_PIN N3 [get_ports {fmcb_dp4_c2m_n}]
# set_property PACKAGE_PIN N4 [get_ports {fmcb_dp4_c2m_p}]
# set_property PACKAGE_PIN P5 [get_ports {fmcb_dp4_m2c_n}]
# set_property PACKAGE_PIN P6 [get_ports {fmcb_dp4_m2c_p}]
# set_property PACKAGE_PIN P1 [get_ports {fmcb_dp5_c2m_n}]
# set_property PACKAGE_PIN P2 [get_ports {fmcb_dp5_c2m_p}]
# set_property PACKAGE_PIN R3 [get_ports {fmcb_dp5_m2c_n}]
# set_property PACKAGE_PIN R4 [get_ports {fmcb_dp5_m2c_p}]
# set_property PACKAGE_PIN T1 [get_ports {fmcb_dp6_c2m_n}]
# set_property PACKAGE_PIN T2 [get_ports {fmcb_dp6_c2m_p}]
# set_property PACKAGE_PIN U3 [get_ports {fmcb_dp6_m2c_n}]
# set_property PACKAGE_PIN U4 [get_ports {fmcb_dp6_m2c_p}]
# set_property PACKAGE_PIN V1 [get_ports {fmcb_dp7_c2m_n}]
# set_property PACKAGE_PIN V2 [get_ports {fmcb_dp7_c2m_p}]
# set_property PACKAGE_PIN V5 [get_ports {fmcb_dp7_m2c_n}]
# set_property PACKAGE_PIN V6 [get_ports {fmcb_dp7_m2c_p}]

# DP8_C2M_N and DP8_C2M_P receive 10 MHz clock copied directly from the
# motherboard reference input, without going through the PLL
# Other DP8 and all DP9 are not connected

#############
# FMCB Gigabit Reference Clocks
#############

# set_property PACKAGE_PIN U7 [get_ports {fmcb_gbtclk0_m2c_n}]
# set_property PACKAGE_PIN U8 [get_ports {fmcb_gbtclk0_m2c_p}]
# set_property PACKAGE_PIN W7 [get_ports {fmcb_gbtclk1_m2c_n}]
# set_property PACKAGE_PIN W8 [get_ports {fmcb_gbtclk1_m2c_p}]

