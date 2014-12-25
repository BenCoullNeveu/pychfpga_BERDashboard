library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity buck_sync is port (
	clk_200mhz     : in std_logic;

	sync_fmca : out std_logic;
	sync_fmcb : out std_logic;

	sync_1v0 : out std_logic;
	sync_1v8 : out std_logic;
	sync_1v0_gtx : out std_logic;
	sync_5v0 : out std_logic;
	sync_1v2 : out std_logic;
	sync_vadj : out std_logic;
	sync_1v5 : out std_logic;
	sync_3v3 : out std_logic;
	sync_12v0 : out std_logic
);
end entity buck_sync;

------------------------------------------------------------------------------
-- Architecture section
------------------------------------------------------------------------------

architecture IMPL of buck_sync is

	-- A 1 MHz switching clock is highly desirable for the ADCs. To get there, we prescale by 5 and
	-- assign sync edges to one of 40 slots.
	signal prescale : unsigned(2 downto 0) := (others => '0');
	signal prescale_strobe : std_logic := '0';

	signal phase : unsigned(5 downto 0) := (others => '0');

	signal sync_fmca_int : std_logic := '0';
	signal sync_fmcb_int : std_logic := '0';

	signal sync_1v0_int : std_logic := '0';
	signal sync_1v8_int : std_logic := '0';
	signal sync_1v0_gtx_int : std_logic := '0';
	signal sync_5v0_int : std_logic := '0';
	signal sync_1v2_int : std_logic := '0';
	signal sync_vadj_int : std_logic := '0';
	signal sync_1v5_int : std_logic := '0';
	signal sync_3v3_int : std_logic := '0';
	signal sync_12v0_int : std_logic := '0';

begin

	process(clk_200mhz)
	begin
		if rising_edge(clk_200mhz) then
			-- Prescale into prescale_strobe
			prescale_strobe <= '0';
			prescale <= prescale + 1;
			if to_integer(prescale)=4 then
				prescale <= (others => '0');
				prescale_strobe <= '1';

			end if;

			-- Count slots
			if prescale_strobe='1' then
				phase <= phase + 1;
				if to_integer(phase)=39 then
					phase <= (others => '0');
				end if;
			end if;

			-- Assign outputs
			case to_integer(phase) is
				-- The mezzanine syncs are run at 2 MHz, 180' out of phase. Since
				-- different boards will have different 200 MHz phase offsets from the
				-- global 10 MHz clock, there's no global mezz buck sync -- so forget
				-- about confining all these pulses to a single sample instant at the
				-- ADCs. Instead, focus on keeping a tidy local supply by spreading out
				-- similar loads.
				when 0|20 =>
					sync_fmca_int <= '1';
					sync_fmcb_int <= '0';
				when 10|30 =>
					sync_fmca_int <= '0';
					sync_fmcb_int <= '1';

				-- We assign everything else a slot in between. Supplies are ganged
				-- two ways: VCC3V3, VCC12V0, and VCC5V0 come off the main supply, and
				-- are staggered against each other. The remainder are powered off the
				-- 5V supply, and are staggered against each other (and it). This is
				-- fairly unoptimized; for example, I haven't really tried to balance
				-- large loads against each other or anything. It's not clear offhand
				-- what would be smart.
				when 1 => sync_5v0_int <= '1';
				when 3 => sync_1v0_int <= '1';
				when 5 => sync_12v0_int <= '0';
				when 7 =>
				when 9 => sync_1v2_int <= '1';
				when 11 => sync_1v0_gtx_int <= '0';
				when 13 => sync_3v3_int <= '1';
				when 15 => sync_vadj_int <= '0';
				when 17 => sync_1v5_int <= '0';
				when 19 => sync_1v8_int <= '1';
				when 21 => sync_5v0_int <= '0';
				when 23 => sync_1v0_int <= '0';
				when 25 => sync_12v0_int <= '1';
				when 27 =>
				when 29 => sync_1v2_int <= '0';
				when 31 => sync_1v0_gtx_int <= '1';
				when 33 => sync_3v3_int <= '0';
				when 35 => sync_vadj_int <= '1';
				when 37 => sync_1v5_int <= '1';
				when 39 => sync_1v8_int <= '0';

				when others => -- nop
			end case;

			-- Buffer
			sync_fmca <= sync_fmca_int;
			sync_fmcb <= sync_fmcb_int;

			sync_1v0 <= sync_1v0_int;
			sync_1v8 <= sync_1v8_int;
			sync_1v0_gtx <= sync_1v0_gtx_int;
			sync_5v0 <= sync_5v0_int;
			sync_1v2 <= sync_1v2_int;
			sync_vadj <= sync_vadj_int;
			sync_1v5 <= sync_1v5_int;
			sync_3v3 <= sync_3v3_int;
			sync_12v0 <= sync_12v0_int;
		end if;
	end process;

end IMPL;
