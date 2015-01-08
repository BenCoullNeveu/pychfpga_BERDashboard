----------------------------------------------------------------------------------
--! @file
--! @brief
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

entity bus_interconnect is
	generic (
		NUMBER_OF_MASTER_INTERFACES: integer;
		ADDRESS_WIDTH: integer := 32
	);
	port (
		-- Slave interface
		s_addr: in slv32;
		s_wdat: in slv32;
		s_rdat: out slv32;
		s_wreq: in std_logic;
		s_wack: out std_logic;
		s_rreq: in std_logic;
		s_rack: out std_logic;

		-- Master interfaces
		m_addr: out slv32_array(0 to NUMBER_OF_MASTER_INTERFACES-1);
		m_wdat: out slv32_array(0 to NUMBER_OF_MASTER_INTERFACES-1);
		m_rdat: in slv32_array(0 to NUMBER_OF_MASTER_INTERFACES-1);
		m_wreq: out std_logic_vector(0 to NUMBER_OF_MASTER_INTERFACES-1);
		m_wack: in std_logic_vector(0 to NUMBER_OF_MASTER_INTERFACES-1);
		m_rreq: out std_logic_vector(0 to NUMBER_OF_MASTER_INTERFACES-1);
		m_rack: in std_logic_vector(0 to NUMBER_OF_MASTER_INTERFACES-1);

		clk: in std_logic -- Control interface clock
	);
end bus_interconnect;

architecture IMPL of bus_interconnect is


begin

	---------------------------------------------------------------------
	-- Register access process
	---------------------------------------------------------------------

	bus_proc: process(clk)
	-- variable reg_number_var: integer range 0 to 2**LOCAL_ADDRESS_WIDTH-1;
	variable s_rdat_var: slv32;
	begin
		if rising_edge(clk) then

			m_rreq <= (others=> s_rreq);
			m_wreq <= (others=> s_wreq);
			m_addr <= (others=> s_addr);
			m_wdat <= (others=> s_wdat);

			s_rack <= or_reduce(m_rack);
			s_wack <= or_reduce(m_wack);

			-- or all data buses from masters
			s_rdat_var := (others=>'0');
			for i in 0 to NUMBER_OF_MASTER_INTERFACES-1 loop
				s_rdat_var := s_rdat_var or m_rdat(i);
			end loop;
			s_rdat <= s_rdat_var;

		end if; -- clk
	end process;

end IMPL;
