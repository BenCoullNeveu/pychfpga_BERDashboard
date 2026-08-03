async def power_cycle_mezz(m):
	await m.set_mezzanine_power_async(False)
	await m.set_mezzanine_power_async(True)
	m.IOExpander.init()
	m.ADC_PLL.init()

async def test_mezz_power_cycle(i, mezz=1):
	m = i.mezzanine[mezz]
	r=i.REFCLK
	clk_name = f'ADC_CLK{(mezz-1)*4}'
	r.ADC_SYNC = 1
	await power_cycle_mezz(m)
	r.ADC_SYNC = 0
	f=[i.FreqCtr.read_frequency(f'ADC_CLK{n}', 0.01) for n in (0,4,8,12)]
	print(f'{clk_name}={f}')

