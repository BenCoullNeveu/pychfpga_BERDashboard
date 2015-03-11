Introduction
============

This document provides a high-level introduction to firmware running on the
board. For specific information on building each of these components, refer
to the Table of Contents at :doc:`/index`.

.. figure:: ../images/banner.jpg
   :align:  center

.. contents:: Table of Contents
   :local:

Components
----------

"Firmware" refers to the following components:

**First-Stage Bootloader** (`MLO`)
   Early bootloader (a minimal version of u-boot), required to initialize
   hardware before loading the second-stage bootloader.

   * Git repository: https://bitbucket.org/winterlandcosmology/iceboard-uboot
   * Documentation: :doc:`bootloader`.

**Second-Stage Bootloader** (`u-boot.bin`)
   A more fully-featured bootloader, capable of loading and booting Linux (as
   well as network booting and other more complex functions.) The second-stage
   bootloader is distributed as `u-boot.bin`.

   * Git repository: https://bitbucket.org/winterlandcosmology/iceboard-uboot
   * Documentation: :doc:`bootloader`.

**Linux Kernel** (`uImage`)
   The IceBoard runs TI's 2.6.37 branch of the Linux kernel. As of February
   2015, it looks like an upgrade to modern kernels (v3.20 or later) will be
   feasible.

   * Git repository: https://bitbucket.org/winterlandcosmology/iceboard-linux
   * Documentation: :doc:`kernel`.

**Root Filesystem** (`rootfs.tar.bz2`)
   The root filesystem contains a stripped-down Linux distribution with a
   minimal set of generic tools (SSH server, shell, et cetera.) On the flash
   card, the root filesystem occupies a separate EXT2 partition from the above
   components.

   * Git repository: https://bitbucket.org/winterlandcosmology/iceboard-buildroot
   * Documentation: :doc:`rootfs`.

**Application Stack**
   The application stack consists of both IceBoard- and experiment-specific
   components, including hardware support libraries, and the board's web
   interface. These components are distributed as `.opk` files, and are
   installed into the flash card's EXT2 partition.

   * Git repository: https://bitbucket.org/winterlandcosmology/icecore
   * Documentation: :doc:`app_server`.

**FPGA Bitstream**
   Although the FPGA bitstream is properly "gateware" or "RTL" (not
   "firmware", a term which is usually reserved for a specific class of
   software), it is lab convention to lump bitstreams in with other firmware.
   For DFMUX (but not currently for CHIME), the compiled FPGA bitstream is
   distributed as an `.opk`, and is also installed into the flash card's EXT2
   partition.

System Diagrams
---------------

In the following sections, we provide a graphical model for parts of the
system.

Boot-Up
~~~~~~~

:ref:`BootDiagram` shows the boot process.

.. _BootDiagram:
.. figure:: images/boot_diagram.svg
   :align: center

   IceBoard Boot-Up

On power-up, the ARM core begins executing code from its built-in boot ROM. If
it finds a MMC/SD card containing the file "`MLO`", it loads and executes this
program.

Control is then passed to the second-stage bootloader. After a 3s delay, the
second-stage bootloader loads a boot script (`boot.scr`) from the MMC/SD card
and executes it. This script loads and boots Linux from the `uImage` file.

Userspace
~~~~~~~~~

After Linux boots, control is passed to userspace code in the MMC/SD card's
EXT2 partition. Userspace is structured as shown in :ref:`UserspaceDiagram`.

.. _UserspaceDiagram:
.. figure:: images/userspace_diagram.svg
   :align: center

   Userspace Overview

All activity (even from on-board Python code) hits the application server as
an HTTP request. Static web content (HTML, JS, CSS, et cetera) is served as
expected. Method calls (with the special URL `/tuber`) provide a
JSON-formatted request and result in a JSON response.

RS-232 Boot Transcript
----------------------

The following sections show a complete RS-232 boot transcript.  You may use
this transcript as a reference to diagnose boot problems. Early stages of the
boot process should be reproducible faithfully; once boot proceeds to the
Linux kernel, you might see deviations from this transcript (due to either
timing, firmware changes, or network conditions) that do not indicate a
problem.

First-Stage Bootloader
~~~~~~~~~~~~~~~~~~~~~~

