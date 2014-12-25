library IEEE;
use IEEE.std_logic_1164.all;
use IEEE.numeric_std.all;

entity irigb_encoder is port (
	clk_200mhz : in std_logic;
	ts_out : out std_logic
);
end irigb_encoder;

architecture behav of irigb_encoder is

	signal ticks : integer range 0 to 199999 := 0;
	signal tick_strobe : std_logic := '0';

	signal ms : integer range 0 to 9 := 0;
	signal index : integer range 0 to 99 := 99;

	signal sec1 : unsigned(3 downto 0) := "0000"; -- sec is 0-59
	signal sec10 : unsigned(2 downto 0) := "000";

	signal min1 : unsigned(3 downto 0) := "0000"; -- min is 0-59
	signal min10 : unsigned(2 downto 0) := "000";

	signal hour1 : unsigned(3 downto 0) := "0000"; -- hour is 0-23
	signal hour10 : unsigned(1 downto 0) := "00";

	signal day1 : unsigned(3 downto 0) := "0001"; -- day is 1-366
	signal day10 : unsigned(3 downto 0) := "0000";
	signal day100 : unsigned(1 downto 0) := "00";

	signal year1 : unsigned(3 downto 0) := "0000"; -- year is 0-99
	signal year10 : unsigned(3 downto 0) := "0000";

	signal sbs : unsigned(16 downto 0) := b"0000_0000_0000_0000_0"; -- sbs is 0-86399

	signal dout : std_logic;

	type sul_bool is array(boolean) of std_ulogic;
	constant active_high: sul_bool := ( FALSE => '0' , TRUE  => '1' );

	constant LP : integer := 8;
	constant L0 : integer := 2;
	constant L1 : integer := 5;

	type bool_dur is array(boolean) of integer;
	constant duration : bool_dur := ( FALSE => L0, TRUE => L1 );

