library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity arm_spi is port (
	clk : in std_logic;
	reset : in std_logic;

	sck : in std_logic;
	miso : out std_logic;
	mosi : in std_logic;
	cs_n : in std_logic;

	addr : out std_logic_vector(31 downto 0);
	din : in std_logic_vector(31 downto 0);
	dout : out std_logic_vector(31 downto 0);
	wreq, rreq : out std_logic;
	wack, rack : in std_logic
);
end arm_spi;

architecture behav of arm_spi is

	-- Shift registers
	signal sck_dly : std_logic_vector(1 to 3) := (others => '0');
	signal sck_rising, sck_falling : std_logic := '0';

	signal mosi_dly : std_logic := '0';

	signal mosi_shreg, miso_shreg, miso_shreg_in : std_logic_vector(7 downto 0) := (others => '0');
	signal mosi_shreg_count, miso_shreg_count : unsigned(2 downto 0) := (others => '0');
	signal mosi_shreg_strobe, miso_shreg_strobe, miso_shreg_ld : std_logic := '0';

	-- If we trigger a new output word before SCK has fallen, we need
	-- to inhibit the first output shift (so we don't swallow a bit.)
	signal suppress_shift : std_logic := '0';

	-- Byte-wide state machine
	type SPI_STATE_TYPE is (
		SPI_IDLE,
		SPI_A1, SPI_A2, SPI_A3, SPI_A4,
		SPI_RW, SPI_R1, SPI_R2, SPI_R3,
		SPI_W1, SPI_W2, SPI_W3, SPI_W4
	);
	signal spi_state : SPI_STATE_TYPE := SPI_IDLE;

	signal din_latched : std_logic_vector(31 downto 8) := (others => '0');
	signal op : std_logic_vector(1 downto 0) := "00";

begin

	miso <= miso_shreg(7);

	shreg_proc : process(clk)
	begin
		if rising_edge(clk) then

			sck_dly <= sck & sck_dly(1 to sck_dly'high-1);
			mosi_dly <= mosi;
			mosi_shreg_strobe <= '0';
			miso_shreg_strobe <= '0';

			if reset='1' or cs_n='1' then
				-- Idle state; everything held in
				-- reset.
				mosi_shreg <= (others => '0');
				miso_shreg <= (others => '0');
				mosi_shreg_count <= (others => '0');
				miso_shreg_count <= (others => '0');
				suppress_shift <= '0';
			else
				-- On rising clock edges, sample MOSI. Strobe when
				-- a new byte is fully ready.
				if sck_dly="100" then
					mosi_shreg <= mosi_shreg(6 downto 0) & mosi_dly;
					mosi_shreg_count <= mosi_shreg_count + 1;
					
					if mosi_shreg_count=7 then
						mosi_shreg_strobe <= '1';
					end if;
				end if;

				if miso_shreg_ld='1' then
					-- Load when commanded.
					miso_shreg <= miso_shreg_in;
					miso_shreg_count <= (others => '1');

					-- If the next sck edge is falling, make sure we
					-- don't swallow the MSB by accident.
					if sck_dly(1)='1' then
							suppress_shift <= '1';
					else
							suppress_shift <= '0';
					end if;

				elsif sck_dly="011" then
					-- On falling clock edges, update MISO.
					suppress_shift <= '0';
					if suppress_shift='0' then
						miso_shreg <= miso_shreg(6 downto 0) & '0';
						miso_shreg_count <= miso_shreg_count - 1;
						if miso_shreg_count=0 then
							-- Strobe when a byte has fully shifted out.
							miso_shreg_strobe <= '1';
						end if;
					end if;
				end if;
			end if;

		end if;
	end process;

	state_proc : process(clk)
	begin
		if rising_edge(clk) then

			rreq <= '0';
			wreq <= '0';

			miso_shreg_ld <= '0';

			if reset='1' or cs_n='1' then
				spi_state <= SPI_IDLE;
				addr <= (others => '0');
				dout <= (others => '0');
			else

				case spi_state is
					when SPI_IDLE =>
						if mosi_shreg_strobe='1' then
							addr(7 downto 0) <= mosi_shreg(7 downto 2) & "00";
							op <= mosi_shreg(1 downto 0);
							spi_state <= SPI_A1;
						end if;
					when SPI_A1 =>
						if mosi_shreg_strobe='1' then
							addr(15 downto 8) <= mosi_shreg;
							spi_state <= SPI_A2;
						end if;
					when SPI_A2 =>
						if mosi_shreg_strobe='1' then
							addr(23 downto 16) <= mosi_shreg;
							spi_state <= SPI_A3;
						end if;
					when SPI_A3 =>
						-- Here, we've latched the entire address. We
						-- diverge depending on the operation: for reads,
						-- we need to dispatch them immediately.
						if mosi_shreg_strobe='1' then
							addr(31 downto 24) <= mosi_shreg;

							case op is
								when "00" => -- read! Dispatch immediately.
									rreq <= '1';
									spi_state <= SPI_RW;

								when "01" => -- write
									spi_state <= SPI_W1;

								when others => -- eek!
									spi_state <= SPI_IDLE;
							end case;
						end if;

					--
					-- Reads
					--
					when SPI_RW =>
						-- TODO: add read timeout
						if rack='1' then
							din_latched <= din(din_latched'range);
							miso_shreg_in <= din(7 downto 0);
							miso_shreg_ld <= '1';
							spi_state <= SPI_R1;
						end if;
					when SPI_R1 =>
						if miso_shreg_strobe='1' then
							miso_shreg_in <= din_latched(15 downto 8);
							miso_shreg_ld <= '1';
							spi_state <= SPI_R2;
						end if;
					when SPI_R2 =>
						if miso_shreg_strobe='1' then
							miso_shreg_in <= din_latched(23 downto 16);
							miso_shreg_ld <= '1';
							spi_state <= SPI_R3;
						end if;
					when SPI_R3 =>
						if miso_shreg_strobe='1' then
							miso_shreg_in <= din_latched(31 downto 24);
							miso_shreg_ld <= '1';
							spi_state <= SPI_IDLE;
						end if;

					--
					-- Writes
					--
					when SPI_W1 =>
						if mosi_shreg_strobe='1' then
							dout(7 downto 0) <= mosi_shreg;
							spi_state <= SPI_W2;
						end if;
					when SPI_W2 =>
						if mosi_shreg_strobe='1' then
							dout(15 downto 8) <= mosi_shreg;
							spi_state <= SPI_W3;
						end if;
					when SPI_W3 =>
						if mosi_shreg_strobe='1' then
							dout(23 downto 16) <= mosi_shreg;
							spi_state <= SPI_W4;
						end if;
					when SPI_W4 =>
						-- Dispatch the write. TODO: timeouts and
						-- listen for wack?
						if mosi_shreg_strobe='1' then
							dout(31 downto 24) <= mosi_shreg;
							wreq <= '1';
							spi_state <= SPI_IDLE;
						end if;

					when others =>
						spi_state <= SPI_IDLE;
				end case;
			end if;
		end if;
	end process;
end behav;

-- vim: ts=4 sts=4
