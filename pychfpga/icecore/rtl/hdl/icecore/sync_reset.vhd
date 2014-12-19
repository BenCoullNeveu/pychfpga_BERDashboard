-----------------------------------------------------------------------------
-- Title      : FF Synchronizer with Reset
-- Project    : 10 Gigabit Ethernet PCS/PMA Core
-- File       : xge_sync.vhd (was ten_gig_eth_pcs_pma_0_ff_synchronizer_rst2.vhdd in v14 10G PCS/PMA example design)
-- Author     : Xilinx Inc.
-- Description: This module provides a parameterizable multi stage 
--              FF Synchronizer with appropriate synth attributes
--              to mark ASYNC_REG and prevent SRL inference
--              An active reset is included with a paramterized 
--              reset value
-------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity sync_reset is 
	generic(
		NUMBER_OF_STAGES : integer := 3;
		RESET_VALUE : std_logic := '1'
	);
	port (
		clk : in std_logic;
		async_reset : in std_logic;
		sync_reset : in std_logic := not RESET_VALUE;
		reset_out : out std_logic
	);
end sync_reset;

architecture impl of sync_reset is
	
	signal sync_regs : std_logic_vector(NUMBER_OF_STAGES-1 downto 0) := (others => RESET_VALUE);

	attribute SHREG_EXTRACT : string;
	attribute SHREG_EXTRACT of sync_regs : signal is "no";
	attribute ASYNC_REG : string;
	attribute ASYNC_REG of sync_regs : signal is "true";
	
begin
	sync_proc : process(clk, async_reset)
	begin
		if(async_reset = '1') then
			sync_regs <= (others => RESET_VALUE);
		elsif rising_edge(clk) then
			sync_regs <= sync_regs(NUMBER_OF_STAGES-2 downto 0) & sync_reset; -- shift left
		end if;
	end process sync_proc;
	
	reset_out <= sync_regs(NUMBER_OF_STAGES-1);
	
end impl;
