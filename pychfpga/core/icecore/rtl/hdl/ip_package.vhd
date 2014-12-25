----------------------------------------------------------------------------------
--! @file
-- Company: McGill University
-- Engineer: JF Cliche
-- 
-- Create Date:   2013-05-22 
-- Design Name:  None
-- Module Name:    IP definition Package
-- Project Name: None
-- Target Devices: Kintex 7
-- Tool versions: Vivado 2013.2
-- Description: Provide definition of the IP cores as components so they can be instantiated as black boxes. This is needed to use the pre-synthesized IP feature of Vivado 2013.2
--
----------------------------------------------------------------------------------

library IEEE;
use IEEE.STD_LOGIC_1164.all;
use IEEE.NUMERIC_STD.ALL;

package ip_package is

	component clock_mmcm port (
		-- Clock in ports
		CLK_IN1           : in     std_logic;
		CLKFB_IN          : in     std_logic;
		-- Clock out ports
		CLK200          : out    std_logic;
		CLK125          : out    std_logic;
		clk25_180          : out    std_logic;
		CLK25          : out    std_logic;
		clk25_90          : out    std_logic;
		CLKFB_OUT         : out    std_logic;
		-- Status and control signals
		RESET             : in     std_logic;
		LOCKED            : out    std_logic
	 );
	end component;

end ip_package;

package body ip_package is
end ip_package;
