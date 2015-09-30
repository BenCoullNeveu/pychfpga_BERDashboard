library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library unisim;
use unisim.vcomponents.all;

library work;
use work.icecore_package.irigb;

entity timestamp is
	port (
		clk		: in std_logic;
		clk_200mhz	: in std_logic;

		-- 200 MHz disciplined
		irig_bp, irig_sma : in std_logic;
		ts_out		: out irigb;
		timing_reset_200: out std_logic;
		calibration_out	: out std_logic;

		-- Control interface
		addr		: in unsigned(4 downto 0);
		din		: in std_logic_vector(31 downto 0);
		dout		: out std_logic_vector(31 downto 0);

		wreq		: in std_logic;
		wack		: out std_logic;
		rreq		: in std_logic;
		rack		: out std_logic
	);
end timestamp;

architecture behav of timestamp is

	attribute async_reg : string;
	attribute shreg_extract : string;

	-- IRIG-B encoder: replaces oddball "test mode"
	component irigb_encoder port(
		clk_200mhz : in std_logic;
		ts_out : out std_logic
	);
	end component;

	-- IRIG-B decoder
	component irigb_decoder port(
		clk_200mhz : in std_logic;
		irig : in std_logic_vector(0 to 3);
		source : in unsigned(1 downto 0);
		ts : out irigb
	);
	end component;

	signal irig_test : std_logic := '0';
	signal ts : irigb;

	-- We also need IRIG timestamps conditioned on the IPIF clock.
	signal ts_ipif_sync1, ts_ipif_sync2, ts_ipif_latched : irigb;
	attribute async_reg of ts_ipif_sync1, ts_ipif_sync2 : signal is "true";

	-- Control bits
	signal irig_source, irig_source_sync1, irig_source_sync2 : unsigned(1 downto 0) := "00";
	signal irig_sample : std_logic := '0';

	-- Timestamp buffers
	signal ts_irig_ctl_buf : std_logic_vector(95 downto 0);

	signal ts_comparator, ts_comparator_sync1, ts_comparator_sync2 : irigb;
	attribute async_reg of ts_comparator_sync1, ts_comparator_sync2 : signal is "true";

	-- Timestamp comparator; used for DMFD sync
	signal ts_comparator_en, ts_comparator_en_sync1, ts_comparator_en_sync2 : std_logic := '0';
	attribute async_reg of ts_comparator_en_sync1, ts_comparator_en_sync2 : signal is "true";
	signal ts_comparator_hold, ts_comparator_hold_sync1, ts_comparator_hold_sync2 : std_logic := '0';
	attribute async_reg of ts_comparator_hold_sync1, ts_comparator_hold_sync2 : signal is "true";
	signal y_gt, y_eq, d_gt, d_eq, h_gt, h_eq, m_gt, m_eq, s_gt, s_eq, ss_gt, ss_eq : std_logic := '0';

	signal timing_reset_200_pre2, timing_reset_200_pre1 : std_logic := '0';
	attribute shreg_extract of timing_reset_200_pre2, timing_reset_200_pre1 : signal is "no";

	signal timing_reset_force, timing_reset_force_sync1, timing_reset_force_sync2 : std_logic := '0';
	attribute async_reg of timing_reset_force_sync1, timing_reset_force_sync2 : signal is "true";

	signal irig_vect : std_logic_vector(0 to 3);
