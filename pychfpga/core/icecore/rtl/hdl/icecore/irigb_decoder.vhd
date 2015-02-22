library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.icecore_package.irigb;

entity irigb_decoder is port (
	clk_200mhz : in std_logic;
	irig : in std_logic_vector(0 to 3);
	source : in unsigned(1 downto 0);
	pps: out std_logic;
	ts : out irigb
);
end irigb_decoder;

architecture rtl of irigb_decoder is

	signal irig_dly1, irig_dly2 : std_logic := '0';
	signal symbol_counter : unsigned(17 downto 0) := (others => '0');

	signal source_dly1, source_dly2 : unsigned(source'range) := (others => '0');

	-- How many milliseconds has the IRIG signal remained low?
	-- We use this to discriminate between symbols. Tracking 'high'
	-- length might seem more conventional, but this way, we can decode
	-- symbols at the instant of the next rising edge (which is what we
	-- ultimately align timestamps to.)
	signal ms_lo : unsigned(3 downto 0) := (others => '0');
	signal ms_strobe : std_logic := '0';

	-- Strobes for 0, 1, and p symbols.
	signal strobe_0, strobe_1, strobe_p : std_logic := '0';
	signal last_p, double_p : std_logic := '0';

	-- There's a state here for every IRIG-B bit, and a 'stuffed' state
	-- that the decoder slides into after each timestamp. It's
	-- re-activated when two timing pulses occur back-to-back.
	type state_type is (
		S1, S2, S4, S8, Sb, S10, S20, S40, P1,
		M1, M2, M4, M8, Mb, M10, M20, M40, Mb2, P2,
		H1, H2, H4, H8, Hb, H10, H20, Hb2, Hb3, P3,
		D1, D2, D4, D8, Db, D10, D20, D40, D80, P4,
		D100, D200, Db2, Db3, Db4, Db5, Db6, Db7, Db8, P5,
		Y1, Y2, Y4, Y8, Yb, Y10, Y20, Y40, Y80, P6,
		C0, C1, C2, C3, C4, C5, C6, C7, C8, P7,
		C9, C10, C11, C12, C13, C14, C15, C16, C17, P8,
		SBS0, SBS1, SBS2, SBS3, SBS4, SBS5, SBS6, SBS7, SBS8, P9,
		SBS9, SBS10, SBS11, SBS12, SBS13, SBS14, SBS15, SBS16, SBSb, P0,
		STUFFED
	);
	signal state : state_type := STUFFED;

	-- Sized to fit maximum BCD values (so a deranged IRIG-B timestamp
	-- will still be accurately decoded)
	signal s,m : unsigned(6 downto 0) := (others => '0');
	signal h : unsigned(5 downto 0) := (others => '0');
	signal d : unsigned(8 downto 0) := (others => '0');
	signal y : unsigned(7 downto 0) := (others => '0');
	signal c : std_logic_vector(17 downto 0) := (others => '0');
	signal sbs : std_logic_vector(17 downto 0) := (others => '0');
	signal ss : unsigned(28 downto 0) := (others => '1'); -- at 200 MHz, ~2.7 seconds to saturation

	-- Output timestamp (pipelined)
	signal ts_pre : irigb;

begin
	-- Symbol detector
	process(clk_200mhz)
	begin
		if rising_edge(clk_200mhz) then

			-- Multiplex and delay for pipelining and edge detection
			irig_dly1 <= irig(to_integer(source_dly2));
			irig_dly2 <= irig_dly1;

			source_dly1 <= source;
			source_dly2 <= source_dly1;

			-- Count millisecond ticks between edges
			symbol_counter <= (others => '0');
			ms_strobe <= '0';
			if irig_dly1=irig_dly2 then
				symbol_counter <= symbol_counter + 1;
				if symbol_counter=199999 then
					symbol_counter <= (others => '0');
					ms_strobe <= '1';
				end if;
			end if;

			-- We need a 'low' counter to decode symbols
			if irig_dly2='1' then
				ms_lo <= (others => '0');
			elsif ms_strobe='1' and ms_lo /= (ms_lo'range => '1') then
				ms_lo <= ms_lo + 1;
			end if;

			-- Now decode symbols on a rising edge.
			strobe_0 <= '0';
			strobe_1 <= '0';
			strobe_p <= '0';
			if irig_dly2='1' then
				case to_integer(ms_lo) is
					when 1|2 => strobe_p <= '1';
					when 4|5 => strobe_1 <= '1';
					when 7|8 => strobe_0 <= '1';
					when others =>
				end case;
			end if;

			-- When a double-P is detected, force state to become S1. This
			-- is how the state machine gets initialized during each timestamp.
			if strobe_p='1' then
				last_p <= '1';
			end if;
			if strobe_0='1' or strobe_1='1' then
				last_p <= '0';
			end if;
			if strobe_p='1' and last_p='1' then
				state <= S1;
				s <= (others => '0');
				m <= (others => '0');
				h <= (others => '0');
				d <= (others => '0');
				y <= (others => '0');
				c <= (others => '0');
				sbs <= (others => '0');
			end if;

			-- If we switch the irig source, invalidate the state so we can start anew
			if source_dly1 /= source_dly2 then
				state <= STUFFED;
			-- Otherwise, we proceed through states.
			elsif state/=STUFFED and (strobe_1 or strobe_0 or strobe_p)='1' then
				state <= state_type'val(state_type'pos(state) + 1);
			end if;

			-- When a '1' is decoded, we need to set some bits somewhere
			if strobe_1='1' then
				case state is
					when S1    => s <= s + 1;
					when S2    => s <= s + 2;
					when S4    => s <= s + 4;
					when S8    => s <= s + 8;
					when S10   => s <= s + 10;
					when S20   => s <= s + 20;
					when S40   => s <= s + 40;

					when M1    => m <= m + 1;
					when M2    => m <= m + 2;
					when M4    => m <= m + 4;
					when M8    => m <= m + 8;
					when M10   => m <= m + 10;
					when M20   => m <= m + 20;
					when M40   => m <= m + 40;

					when H1    => h <= h + 1;
					when H2    => h <= h + 2;
					when H4    => h <= h + 4;
					when H8    => h <= h + 8;
					when H10   => h <= h + 10;
					when H20   => h <= h + 20;

					when D1    => d <= d + 1;
					when D2    => d <= d + 2;
					when D4    => d <= d + 4;
					when D8    => d <= d + 8;
					when D10   => d <= d + 10;
					when D20   => d <= d + 20;
					when D40   => d <= d + 40;
					when D80   => d <= d + 80;
					when D100  => d <= d + 100;
					when D200  => d <= d + 200;

					when Y1    => y <= y + 1;
					when Y2    => y <= y + 2;
					when Y4    => y <= y + 4;
					when Y8    => y <= y + 8;
					when Y10   => y <= y + 10;
					when Y20   => y <= y + 20;
					when Y40   => y <= y + 40;
					when Y80   => y <= y + 80;

					when C0    => c(0) <= '1';
					when C1    => c(1) <= '1';
					when C2    => c(2) <= '1';
					when C3    => c(3) <= '1';
					when C4    => c(4) <= '1';
					when C5    => c(5) <= '1';
					when C6    => c(6) <= '1';
					when C7    => c(7) <= '1';
					when C8    => c(8) <= '1';
					when C9    => c(9) <= '1';
					when C10   => c(10) <= '1';
					when C11   => c(11) <= '1';
					when C12   => c(12) <= '1';
					when C13   => c(13) <= '1';
					when C14   => c(14) <= '1';
					when C15   => c(15) <= '1';
					when C16   => c(16) <= '1';
					when C17   => c(17) <= '1';

					when SBS0  => sbs(0) <= '1';
					when SBS1  => sbs(1) <= '1';
					when SBS2  => sbs(2) <= '1';
					when SBS3  => sbs(3) <= '1';
					when SBS4  => sbs(4) <= '1';
					when SBS5  => sbs(5) <= '1';
					when SBS6  => sbs(6) <= '1';
					when SBS7  => sbs(7) <= '1';
					when SBS8  => sbs(8) <= '1';
					when SBS9  => sbs(9) <= '1';
					when SBS10 => sbs(10) <= '1';
					when SBS11 => sbs(11) <= '1';
					when SBS12 => sbs(12) <= '1';
					when SBS13 => sbs(13) <= '1';
					when SBS14 => sbs(14) <= '1';
					when SBS15 => sbs(15) <= '1';
					when SBS16 => sbs(16) <= '1';

					when others => -- nop
				end case;
			end if;

			-- Count subseconds; on saturation, clear the 'recent' flag.
			if ss=(ss'range => '1') then
				ts_pre.recent <= '0';
				ts_pre.source <= source_dly2; -- otherwise this never gets updated when IRIG source invalid
			else
				ts_pre.recent <= '1';
				ss <= ss + 1;
			end if;

			pps <= '0';
			if state=P0 and strobe_p='1' then
			-- generate a PPS rising edge on the rising edge following the last
				pps <= '1';
				-- Latch timestamp
				ts_pre.s <= s;
				ts_pre.m <= m;
				ts_pre.h <= h;
				ts_pre.d <= d;
				ts_pre.y <= y;
				ts_pre.c <= c;
				ts_pre.sbs <= sbs;
				ts_pre.source <= source_dly2;

				ss <= (others => '0');
			end if;

			-- -- Clear PPD 0.5 seconds after the beginning of a frame to yield a 50% duty cycle.
			-- if ss = 100000 then
			-- 	pps <= '0';
			-- end if;

			ts <= ts_pre;

		end if;
	end process;

	-- Assign subseconds; divide 200 MHz counts down to 100 MHz.
	ts_pre.ss <= ss(28 downto 1);

end rtl;
