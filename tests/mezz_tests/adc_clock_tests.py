#!/usr/bin/env python

import time
import asyncio
from pychfpga.fpga_array import FPGAArray

ICEBOARDS='496:1'
MDNS_TIMEOUT=60
STDERR_LOG_LEVEL='info'
MODE = 'shuffle16'


#arr = FPGAArray(iceboards=ICEBOARDS, mdns_timeout=MDNS_TIMEOUT, stderr_log_level=STDERR_LOG_LEVEL, mode=MODE)
#local_ib = arr.ib




async def power_cycle_ib_mezzanines(ib, off_time = 0):
    '''
    Turn off power to mezzanines, turn back on and initialize.
    '''
    m1 = ib.mezzanine[0].get(1)
    m2 = ib.mezzanine[0].get(2)

    # turn off power to mezzanines
    print('---------------------------------------------------------')
    print(f'Turning off power to {m1}, {m2} for {off_time} seconds')
    await m1.set_mezzanine_power_async(False)
    #await m1.set_mezzanine_reset_async(True)

    await m2.set_mezzanine_power_async(False)
    #await m2.set_mezzanine_reset_async(True)
    time.sleep(off_time) # in seconds

    # turn on power and configure pll
    print(f'Turning on power to {m1}, {m2} and configuring PLL')
    
    await m1.set_mezzanine_power_async(True)
    #time.sleep(1)
    await m1.init()
    
    await m2.set_mezzanine_power_async(True)
    #time.sleep(1)
    await m2.init()
    


def check_adc_freq(ib):
    '''
    1. Check ADC frequencies.
    2. Try pulsing the sync if clocks are missing
    3. Check ADC clocks again
    '''
#    ib[0].REFCLK.ADC_SYNC = 1
#    ib[0].REFCLK.ADC_SYNC = 0
#    time.sleep(1)
    
    freqs = [ib[0].FreqCtr.read_frequency(f'ADC_CLK{i}', gate_time=0.001) for i in (0,4,8,12)]
    err = any(abs(f-ib[0]._sampling_frequency/4) > 2.1e3 for f in freqs)

    if err:
        msg = f'ERROR: some ADCs are not generating a proper clock. Frequencies are {freqs} Hz.'
        print(msg)
        
        # pulse sync
        #ib[0].REFCLK.ADC_SYNC = 1
        #ib[0].REFCLK.ADC_SYNC = 0
        #ib[0].REFCLK.local_sync() 
        #ib.sync()
        #time.sleep(1)
        
        # check frequencies again
        #freqs = [ib[0].FreqCtr.read_frequency(f'ADC_CLK{i}', gate_time=0.001) for i in (0,4,8,12)]
        #err = any(abs(f-ib[0]._sampling_frequency/4) > 2.1e3 for f in freqs)
            
        #if err:
        #    msg = f'ERROR AFTER SYNC PULSE: some ADCs are not generating a proper clock. Frequencies are {freqs} Hz.'
        #    print(msg)
        #else:
        #    msg = f'ADC frequencies after sync pulse are {[f/1e6 for f in freqs]}'
        #    print(msg)
    else:
        msg = f'ADC frequencies are {[f/1e6 for f in freqs]}'
        print(msg)

    return msg, freqs


def check_adc_continuously(ib, check_duration = 5):
    '''
    Check ADC clock frequencies every minute for check_duration minutes.
    '''
    err_tags = []

    # check_duration is in minutes
    print(f'Checking ADC clock frequencies for {check_duration} minutes')
    
    if check_duration == 0:
        msg, freqs = check_adc_freq(ib)
        if 'ERROR' in msg:
            err_tags.append(msg)

    else:

        minutes_passed = 0
    
        while minutes_passed < check_duration:
        
            # wait a minute before checking freqs
            time.sleep(60)
            minutes_passed += 1
        
            print('---------------------------------')
            print(f'{minutes_passed} minutes passed')
            msg, freqs = check_adc_freq(ib) 
        
            if 'ERROR' in msg:
                err_tags.append(f'Minute {minutes_passed}: {msg}')

    return err_tags, freqs