The first-stage bootloader produces the following output on RS-232::

   U-Boot 2010.06-dirty (May 12 2014 - 13:39:15)

   TI8148-GP rev 2.1

   ARM clk: 600MHz
   DDR clk: 400MHz

   DRAM:  1 GiB
   DCACHE:  Off
   MMC:   OMAP SD/MMC: 0
   Using default environment

   The 2nd stage U-Boot will now be auto-loaded
   Please do not interrupt the countdown till TI8148_EVM prompt if 2nd stage is already flashed
   reading u-boot.bin

   186092 bytes read
   ## Starting application at 0x80800000 ...

Second-Stage Bootloader
~~~~~~~~~~~~~~~~~~~~~~~

The second-stage bootloader takes over and produces the following output::

   U-Boot 2010.06 (Mar 18 2014 - 16:45:35)
   
   TI8148-GP rev 2.1
   
   ARM clk: 600MHz
   DDR clk: 400MHz
   
   I2C:   ready
   DRAM:  1 GiB
   DCACHE:  On
   NAND:  HW ECC BCH8 Selected
   No NAND device found!!!
   0 MiB
   MMC:   OMAP SD/MMC: 0
   *** Warning - bad CRC or MMC, using default environment
   
                             .:;rrr;;.
                       ,5#@@@@#####@@@@@@#2,
                    ,A@@@hi;;;r5;;;;r;rrSG@@@A,
                  r@@#i;:;s222hG;rrsrrrrrr;ri#@@r
                :@@hr:r;SG3ssrr2r;rrsrsrsrsrr;rh@@:
               B@H;;rr;3Hs;rrr;sr;;rrsrsrsrsrsr;;H@B
              @@s:rrs;5#;;rrrr;r#@H:;;rrsrsrsrsrr:s@@
             @@;;srs&X#9;r;r;;,2@@@rrr:;;rrsrsrsrr;;@@
            @@;;rrsrrs@MB#@@@@@###@@@@@@#rsrsrsrsrr;;@@
           G@r;rrsrsr;#X;SX25Ss#@@#M@#9H9rrsrsrsrsrs;r@G
           @9:srsrsrs;2@;:;;:.X@@@@@H::;rrsrsrsrsrsrr:3@
          X@;rrsrsrsrr;XAi;;:&@@#@Bs:rrsrsrsrsrsrsrsrr;@X
          @#;rsrsrsrsrr;r2ir@@@###::rrsrsrsrsrsrsrsrsr:@@
          @A:rrsrsrsrr;:2@29@@M@@@;:;rrrrsrsrsrsrsrsrs;H@
          @&;rsrsrsrr;A@@@@@@###@@@s::;:;;rrsrsrsrsrsr;G@
          @#:rrsrsrsr;G@5Hr25@@@#@@@#9XG9s:rrrrsrsrsrs:#@
          M@;rsrsrsrs;r@&#;::S@@@@@@@M@@@@Grr:;rsrsrsr;@#
          :@s;rsrsrsrr:M#Msrr;;&#@@@@@@@@@@H@@5;rsrsr;s@,
           @@:rrsrsrsr;S@rrrsr;:;r3MH@@#@M5,S@@irrsrr:@@
            @A:rrsrsrsrrrrrsrsrrr;::;@##@r:;rH@h;srr:H@
            ;@9:rrsrsrsrrrsrsrsrsr;,S@Hi@i:;s;MX;rr:h@;
             r@B:rrrrsrsrsrsrsrr;;sA@#i,i@h;r;S5;r:H@r
              ,@@r;rrrsrsrsrsrr;2BM3r:;r:G@:rrr;;r@@,
                B@Mr;rrrrsrsrsr@@S;;;rrr:5M;rr;rM@H
                 .@@@i;;rrrrsrs2i;rrrrr;r@M:;i@@@.
                   .A@@#5r;;;r;;;rrr;r:r#AsM@@H.
                      ;&@@@@MhXS5i5SX9B@@@@G;
                          :ihM#@@@@@##hs,
   
   Net:   <ethaddr> not set. Reading from E-fuse
   Detected MACID:84:7e:40:6f:5c:72
   cpsw
   Hit any key to stop autoboot:  0
   reading boot.scr
   
   194 bytes read
   Running bootscript from MMC/SD to set the ENV...
   ## Executing script at 80900000
   reading uImage
   
   2717696 bytes read
   ## Booting kernel from Legacy Image at 80010000 ...
      Image Name:   Linux-2.6.37-yocto-standard+
      Image Type:   ARM Linux Kernel Image (uncompressed)
      Data Size:    2717632 Bytes = 2.6 MiB
      Load Address: 80008000
      Entry Point:  80008000
      Verifying Checksum ... OK
      Loading Kernel Image ... OK
   OK 
   
   Starting kernel ...

