----------------------------------------------------------------------------------
--! @file
--! @brief Core firmware registers extected to be present on every IceBoard application
-- Company: McGill University
-- Engineers: JF Cliche (JFC Inc) & Graeme Smecher (Three-Speed Logic, Inc)
--
-- Create Date:    2015-01-06
-- Design Name:    ICE development environment
-- Module Name:    icecore
-- Project Name:   Generic
-- Target Devices:  Kintex 7 on IceBoard (McGill Model MGK7MB)
-- Tool versions:  Vivado 2014.4
---  LIBRARY DECLARATIONS ----------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use ieee.std_logic_misc.all; -- for or_reduce()

library UNISIM;
use UNISIM.VComponents.all;

use work.icecore_package.all;

entity core_registers is
	generic (
		ADDRESS_MASK: std_logic_vector(31 downto 0);
		ADDRESS_WIDTH: integer := 32;
		APPLICATION_COOKIE: std_logic_vector(31 downto 0);
		APPLICATION_FLAGS: std_logic_vector(31 downto 0);
		SIM: BOOLEAN:= FALSE --! Indicates this is running as a simulation. Used to accelerate simulations
	);
	port (

		-- Control interface (*** JFC: to be replaced by an AXI4-Lite bus)
		addr: in std_logic_vector(ADDRESS_WIDTH-1 downto 0);
		din: in std_logic_vector(31 downto 0);
		dout: out std_logic_vector(31 downto 0);

		wreq: in std_logic;
		wack: out std_logic;
		rreq: in std_logic;
		rack: out std_logic;

		clk: in std_logic; -- Control interface clock
		dna_clk: in std_logic -- CLock used for DNA access (<97 MHz)

	);
end core_registers;

architecture IMPL of core_registers is

	-- Attributes
	attribute equivalent_register_removal: string;
	attribute keep:string;
	attribute shreg_extract: string;



	signal firmware_crc32: std_logic_vector(31 downto 0);


	signal firmware_timestamp: std_logic_vector(31 downto 0);
	signal firmware_timestamp_valid: std_logic;

	signal dna_dout: std_logic;
	signal dna_read: std_logic :='1'; -- First clock is a read
	signal dna_shift: std_logic := '1'; -- Will start shifting as soon as read is disabled
	signal dna_ctr: unsigned(5 downto 0) := to_unsigned(57-1, 6); -- Will shift 57 times
	signal fpga_serial_number: std_logic_vector(56 downto 0) := (others=>'0'); -- Need to initialize because we do not shift all the 64 bits

	signal fpga_ip_address: std_logic_vector(31 downto 0) := X"0A0A0A0B";
	signal fpga_ip_port: std_logic_vector(15 downto 0) := X"A028"; -- 41000
	signal fpga_mac_address: std_logic_vector(47 downto 0) := X"123456789ABC";

	constant NUMBER_OF_REGISTERS: integer := 10;
	signal reg_wr_value : slv32_array(0 to NUMBER_OF_REGISTERS-1);
	signal reg_rd_value : slv32_array(0 to NUMBER_OF_REGISTERS-1);


begin

-------------------------
-- Register assignments
-------------------------

-- Register Read values
reg_rd_value(0) <= x"beefface"; -- (Read only) Core firmware cookie
reg_rd_value(1) <= APPLICATION_COOKIE; -- (Read only) Application firmware cookie
reg_rd_value(2) <= APPLICATION_FLAGS; -- (Read only) Application Flags: Kintex 7
reg_rd_value(3) <= firmware_crc32; -- (Read/Write with readback) Firmware CRC32, computed by the host application and stored here for future reference
reg_rd_value(4) <= firmware_timestamp; -- (Read only) Firmware timestamp, taken from the USER_ACCESS data filled in when the bitstream file was generated
reg_rd_value(5) <= fpga_serial_number(31 downto 0); -- (Read only)
reg_rd_value(6) <= "0000000" & fpga_serial_number(56 downto 32); -- (Read only)
reg_rd_value(7) <= fpga_mac_address(31 downto 0); -- (Read/Write with readback)
reg_rd_value(8) <= fpga_mac_address(47 downto 32) & fpga_ip_port; -- (Read/Write with readback)
reg_rd_value(9) <= fpga_ip_address; -- (Read/Write with readback)
-- reg_rd_value(7 to 9) <= reg_wr_value(7 to 9); -- Readback FPGA  Ethernet parameters

-- Register write values
firmware_crc32                 <= reg_wr_value(3);
fpga_mac_address(31 downto 0)  <= reg_wr_value(7);
fpga_mac_address(47 downto 32) <= reg_wr_value(8)(31 downto 16);
fpga_ip_port                   <= reg_wr_value(8)(15 downto 0);
fpga_ip_address                <= reg_wr_value(9);


reg0: entity work.register_array
	generic map(
		ADDRESS_MASK => ADDRESS_MASK,
		NUMBER_OF_REGISTERS => NUMBER_OF_REGISTERS,
		DEFAULT_REGISTER_VALUES => (0 to 8 => X"00000000", 9 => X"12345678"),
		ADDRESS_WIDTH => 32,
		SIM => SIM --! Indicates this is running as a simulation. Used to accelerate simulations
	)
	port map (
		-- Control interface (*** JFC: to be replaced by an AXI4-Lite bus)
		addr => addr,
		din => din,
		dout => dout,
		wreq => wreq,
		wack => wack,
		rreq => rreq,
		rack => rack,

		-- Register interface
		reg_wr_value  => reg_wr_value,
		reg_rd_value  => reg_rd_value,

		clk => clk -- Clocks both control and register interface
	);



--! Implement USR_ACCESS for 7-series platforms
usr_access0: USR_ACCESSE2
	port map(
		CFGCLK => open,--1-bit Configuration Clock output
		DATA => firmware_timestamp,--32-bit Configuration Data output
		DATAVALID => firmware_timestamp_valid --1-bit Active high data validoutput
		);

dna0 : DNA_PORT
	generic map (
		SIM_DNA_VALUE => X"000000000000000" -- Specifies a sample 57-bit DNA value for simulation
	)
	port map (
		DOUT => dna_dout, -- 1-bit output: DNA output data.
		CLK => dna_clk, -- 1-bit input: Clock input.
		DIN => '0', -- 1-bit input: User data input pin.
		READ => dna_read, -- 1-bit input: Active high load DNA, active low read input.
		SHIFT => dna_shift -- 1-bit input: Active high shift enable input.
	);

dna_proc: process(dna_clk)
	begin
		if rising_edge(dna_clk) then
			dna_read <='0';
			if dna_read='0' and dna_shift='1' then -- when data is ready and we have not finished shifting
				fpga_serial_number <= std_logic_vector(shift_left(unsigned(fpga_serial_number), 1));
				fpga_serial_number(0) <= dna_dout;
				dna_ctr <= dna_ctr - 1;
				if dna_ctr = 0 then
					dna_shift <= '0';
				end if;
			end if;
		end if;
	end process;


end IMPL;