begin

	irig_vect <=  irig_bp & irig_test & irig_sma & '0'; -- Combine all irig signal source in a single vector

	enc : irigb_encoder port map (
		clk_200mhz => clk_200mhz,
		ts_out => irig_test
	);

	dec : irigb_decoder port map (
		clk_200mhz => clk_200mhz,
		irig => irig_vect,
		source => irig_source_sync2,
		ts => ts
	);

	--
	-- Calibration output. This is a square-wave with period 2 Hz,
	-- phase-aligned with IRIG-B output (i.e. it's just the seconds
	-- LSB.)
	--

	cal_out_proc : process(clk_200mhz)
	begin
		if rising_edge(clk_200mhz) then
			calibration_out <= ts.s(0);
		end if;
	end process;

	--
	-- Timestamp comparator.
	--

	timestamp_comparator_proc : process(clk_200mhz)
	begin
		if rising_edge(clk_200mhz) then

			ts_comparator_en_sync1 <= ts_comparator_en;
			ts_comparator_en_sync2 <= ts_comparator_en_sync1;

			ts_comparator_sync1 <= ts_comparator;
			ts_comparator_sync2 <= ts_comparator_sync1;

			irig_source_sync1 <= irig_source;
			irig_source_sync2 <= irig_source_sync1;

			timing_reset_force_sync1 <= timing_reset_force;
			timing_reset_force_sync2 <= timing_reset_force_sync1;

			--
			-- Timestamp comparison involves great honking big
			-- vectors, which we're doing a combination of
			-- equality testing and greater-than/less-than
			-- matching. Try some pipelining in the hopes it's
			-- less onerous.
			--

			(y_eq, d_eq, h_eq, m_eq, s_eq, ss_eq) <= std_logic_vector'(b"000000");
			(y_gt, d_gt, h_gt, m_gt, s_gt, ss_gt) <= std_logic_vector'(b"000000");

			if ts_comparator_sync2.y > ts.y then
				y_gt <= '1';
			end if;
			if ts_comparator_sync2.y = ts.y then
				y_eq <= '1';
			end if;

			if ts_comparator_sync2.d > ts.d then
				d_gt <= '1';
			end if;
			if ts_comparator_sync2.d = ts.d then
				d_eq <= '1';
			end if;

			if ts_comparator_sync2.h > ts.h then
				h_gt <= '1';
			end if;
			if ts_comparator_sync2.h = ts.h then
				h_eq <= '1';
			end if;

			if ts_comparator_sync2.m > ts.m then
				m_gt <= '1';
			end if;
			if ts_comparator_sync2.m = ts.m then
				m_eq <= '1';
			end if;

			if ts_comparator_sync2.s > ts.s then
				s_gt <= '1';
			end if;
			if ts_comparator_sync2.s = ts.s then
				s_eq <= '1';
			end if;

			if ts_comparator_sync2.ss > ts.ss then
				ss_gt <= '1';
			end if;
			if ts_comparator_sync2.ss = ts.ss then
				ss_eq <= '1';
			end if;

			-- Hold datapath in reset until the requested time rolls by.
			ts_comparator_hold <= '0';
			if ts.recent='1' and (
					(y_gt='1') or
					(y_eq='1' and d_gt='1') or
					(y_eq='1' and d_eq='1' and h_gt='1') or
					(y_eq='1' and d_eq='1' and h_eq='1' and m_gt='1') or
					(y_eq='1' and d_eq='1' and h_eq='1' and m_eq='1' and s_gt='1') or
					(y_eq='1' and d_eq='1' and h_eq='1' and m_eq='1' and s_eq='1' and ss_gt='1')) then

				ts_comparator_hold <= '1';
			end if;

			timing_reset_200_pre2 <= (ts_comparator_hold and ts_comparator_en_sync2) or timing_reset_force_sync2;
			timing_reset_200_pre1 <= timing_reset_200_pre2;
			timing_reset_200 <= timing_reset_200_pre1;

			ts_out <= ts;
		end if;
	end process;

	--
	-- Control interface
	--

	wack <= wreq;
	control_proc: process(clk)
	begin
		if rising_edge(clk) then

			-- Sample signals into IPIF clock domain
			ts_ipif_sync1 <= ts;
			ts_ipif_sync2 <= ts_ipif_sync1;
			irig_sample <= '0';
			if irig_sample='1' then
				ts_ipif_latched <= ts_ipif_sync2;
			end if;

			ts_comparator_hold_sync1 <= ts_comparator_hold;
			ts_comparator_hold_sync2 <= ts_comparator_hold_sync1;

			rack <= rreq;
			dout <= (others => '0');

			if wreq='1' then
				case to_integer(addr) is
					when 0 =>
						timing_reset_force <= din(5);
						ts_comparator_en <= din(3);
						irig_sample <= din(2);
						irig_source <= unsigned(din(1 downto 0));

					-- 9 to 14: timestamp comparator
					when 9 => ts_comparator.y <= unsigned(din(ts_comparator.y'range));
					when 10 => ts_comparator.d <= unsigned(din(ts_comparator.d'range));
					when 11 => ts_comparator.h <= unsigned(din(ts_comparator.h'range));
					when 12 => ts_comparator.m <= unsigned(din(ts_comparator.m'range));
					when 13 => ts_comparator.s <= unsigned(din(ts_comparator.s'range));
					when 14 => ts_comparator.ss <= unsigned(din(ts_comparator.ss'range));
					when others => -- nop
				end case;
			end if;

			if rreq='1' then
				case to_integer(addr) is
					when 0 =>
						dout(5) <= timing_reset_force;
						dout(4) <= ts_comparator_hold_sync2;
						dout(3) <= ts_comparator_en;
						--dout(2) <= '0'; -- IRIG sample flag
						dout(1 downto 0) <= std_logic_vector(irig_source);

					-- IRIG-B timestamp
					when 1 => dout(ts_ipif_latched.y'range) <= std_logic_vector(ts_ipif_latched.y);
					when 2 => dout(ts_ipif_latched.d'range) <= std_logic_vector(ts_ipif_latched.d);
					when 3 => dout(ts_ipif_latched.h'range) <= std_logic_vector(ts_ipif_latched.h);
					when 4 => dout(ts_ipif_latched.m'range) <= std_logic_vector(ts_ipif_latched.m);
					when 5 => dout(ts_ipif_latched.s'range) <= std_logic_vector(ts_ipif_latched.s);
					when 6 => dout(ts_ipif_latched.ss'range) <= std_logic_vector(ts_ipif_latched.ss);
					when 7 => -- sneak recent + source bits into control field
						dout(31) <= ts_ipif_latched.recent;
						dout(30 downto 29) <= std_logic_vector(ts_ipif_latched.source);
						dout(ts_ipif_latched.c'range) <= std_logic_vector(ts_ipif_latched.c);
					when 8 => dout(ts_ipif_latched.sbs'range) <= std_logic_vector(ts_ipif_latched.sbs);

					-- IRIG-B comparator
					when 9 => dout(ts_comparator.y'range) <= std_logic_vector(ts_comparator.y);
					when 10 => dout(ts_comparator.d'range) <= std_logic_vector(ts_comparator.d);
					when 11 => dout(ts_comparator.h'range) <= std_logic_vector(ts_comparator.h);
					when 12 => dout(ts_comparator.m'range) <= std_logic_vector(ts_comparator.m);
					when 13 => dout(ts_comparator.s'range) <= std_logic_vector(ts_comparator.s);
					when 14 => dout(ts_comparator.ss'range) <= std_logic_vector(ts_comparator.ss);

					when others => -- do nothing
				end case;
			end if;
		end if;
	end process;

end behav;