Linux Kernel
~~~~~~~~~~~~

Control is now passed to the Linux kernel. A kernel boot appears as follows::

   [    0.000000] Linux version 2.6.37-yocto-standard+ (gsmecher@fromme) (gcc version 4.8.1 (Sourcery CodeBench Lite 2013.11-53) ) #47 Thu Feb 12 09:54:44 PST 2015
   [    0.000000] CPU: ARMv7 Processor [413fc082] revision 2 (ARMv7), cr=10c53c7f
   [    0.000000] CPU: VIPT nonaliasing data cache, VIPT aliasing instruction cache
   [    0.000000] Machine: ti8148evm
   [    0.000000] ti81xx_reserve: ### Reserved DDR region @bff00000
   [    0.000000] reserved size = 0 at 0x0
   [    0.000000] Memory policy: ECC disabled, Data cache writealloc
   [    0.000000] OMAP chip is TI8148 2.1
   [    0.000000] SRAM: Mapped pa 0x402f1000 to va 0xfe400000 size: 0xf000
   [    0.000000] Built 1 zonelists in Zone order, mobility grouping on.  Total pages: 259840
   [    0.000000] Kernel command line: console=ttyO0,115200n8 root=/dev/mmcblk0p2 ro rootwait
   [    0.000000] PID hash table entries: 4096 (order: 2, 16384 bytes)
   [    0.000000] Dentry cache hash table entries: 131072 (order: 7, 524288 bytes)
   [    0.000000] Inode-cache hash table entries: 65536 (order: 6, 262144 bytes)
   [    0.000000] Memory: 1023MB = 1023MB total
   [    0.000000] Memory: 1032704k/1032704k available, 15872k reserved, 261120K highmem
   [    0.000000] Virtual kernel memory layout:
   [    0.000000]     vector  : 0xffff0000 - 0xffff1000   (   4 kB)
   [    0.000000]     fixmap  : 0xfff00000 - 0xfffe0000   ( 896 kB)
   [    0.000000]     DMA     : 0xffc00000 - 0xffe00000   (   2 MB)
   [    0.000000]     vmalloc : 0xf0800000 - 0xf8000000   ( 120 MB)
   [    0.000000]     lowmem  : 0xc0000000 - 0xf0000000   ( 768 MB)
   [    0.000000]     pkmap   : 0xbfe00000 - 0xc0000000   (   2 MB)
   [    0.000000]     modules : 0xbf000000 - 0xbfe00000   (  14 MB)
   [    0.000000]       .init : 0xc0008000 - 0xc0044000   ( 240 kB)
   [    0.000000]       .text : 0xc0044000 - 0xc0521000   (4980 kB)
   [    0.000000]       .data : 0xc0522000 - 0xc056f7e0   ( 310 kB)
   [    0.000000] SLUB: Genslabs=11, HWalign=64, Order=0-3, MinObjects=0, CPUs=1, Nodes=1
   [    0.000000] NR_IRQS:407
   [    0.000000] IRQ: Found an INTC at 0xfa200000 (revision 5.0) with 128 interrupts
   [    0.000000] Total of 128 interrupts on 1 active controller
   [    0.000000] GPMC revision 6.0
   [    0.000000] Trying to install interrupt handler for IRQ400
   [    0.000000] Trying to install interrupt handler for IRQ401
   [    0.000000] Trying to install interrupt handler for IRQ402
   [    0.000000] Trying to install interrupt handler for IRQ403
   [    0.000000] Trying to install interrupt handler for IRQ404
   [    0.000000] Trying to install interrupt handler for IRQ405
   [    0.000000] Trying to install interrupt handler for IRQ406
   [    0.000000] Trying to install type control for IRQ407
   [    0.000000] Trying to set irq flags for IRQ407
   [    0.000000] OMAP clockevent source: GPTIMER1 at 20000000 Hz
   [    0.000000] Console: colour dummy device 80x30
   [    0.000000] Calibrating delay loop... 599.65 BogoMIPS (lpj=2998272)
   [    0.220000] pid_max: default: 32768 minimum: 301
   [    0.220000] Security Framework initialized
   [    0.220000] Mount-cache hash table entries: 512
   [    0.220000] CPU: Testing write buffer coherency: ok
   [    0.220000] devtmpfs: initialized
   [    0.220000] TI81XX: Map 0xbff00000 to 0xfe500000 for dram barrier
   [    0.220000] TI81XX: Map 0x40300000 to 0xfe600000 for sram barrier
   [    0.220000] omap_voltage_early_init: voltage driver support not added
   [    0.220000] regulator: core version 0.5
   [    0.220000] regulator: dummy:
   [    0.220000] NET: Registered protocol family 16
   [    0.220000] omap_voltage_domain_lookup: Voltage driver init not yet happened.Faulting!
   [    0.220000] omap_voltage_add_dev: VDD specified does not exist!
   [    0.220000] OMAP GPIO hardware version 0.1
   [    0.220000] OMAP GPIO hardware version 0.1
   [    0.220000] OMAP GPIO hardware version 0.1
   [    0.220000] OMAP GPIO hardware version 0.1
   [    0.220000] omap_mux_init: Add partition: #1: core, flags: 4
   [    0.240000] Cannot clk_get ck_32
   [    0.240000] Debugfs: Only enabling/disabling deep sleep and wakeup timer is supported now
   [    0.240000] ti81xx_pcie: Invoking PCI BIOS...
   [    0.240000] ti81xx_pcie: Setting up Host Controller...
   [    0.240000] ti81xx_pcie: Register base mapped @0xf0820000
   [    0.240000] ti81xx_pcie: forcing link width - x1
   [    0.350000] ti81xx_pcie: Starting PCI scan...
   [    0.350000] PCI: bus0: Fast back to back transfers enabled
   [    0.350000] ti81xx_pcie: PCI scan done.
   [    0.350000] bio: create slab <bio-0> at 0
   [    0.350000] vgaarb: loaded
   [    0.350000] SCSI subsystem initialized
   [    0.350000] usbcore: registered new interface driver usbfs
   [    0.350000] usbcore: registered new interface driver hub
   [    0.350000] usbcore: registered new device driver usb
   [    0.350000] USBSS revision 4ea2080b
   [    0.350000] registerd cppi-dma Intr @ IRQ 17
   [    0.350000] Cppi41 Init Done
   [    0.380000] omap_i2c omap_i2c.1: bus 1 rev4.0 at 100 kHz
   [    0.400000] omap_i2c omap_i2c.2: bus 2 rev4.0 at 100 kHz
   [    0.400000] Switching to clocksource gp timer
   [    0.410000] musb-hdrc: version 6.0, peripheral, debug=0
   [    0.410000] musb-hdrc musb-hdrc.0: dma type: dma-cppi41
   [    0.410000] MUSB controller-0 revision 4ea20800
   [    0.410000] usb2phy: computed values rxcalib(15)DACs(33 12 14)
   [    0.410000] usb2phy: override computed values rxcalib(15)DACs(33 12 14)
   [    0.410000] usb2phy_config: musb(0) rxcalib done, rxcalib read value 6f70d976
   [    0.410000] musb-hdrc musb-hdrc.0: USB Peripheral mode controller at f081e000 using DMA, IRQ 18
   [    0.410000] NET: Registered protocol family 2
   [    0.410000] IP route cache hash table entries: 32768 (order: 5, 131072 bytes)
   [    0.410000] TCP established hash table entries: 131072 (order: 8, 1048576 bytes)
   [    0.410000] TCP bind hash table entries: 65536 (order: 6, 262144 bytes)
   [    0.420000] TCP: Hash tables configured (established 131072 bind 65536)
   [    0.420000] TCP reno registered
   [    0.420000] UDP hash table entries: 512 (order: 1, 8192 bytes)
   [    0.420000] UDP-Lite hash table entries: 512 (order: 1, 8192 bytes)
   [    0.420000] NET: Registered protocol family 1
   [    0.420000] RPC: Registered udp transport module.
   [    0.420000] RPC: Registered tcp transport module.
   [    0.420000] RPC: Registered tcp NFSv4.1 backchannel transport module.
   [    0.420000] NetWinder Floating Point Emulator V0.97 (double precision)
   [    0.420000] PMU: registered new PMU device of type 0
   [    0.420000] omap-iommu omap-iommu.0: ducati registered
   [    0.420000] omap-iommu omap-iommu.1: sys registered
   [    0.550000] highmem bounce pool size: 64 pages
   [    0.560000] DLM (built Feb 11 2015 09:47:10) installed
   [    0.560000] JFFS2 version 2.2. (NAND) © 2001-2006 Red Hat, Inc.
   [    0.560000] msgmni has been set to 1507
   [    0.560000] io scheduler noop registered
   [    0.560000] io scheduler deadline registered
   [    0.560000] io scheduler cfq registered (default)
   [    0.560000] Serial: 8250/16550 driver, 4 ports, IRQ sharing disabled
   [    0.560000] omap_uart.0: ttyO0 at MMIO 0x48020000 (irq = 72) is a OMAP UART0
   [    1.210000] console [ttyO0] enabled
   [    1.210000] omap_uart.1: ttyO1 at MMIO 0x48022000 (irq = 73) is a OMAP UART1
   [    1.220000] omap_uart.2: ttyO2 at MMIO 0x48024000 (irq = 74) is a OMAP UART2
   [    1.230000] omap_uart.3: ttyO3 at MMIO 0x481a6000 (irq = 44) is a OMAP UART3
   [    1.240000] omap_uart.4: ttyO4 at MMIO 0x481a8000 (irq = 45) is a OMAP UART4
   [    1.240000] omap_uart.5: ttyO5 at MMIO 0x481aa000 (irq = 46) is a OMAP UART5
   [    1.260000] brd: module loaded
   [    1.270000] loop: module loaded
   [    1.270000] ahci probe: devid name is ahci
   [    1.280000] ahci CAP register dump =0x6726ff80
   [    1.280000] Modified ahci CAP register dump =0x6f26ff80
   [    1.290000] ahci ahci.0: forcing PORTS_IMPL to 0x1
   [    1.290000] ahci: SSS flag set, parallel bus scan disabled
   [    1.300000] ahci ahci.0: AHCI 0001.0300 32 slots 1 ports 3 Gbps 0x1 impl platform mode
   [    1.300000] ahci ahci.0: flags: ncq sntf stag pm led clo only pmp pio slum part ccc apst
   [    1.310000] scsi0 : ahci_platform
   [    1.320000] ata1: SATA max UDMA/133 mmio [mem 0x4a140000-0x4a150fff] port 0x100 irq 16
   [    1.330000] m25p80 spi1.0: s25fl256s0 (32768 Kbytes)
   [    1.330000] Creating 6 MTD partitions on "boot_spi_flash":
   [    1.340000] 0x000000000000-0x000000040000 : "U-Boot-min"
   [    1.350000] 0x000000040000-0x0000000c0000 : "U-Boot"
   [    1.350000] 0x0000000c0000-0x000000100000 : "U-Boot Env"
   [    1.360000] 0x000000100000-0x000000500000 : "Kernel"
   [    1.370000] 0x000000500000-0x000000540000 : "IPMI FRU"
   [    1.370000] 0x000000540000-0x000002000000 : "File System"
   [    1.380000] m25p80 spi4.0: s25fl256s0 (32768 Kbytes)
   [    1.380000] Creating 1 MTD partitions on "fpga_spi_flash":
   [    1.390000] 0x000000000000-0x000002000000 : "golden"
   [    1.400000] omap2-nand driver initializing
   [    1.450000] davinci_mdio davinci_mdio.0: davinci mdio revision 1.6
   [    1.450000] davinci_mdio davinci_mdio.0: detected phy mask fffffff9
   [    1.460000] davinci_mdio.0: probed
   [    1.460000] davinci_mdio davinci_mdio.0: phy[1]: device 0:01, driver Micrel KSZ9021 Gigabit PHY
   [    1.470000] davinci_mdio davinci_mdio.0: phy[2]: device 0:02, driver Micrel KSZ9021 Gigabit PHY
   [    1.480000] CAN device driver interface
   [    1.490000] CAN bus driver for Bosch D_CAN controller 1.0
   [    1.490000] usbcore: registered new interface driver cdc_ether
   [    1.500000] usbcore: registered new interface driver dm9601
   [    1.510000] usbcore: registered new interface driver cdc_acm
   [    1.510000] cdc_acm: v0.26:USB Abstract Control Model driver for USB modems and ISDN adapters
   [    1.520000] Initializing USB Mass Storage driver...
   [    1.530000] usbcore: registered new interface driver usb-storage
   [    1.530000] USB Mass Storage support registered.
   [    1.540000] g_ether gadget: using random self ethernet address
   [    1.540000] g_ether gadget: using random host ethernet address
   [    1.550000] usb0: MAC 1a:0f:97:f8:a1:58
   [    1.550000] usb0: HOST MAC 42:85:93:8c:44:71
   [    1.560000] g_ether gadget: Ethernet Gadget, version: Memorial Day 2008
   [    1.560000] g_ether gadget: g_ether ready
   [    1.570000] mice: PS/2 mouse device common for all mice
   [    1.580000] omap_rtc omap_rtc: rtc core: registered omap_rtc as rtc0
   [    1.580000] i2c /dev entries driver
   [    1.590000] i2c i2c-1: Added multiplexed i2c bus 5
   [    1.590000] i2c i2c-1: Added multiplexed i2c bus 6
   [    1.600000] i2c i2c-1: Added multiplexed i2c bus 7
   [    1.600000] i2c i2c-1: Added multiplexed i2c bus 8
   [    1.610000] i2c i2c-1: Added multiplexed i2c bus 9
   [    1.620000] i2c i2c-1: Added multiplexed i2c bus 10
   [    1.620000] i2c i2c-1: Added multiplexed i2c bus 11
   [    1.630000] pca953x 12-0020: interrupt support not compiled in
   [    1.640000] pca953x 12-0021: interrupt support not compiled in
   [    1.650000] pca953x 12-0022: interrupt support not compiled in
   [    1.660000] pca953x 12-0023: interrupt support not compiled in
   [    1.670000] i2c i2c-1: Added multiplexed i2c bus 12
   [    1.680000] pca954x 1-0070: registered 8 multiplexed busses for I2C switch pca9548
   [    1.680000] i2c i2c-2: Added multiplexed i2c bus 13
   [    1.690000] i2c i2c-2: Added multiplexed i2c bus 14
   [    1.700000] i2c i2c-2: Added multiplexed i2c bus 15
   [    1.700000] i2c i2c-2: Added multiplexed i2c bus 16
   [    1.710000] i2c i2c-2: Added multiplexed i2c bus 17
   [    1.710000] i2c i2c-2: Added multiplexed i2c bus 18
   [    1.720000] at24 19-0054: 1024 byte at24 EEPROM (writable)
   [    1.720000] i2c i2c-2: Added multiplexed i2c bus 19
   [    1.730000] i2c i2c-2: Added multiplexed i2c bus 20
   [    1.740000] pca954x 2-0071: registered 8 multiplexed busses for I2C switch pca9548
   [    1.740000] ata1: SATA link down (SStatus 0 SControl 300)
   [    1.750000] ina2xx 10-0040: power monitor ina230 (Rshunt = 50000 uOhm)
   [    1.760000] ina2xx 10-0041: power monitor ina230 (Rshunt = 20000 uOhm)
   [    1.770000] ina2xx 10-0042: power monitor ina230 (Rshunt = 20000 uOhm)
   [    1.780000] ina2xx 10-0044: power monitor ina230 (Rshunt = 50000 uOhm)
   [    1.790000] ina2xx 10-0045: power monitor ina230 (Rshunt = 20000 uOhm)
   [    1.800000] ina2xx 10-0046: power monitor ina230 (Rshunt = 20000 uOhm)
   [    1.800000] ina2xx 10-0047: power monitor ina230 (Rshunt = 5500 uOhm)
   [    1.810000] ina2xx 10-0048: power monitor ina230 (Rshunt = 2360 uOhm)
   [    1.820000] ina2xx 10-0049: power monitor ina230 (Rshunt = 2360 uOhm)
   [    1.830000] ina2xx 10-0043: power monitor ina230 (Rshunt = 2360 uOhm)
   [    1.840000] ina2xx 10-004b: power monitor ina230 (Rshunt = 5500 uOhm)
   [    1.850000] ina2xx 10-004c: power monitor ina230 (Rshunt = 2360 uOhm)
   [    1.860000] ina2xx 10-004d: power monitor ina230 (Rshunt = 770 uOhm)
   [    1.870000] ina2xx 10-004e: power monitor ina230 (Rshunt = 770 uOhm)
   [    1.880000] ina2xx 10-004f: power monitor ina230 (Rshunt = 770 uOhm)
   [    1.880000] ina2xx 19-0040: power monitor ina230 (Rshunt = 2360 uOhm)
   [    1.890000] lm75 12-0048: hwmon16: sensor 'tmp100'
   [    1.900000] lm75 12-004a: hwmon17: sensor 'tmp100'
   [    1.900000] lm75 12-004b: hwmon18: sensor 'tmp100'
   [    1.910000] lm75 12-004c: hwmon19: sensor 'tmp100'
   [    1.920000] OMAP Watchdog Timer Rev 0x00: initial timeout 60 sec
   [    1.930000] cpuidle: using governor ladder
   [    1.930000] cpuidle: using governor menu
   [    1.940000] TCP cubic registered
   [    1.940000] NET: Registered protocol family 10
   [    1.950000] NET: Registered protocol family 17
   [    1.950000] can: controller area network core (rev 20090105 abi 8)
   [    1.960000] NET: Registered protocol family 29
   [    1.960000] can: raw protocol (rev 20090105)
   [    1.970000] can: broadcast manager protocol (rev 20090105 t)
   [    1.980000] sctp: Hash tables configured (established 65536 bind 65536)
   [    1.980000] Registering the dns_resolver key type
   [    1.990000] VFP support v0.3: implementor 41 architecture 3 part 30 variant c rev 3
   [    2.000000] omap_voltage_late_init: Voltage driver support not added
   [    2.010000] Power Management for TI81XX.
   [    2.020000] Detected MACID=84:7e:40:6f:5c:72
   [    2.020000] Detected MACID=84:7e:40:6f:5c:73
   [    2.030000] omap_rtc omap_rtc: setting system clock to 2000-01-01 00:00:00 UTC (946684800)
   [    2.040000] Waiting for root device /dev/mmcblk0p2...
   [    2.120000] mmc0: host does not support reading read-only switch. assuming write-enable.
   [    2.130000] mmc0: new SD card at address 94de
   [    2.130000] mmcblk0: mmc0:94de SU01G 968 MiB
   [    2.140000]  mmcblk0: p1 p2
   [    2.150000] VFS: Mounted root (ext2 filesystem) readonly on device 179:2.
   [    2.160000] devtmpfs: mounted
   [    2.160000] Freeing init memory: 240K
   Starting logging: OK
   Starting rsyslog daemon: OK
   Populating /dev using udev: [    2.920000] <30>udevd[79]: starting version 182
   done
   Initializing random number generator... read-only file system detected...done
   Starting system message bus: done
   Starting network...
   [    3.800000]  
   [    3.800000] CPSW phy found : id is : 0x221611
   [    3.810000] ADDRCONF(NETDEV_UP): eth0: link is not ready
   Resetting the transceiver...
   Basic registers of MII PHY #2:  1140 7949 0022 1611 01e1 0000 0004 2001.
    Basic mode control register 0x1140: Auto-negotiation enabled.
    Basic mode status register 0x7949 ... 7949.
      Link status: not established.
      End of basic transceiver information.
   
   udhcpc (v1.21.1) started
   grep: /etc/resolv.conf: No such file or directory
   Failed to kill daemon: No such file or directory
   Sending discover...
   Sending discover...
   [    9.800000] PHY: 0:02 - Link is Up - 1000/Full
   [    9.800000] ADDRCONF(NETDEV_CHANGE): eth0: link becomes ready
   Sending discover...
   Sending select for 192.168.1.3...
   Lease of 192.168.1.3 obtained, lease time 16
   Failed to kill daemon: No such file or directory
   deleting routers
   route: SIOCDELRT: No such process
   [   11.010000]  
   [   11.010000] CPSW phy found : id is : 0x221611
   [   11.020000] ADDRCONF(NETDEV_UP): eth1: link is not ready
   Resetting the transceiver...
   Basic registers of MII PHY #1:  1140 7949 0022 1611 01e1 0000 0004 2001.
    Basic mode control register 0x1140: Auto-negotiation enabled.
    Basic mode status register 0x7949 ... 7949.
      Link status: not established.
      End of basic transceiver information.
   
   Setting RMEM_MAX...OK
   Starting dropbear sshd: OK
   Starting iceboard fastpath: OK
   
   Welcome to Buildroot
   iceboard login: 

The Linux boot transcript varies according to the system's configuration. In
particular, the final entries show a successful DHCP lease, indicating the
system should be accessible over the network.

.. vim: sts=3 ts=3 sw=3 tw=78 smarttab expandtab