async def test_power_cycle_mezz(ib, n_cycles = 50, check_time = 0, off_time = 0):
    '''
    Power cycle mezzanines, check frequencies for check_time minutes. 
    Repeat for n_cycles.
    '''
    err_tags = [] 
    err_ctr = 0
    
    for n in range(n_cycles):
        print('\n----------------------')
        print(f'Cycle {n+1}/{n_cycles}')
        print('----------------------')
        
        # record temperature before power-cycling mezz
        #time.sleep(0.5)
        #print(f'Pre-power-cycle temperature: {ib.get_temperatures()[0]}')        
        
        # power cycle mezzs
        await power_cycle_ib_mezzanines(ib, off_time)
        
        # check temp after
        time.sleep(1)
        #temps = ib.get_temperatures()[0]
        #print(f'Temperatures are now {temps}')
        
        # check frequencies
        errs, freqs = check_adc_continuously(ib, check_time)
        if errs:
            err_tags.append(f'Cycle {n+1}: {errs}')
            err_ctr += 1 
    
    print('\n*************************************************************************************************************************')
    print(f'{err_ctr}/{n_cycles} cycles failed.')
    print(f'Errors: {err_tags}')
    print('*************************************************************************************************************************')

    return err_tags, freqs

#asyncio.run(test_power_cycle_mezz(ib=local_ib, n_cycles = 100, off_time = 10))




async def test_reprogram_power_cycle(ib, n_fpga_cycles = 5, n_mezz_cycles = 50, cool_down = 10):
    '''
    1.  Re-program FPGA
    2.  Power cycle mezzanine and check ADC frequencies for n_mezz_cycles
    3.  Repeat steps 1 and 2 for n_fpga_cycles
    '''
    err_tags = []
    
    for n in range(n_fpga_cycles):
        
        # store serial number and virtual slot number in a string
        ib_string = f'MGK7MB {ib.serial[0]}:1'  
        
        print('\n\n*****************************')
        print(f'Cycle {n+1}/{n_fpga_cycles}')
        print('*****************************')
        print('Reprogramming FPGA')
        
        ib = FPGAArray(iceboards = ib_string, mode = 'shuffle16', mdns_timeout = 60, stderr_log_level = 'info').ib
        ib[0].REFCLK.ADC_SYNC = 1
        ib[0].REFCLK.ADC_SYNC = 0
        await asyncio.sleep(0.5)

        if n_mezz_cycles != 0:
            errs, freqs = await test_power_cycle_mezz(ib, n_cycles = n_mezz_cycles)
        else:
            errs, freqs = check_adc_freq(ib)
            if 'ERROR' not in errs:
                errs = []
            
        if errs:
            err_tags.append(f'Reprogramming cycle {n+1}: {len(errs)} errors. Latest improper frequency recorded is {freqs}')
        
        time.sleep(cool_down)

    #if err_tags:
    print(err_tags)
    
    return err_tags, freqs

#asyncio.run(test_reprogram_power_cycle(ib = local_ib, n_mezz_cycles = 0, n_fpga_cycles = 100))





async def test_sync_delays(ib, sync_delays=8, n_mezz_cycles=50):
    '''
    1. Set sync delay
    2. Power-cycle mezzanines for n_mezz_cycles
    3. Repeat for sync delay values 0-sync_delay
    '''
    # tally errors per delay value
    err_tags = []
    for delay in range(sync_delays):
        
        print('\n\n\n*****************************')
        print(f'SYNC DELAY = {delay}')
        print('*****************************')
        
        ib.set_sync_delays((delay, delay))
        err_msgs, freqs = await test_power_cycle_mezz(ib, n_cycles = n_mezz_cycles)
        err_tags.append(f'Delay = {delay}: {len(err_msgs)} errors')
    
    for err in err_tags: print(err)
    return err_tags

#asyncio.run(test_sync_delays(ib = local_ib, sync_delays = 16, n_mezz_cycles = 100))



def test_sync_pulse(ib, n_cycles = 1000):
    
    for n in range(n_cycles):
        print('-------------------------')
        print(f'Cycle {n+1}/{n_cycles}')
        print('-------------------------')
        #ib[0].REFCLK.ADC_SYNC = 1
        #ib[0].REFCLK.ADC_SYNC = 0
        #ib[0].REFCLK.remote_sync()
        #ib[0].REFCLK.local_sync()
        #time.sleep(1)
        ib.sync()
        ib.check_adc_frequencies(0)
    print('\n*************************************************************')
    print(f'There are {ib.adc_clk_err_ctr} errors: {ib.adc_clk_err_msgs}')    
    print('**************************************************************')
    return ib.adc_clk_err_msgs, ib.adc_clk_err_ctr

#test_sync_pulse(local_ib)

