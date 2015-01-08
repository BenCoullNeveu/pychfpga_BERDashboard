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

entity register_array is
	generic (
		ADDRESS_MASK: std_logic_vector(31 downto 0); -- X"000010--" means that we respond to s_addr(31:16)=x"000010" and that we have 8 bits of local address (i.e. 64 registers or less)
		NUMBER_OF_REGISTERS: integer := 1;
		DEFAULT_REGISTER_VALUES: slv32_array;
		ADDRESS_WIDTH: integer := 32;
		SIM: BOOLEAN:= FALSE --! Indicates this is running as a simulation. Used to accelerate simulations
	);
	port (
		-- Control interface (*** JFC: to be replaced by an AXI4-Lite bus)
		s_addr: in std_logic_vector(ADDRESS_WIDTH-1 downto 0);
		s_wdat: in std_logic_vector(31 downto 0);
		s_rdat: out std_logic_vector(31 downto 0);
		s_wreq: in std_logic;
		s_wack: out std_logic;
		s_rreq: in std_logic;
		s_rack: out std_logic;

		reg_wr_value : out slv32_array(0 to NUMBER_OF_REGISTERS-1) := DEFAULT_REGISTER_VALUES(0 to NUMBER_OF_REGISTERS-1);
		reg_rd_value : in slv32_array(0 to NUMBER_OF_REGISTERS-1) := (others=> (others=>'0'));

		clk: in std_logic -- Control interface clock
	);
end register_array;

architecture IMPL of register_array is

	function find_local_address_width_from_mask(mask:std_logic_vector) return integer is --! returns the number of 32-bit registers. mask must be 'downto' direction.
		begin
			for i in mask'low to mask'high loop
				if mask(i)='0' or mask(i)='1' then
					if i<2 then
						return -1; -- invalid
					else
						return i-1;
					end if;
				end if;
			end loop;
			return mask'length-2;
		end find_local_address_width_from_mask;

	-- constant LOCAL_ADDRESS_WIDTH: integer := find_local_address_width_from_mask(ADDRESS_MASK);
	constant LOCAL_ADDRESS_WIDTH: integer := 6;

	signal local_addr_int: unsigned(LOCAL_ADDRESS_WIDTH-1 downto 0) := (others => '0');
	signal s_wdat_int: std_logic_vector(31 downto 0) := (others => '0');

	-- Bus control signals for each module, packed into arrays
	signal s_rreq_int: std_logic;
	signal s_wreq_int: std_logic;

begin

	---------------------------------------------------------------------
	-- Register access process
	---------------------------------------------------------------------

	reg_proc: process(clk)
	-- variable reg_number_var: integer range 0 to 2**LOCAL_ADDRESS_WIDTH-1;
	variable reg_number_var: integer range 0 to NUMBER_OF_REGISTERS-1;
	begin
		if rising_edge(clk) then

			local_addr_int <= unsigned(s_addr(LOCAL_ADDRESS_WIDTH+1 downto 2)); -- strip last two bits to convert byte address to word address;
			reg_number_var := to_integer(local_addr_int); -- To do: add checks against actual number of registers
			s_wdat_int <= s_wdat;
			s_rdat <= (others => '0'); --! This is important to make sure that s_rdat is 0 when we are not accessing this module.

			if s_addr(ADDRESS_WIDTH-1 downto LOCAL_ADDRESS_WIDTH+2) = ADDRESS_MASK(ADDRESS_WIDTH-1 downto LOCAL_ADDRESS_WIDTH+2) then
				s_rreq_int <= s_rreq;
				s_wreq_int <= s_wreq;
			else
				s_rreq_int <= '0';
				s_wreq_int <= '0';
			end if;
			-- Immediately ack any requests.
			s_wack <= s_wreq_int;
			s_rack <= s_rreq_int;

			-- Reads
			if s_rreq_int = '1' then
				s_rdat <= reg_rd_value(reg_number_var);
			end if;

			-- Writes
			if s_wreq_int='1' then
				reg_wr_value(reg_number_var) <= s_wdat_int;
			end if;

		end if; -- clk
	end process;

end IMPL;
