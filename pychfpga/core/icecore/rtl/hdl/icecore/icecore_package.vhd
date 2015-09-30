----------------------------------------------------------------------------------
--! @file
-- Company: McGill University
-- Engineer: JF Cliche & Graeme Smecher
--
-- Create Date:   2013-05-22
-- Design Name:  Icecore
-- Module Name:    Package
-- Project Name: icecore
-- Tool versions: Vivado 2014.4
-- Description: Implements common icecore variables and types
----------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.all;
use IEEE.NUMERIC_STD.ALL;

package icecore_package is

	type irigb is record
		s,m : unsigned(6 downto 0);
		h : unsigned(5 downto 0);
		d : unsigned(8 downto 0);
		y : unsigned(7 downto 0);
		c : std_logic_vector(17 downto 0);
		sbs : std_logic_vector(17 downto 0);
		ss : unsigned(27 downto 0); -- 100MHz ticks, saturating
		recent : std_logic;
		source : unsigned(1 downto 0);
	end record;

	-- generic types and subtypes
	type SLV8_ARRAY_TYPE is array (NATURAL RANGE <>) of std_logic_vector(7 downto 0);
	type SLV16_ARRAY_TYPE is array (NATURAL RANGE <>) of std_logic_vector(15 downto 0);
	type SLV32_ARRAY_TYPE is array (NATURAL RANGE <>) of std_logic_vector(31 downto 0);
	subtype slv32 is std_logic_vector(31 downto 0);
	type slv32_array is array (NATURAL RANGE <>) of std_logic_vector(31 downto 0);

	type U16_ARRAY_TYPE is array(integer range <>) of unsigned(15 downto 0);
	type U32_ARRAY_TYPE is array(integer range <>) of unsigned(31 downto 0);

	type INTEGER_ARRAY_TYPE is array (natural range <>) of integer;

end icecore_package;

package body icecore_package is
end icecore_package;
