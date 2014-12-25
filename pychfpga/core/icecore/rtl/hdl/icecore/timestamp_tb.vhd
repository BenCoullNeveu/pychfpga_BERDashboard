library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

use work.dfmux_package.irigb;

ENTITY timestamp_tb IS
END timestamp_tb;

ARCHITECTURE behav OF timestamp_tb IS 

	component timestamp is port (
		clk		: in std_logic;
		clk_200mhz	: in std_logic;

		-- 200 MHz disciplined
		irig_ser	: in std_logic;
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
	end component;

	signal clk, clk_200mhz : std_logic := '0';

	signal ts : irigb;

	signal timing_reset_200, calibration_out : std_logic;

	signal addr : unsigned(4 downto 0);
	signal din, dout : std_logic_vector(31 downto 0);
	signal wreq, wack, rreq, rack : std_logic := '0';

	signal ipif_ticks : integer := 0;

begin

	--
	-- Clock processes
	--

	PROCESS
	BEGIN
		clk_200mhz <= '0';
		wait for 2.5 ns;
		clk_200mhz <= '1';
		wait for 2.5 ns;
	END PROCESS;

	PROCESS
	BEGIN
		clk <= '0';
		wait for 4 ns;
		clk <= '1';
		wait for 4 ns;
	END PROCESS;

	dut : timestamp port map (
		clk => clk,
		clk_200mhz => clk_200mhz,

		irig_ser => '0',
		ts_out => ts,
		timing_reset_200 => timing_reset_200,
		calibration_out => calibration_out,

		addr => addr,
		din => din,
		dout => dout,
		wreq => wreq,
		wack => wack,
		rreq => rreq,
		rack => rack
	);

	bus_proc : process(clk)
	begin
		if rising_edge(clk) then

			ipif_ticks <= ipif_ticks + 1;

			rreq <= '0';
			wreq <= '0';
			din <= (others => '0');

			case ipif_ticks is
				when 10 =>
					wreq <= '1';
					din <= x"00000001";
				when others => -- nop
			end case;

			assert rack='0' report "Read acknowledge: "
				& integer'image(to_integer(unsigned(dout)));
			assert wack='0' report "Write acknowledge";
		end if;
	end process;
END;