begin

	-- Count ticks
	process(clk_200mhz)
	begin
		if rising_edge(clk_200mhz) then
			if ticks=199999 then
				ticks <= 0;
				tick_strobe <= '1';
			else
				ticks <= ticks + 1;
				tick_strobe <= '0';
			end if;
		end if;

	end process;

	-- Keep track of time
	process(clk_200mhz)
	begin
		if rising_edge(clk_200mhz) then
			if tick_strobe='1' then
				if ms=9 then
					ms <= 0;
				else
					ms <= ms + 1;
				end if;

				if ms=9 then
					if index=99 then
						index <= 0;
					else
						index <= index + 1;
					end if;
				end if;

				if ms=9 and index=99 then
					if sec1=9 then
						sec1 <= (others => '0');
					else
						sec1 <= sec1 + 1;
					end if;

					sbs <= sbs + 1;
				end if;

				if ms=9 and index=99 and sec1=9 then
					if sec10=5 then
						sec10 <= (others => '0');
					else
						sec10 <= sec10 + 1;
					end if;
				end if;

				if ms=9 and index=99 and sec1=9 and sec10=5 then
					if min10=5 and min1=9 then
						min10 <= (others => '0');
						min1 <= (others => '0');
					elsif min1=9 then
						min10 <= min10 + 1;
						min1 <= (others => '0');
					else
						min1 <= min1 + 1;
					end if;
				end if;

				if ms=9 and index=99 and sec1=9 and sec10=5 and min10=5 and min1=9 then
					if hour1=9 then
						hour1 <= (others => '0');
						hour10 <= hour10 + 1;
					elsif hour10=2 and hour1=3 then
						hour1 <= (others => '0');
						hour10 <= (others => '0');
					else
						hour1 <= hour1 + 1;
					end if;
				end if;

				if ms=9 and index=99 and sec1=9 and sec10=5 and min10=5 and min1=9 and hour1=3 and hour10=2 then
					if day1=9 and day10=9 then
						day1 <= (others => '0');
						day10 <= (others => '0');
						day100 <= day100 + 1;
					elsif day1=9 then
						day1 <= (others => '0');
						day10 <= day10 + 1;
					elsif day100=3 and day10=6 and day1=5 then
						day1 <= (0 => '1', others => '0');
						day10 <= (others => '0');
						day100 <= (others => '0');
					else
						day1 <= day1 + 1;
					end if;
				end if;

				if ms=9 and index=99 and sec1=9 and sec10=5 and min1=9 and min10=5 and hour1=3 and hour10=2 and day100=3 and day10=6 and day1=5 then
					if year10=9 and year1=9 then
						year10 <= (others => '0');
						year1 <= (others => '0');
					elsif year1=9 then
						year10 <= year10 + 1;
						year1 <= (others => '0');
					else
						year1 <= year1 + 1;
					end if;
				end if;
			end if;
		end if;
	end process;

	-- Convert time into an IRIG output signal
	out_process : process(clk_200mhz)
	begin
		if rising_edge(clk_200mhz) then

			-- Pipeline output
			ts_out <= dout;

			case index is
				when 00 => dout <= active_high(ms < LP);
				when 01 => dout <= active_high(ms < duration('1' = sec1(0)));
				when 02 => dout <= active_high(ms < duration('1' = sec1(1)));
				when 03 => dout <= active_high(ms < duration('1' = sec1(2)));
				when 04 => dout <= active_high(ms < duration('1' = sec1(3)));
				when 05 => dout <= active_high(ms < L0);
				when 06 => dout <= active_high(ms < duration('1' = sec10(0)));
				when 07 => dout <= active_high(ms < duration('1' = sec10(1)));
				when 08 => dout <= active_high(ms < duration('1' = sec10(2)));
				when 09 => dout <= active_high(ms < LP);
				when 10 => dout <= active_high(ms < duration('1' = min1(0)));
				when 11 => dout <= active_high(ms < duration('1' = min1(1)));
				when 12 => dout <= active_high(ms < duration('1' = min1(2)));
				when 13 => dout <= active_high(ms < duration('1' = min1(3)));
				when 14 => dout <= active_high(ms < L0);
				when 15 => dout <= active_high(ms < duration('1' = min10(0)));
				when 16 => dout <= active_high(ms < duration('1' = min10(1)));
				when 17 => dout <= active_high(ms < duration('1' = min10(2)));
				when 18 => dout <= active_high(ms < L0);
				when 19 => dout <= active_high(ms < LP);
				when 20 => dout <= active_high(ms < duration('1' = hour1(0)));
				when 21 => dout <= active_high(ms < duration('1' = hour1(1)));
				when 22 => dout <= active_high(ms < duration('1' = hour1(2)));
				when 23 => dout <= active_high(ms < duration('1' = hour1(3)));
				when 24 => dout <= active_high(ms < L0);
				when 25 => dout <= active_high(ms < duration('1' = hour10(0)));
				when 26 => dout <= active_high(ms < duration('1' = hour10(1)));
				when 27 => dout <= active_high(ms < L0);
				when 28 => dout <= active_high(ms < L0);
				when 29 => dout <= active_high(ms < LP);
				when 30 => dout <= active_high(ms < duration('1' = day1(0)));
				when 31 => dout <= active_high(ms < duration('1' = day1(1)));
				when 32 => dout <= active_high(ms < duration('1' = day1(2)));
				when 33 => dout <= active_high(ms < duration('1' = day1(3)));
				when 34 => dout <= active_high(ms < L0);
				when 35 => dout <= active_high(ms < duration('1' = day10(0)));
				when 36 => dout <= active_high(ms < duration('1' = day10(1)));
				when 37 => dout <= active_high(ms < duration('1' = day10(2)));
				when 38 => dout <= active_high(ms < duration('1' = day10(3)));
				when 39 => dout <= active_high(ms < LP);
				when 40 => dout <= active_high(ms < duration('1' = day100(0)));
				when 41 => dout <= active_high(ms < duration('1' = day100(1)));
				when 42 => dout <= active_high(ms < L0);
				when 43 => dout <= active_high(ms < L0);
				when 44 => dout <= active_high(ms < L0);
				when 45 => dout <= active_high(ms < L0);
				when 46 => dout <= active_high(ms < L0);
				when 47 => dout <= active_high(ms < L0);
				when 48 => dout <= active_high(ms < L0);
				when 49 => dout <= active_high(ms < LP);
				when 50 => dout <= active_high(ms < duration('1' = year1(0)));
				when 51 => dout <= active_high(ms < duration('1' = year1(1)));
				when 52 => dout <= active_high(ms < duration('1' = year1(2)));
				when 53 => dout <= active_high(ms < duration('1' = year1(3)));
				when 54 => dout <= active_high(ms < L0);
				when 55 => dout <= active_high(ms < duration('1' = year10(0)));
				when 56 => dout <= active_high(ms < duration('1' = year10(1)));
				when 57 => dout <= active_high(ms < duration('1' = year10(2)));
				when 58 => dout <= active_high(ms < duration('1' = year10(3)));
				when 59 => dout <= active_high(ms < LP);
				when 60 => dout <= active_high(ms < L0);
				when 61 => dout <= active_high(ms < L0);
				when 62 => dout <= active_high(ms < L0);
				when 63 => dout <= active_high(ms < L0);
				when 64 => dout <= active_high(ms < L0);
				when 65 => dout <= active_high(ms < L0);
				when 66 => dout <= active_high(ms < L0);
				when 67 => dout <= active_high(ms < L0);
				when 68 => dout <= active_high(ms < L0);
				when 69 => dout <= active_high(ms < LP);
				when 70 => dout <= active_high(ms < L0);
				when 71 => dout <= active_high(ms < L0);
				when 72 => dout <= active_high(ms < L0);
				when 73 => dout <= active_high(ms < L0);
				when 74 => dout <= active_high(ms < L0);
				when 75 => dout <= active_high(ms < L0);
				when 76 => dout <= active_high(ms < L0);
				when 77 => dout <= active_high(ms < L0);
				when 78 => dout <= active_high(ms < L0);
				when 79 => dout <= active_high(ms < LP);
				when 80 => dout <= active_high(ms < duration('1' = sbs(0)));
				when 81 => dout <= active_high(ms < duration('1' = sbs(1)));
				when 82 => dout <= active_high(ms < duration('1' = sbs(2)));
				when 83 => dout <= active_high(ms < duration('1' = sbs(3)));
				when 84 => dout <= active_high(ms < duration('1' = sbs(4)));
				when 85 => dout <= active_high(ms < duration('1' = sbs(5)));
				when 86 => dout <= active_high(ms < duration('1' = sbs(6)));
				when 87 => dout <= active_high(ms < duration('1' = sbs(7)));
				when 88 => dout <= active_high(ms < duration('1' = sbs(8)));
				when 89 => dout <= active_high(ms < LP);
				when 90 => dout <= active_high(ms < duration('1' = sbs(9)));
				when 91 => dout <= active_high(ms < duration('1' = sbs(10)));
				when 92 => dout <= active_high(ms < duration('1' = sbs(11)));
				when 93 => dout <= active_high(ms < duration('1' = sbs(12)));
				when 94 => dout <= active_high(ms < duration('1' = sbs(13)));
				when 95 => dout <= active_high(ms < duration('1' = sbs(14)));
				when 96 => dout <= active_high(ms < duration('1' = sbs(15)));
				when 97 => dout <= active_high(ms < duration('1' = sbs(16)));
				when 98 => dout <= active_high(ms < L0);
				when 99 => dout <= active_high(ms < LP);
				--when others => dout <= '0';
			end case;
		end if;
	end process;

end behav;
