""" MDNS hardware discovery
"""

# Standard library
import logging
import functools  # Used in iceboard discovery
import time  # Used in iceboard discovery
import socket  # used in iceboard discovery (itoa())
import asyncio
import threading

# PyPI packages
from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf

# Local packages
from . import Motherboard, IceCrate

def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

def _get_txt_field(tr, key):
    value = tr.get(key.encode('ascii'), None)
    if isinstance(value, bytes):
        value = value.decode('utf-8')
    return value

def match(target, value):
    return target == '*' or target == value

def tuple_match(target, value):
    return match(target[0], value[0]) and match (target[1], value[1])

class ThreadData:
    def __init__(self,**kwargs):
        self._lock = threading.RLock()
        self.__dict__.update(kwargs)
    def __enter__(self):
        self._lock.acquire()
        return self
    def __exit__(self, type, value, traceback):
        self._lock.release()

async def mdns_discover(
    icecrates=None,
    iceboards=None,
    timeout=None,
    inter_reply_timeout=None,
    clear_hwm=False):
    """ Automatically detect IceBoards and IceCrates on the network using mDNS
    and add them to the hardware map.

    Parameters:

        icecrates (list): List of icecrates whose IceBoards we want to add to the hardware map. It can contain:

                [(model1, serial1), (model2, serial2), ...]: Matches specific
                model and serial number. model can be "*" to match any
                mmodel. serial can be "*" to match any serial. serial can be
                a string or an integer.

                "*" is equivalent to [('*', '*')]  : matches any crate model
                and serial, i.e. all discovered Iceboards from all crates
                are added.

                None or an empty list: no iceboard are added on a crate
                membership basis.


        iceboards (list):  List of iceboards we want to add to the hardware map.

                [(model1, serial1), (model2, serial2), ...]: Matches specific
                model and serial number. model can be "*" to match any
                mmodel. serial can be "*" to match any serial. serial can be
                a string or an integer.

                "*" is equivalent to [('*', '*')]  : matches any iceboard model
                and serial, i.e. all discovered Iceboards from all crates
                are added.

                None or an empty list: no iceboard are added on a crate
                membership basis.

        timeout (float): Maximum amount of time (in seconds) to wait for mDNS replies. 

        inter_reply_timeout (int or float): If non-zero, mDNS search will stop
            when the delay since the last reply  exceeds inter_reply_timeout
            (in seconds). Can be used to shorten the search if we expect the
            replies to come in a burst after some long delay. The search will
            still stop after `timeout` even if the burst has started. This feature is disabled if `inter_reply_timeout` is `None`.



    """
    logger = logging.getLogger(__name__)

    if clear_hwm:
        Motherboard.clear_hardware_map()

    # Normalize iceboard and icecrate target lists to the [ (model,[serial1, serial2]), ...] format
    if iceboards == '*':
        iceboards = [('*', '*')]
    if icecrates == '*':
        icecrates = [('*', '*')]
    # List of explicitely-specified (non-wildcard) boards and crates
    expected_ibs = {(model, serial):None for model, serial in iceboards if model != "*" and serial != "*"}
    expected_ics = {(model, serial):None for model, serial in icecrates if model != "*" and serial != "*"}
    # Check if we expect an open-ended number of boards or crates
    wild_ibs = [(model, serial) for model, serial in iceboards if model == "*" or serial == "*"]
    wild_ics = [(model, serial) for model, serial in icecrates if model == "*" or serial == "*"]

    logger.debug(f'looking for ib={iceboards}, ic={icecrates}')
    t0 = time.time()
    time_info = ThreadData(t0=t0, last_time=t0, dt_max=0, n=0)

    def on_service_state_change(zeroconf: Zeroconf, service_type: str,
                                name: str, state_change: ServiceStateChange,
                                time_info=time_info) -> None:
        # print("Service %s of type %s state changed: %s" % (name, service_type, state_change))

        if state_change is not ServiceStateChange.Added:
            return
        info = zeroconf.get_service_info(service_type, name)
        # print("Info from zeroconf.get_service_info: %r" % (info))
        if not info:
            return
        # print(f"mdns: info= {info}, v4={info.addresses_by_version(version=IPVersion.V4Only)}")
        addr = socket.inet_ntop(socket.AF_INET, info.addresses_by_version(version=IPVersion.V4Only)[0])
        port = info.port
        # print(f"  Address: {addr}:{port}")
        # print("  Weight: %d, priority: %d" % (info.weight, info.priority))
        # print("  Server: %s" % (info.server,))
        tr = info.properties

        ib_serial = _get_txt_field(tr, 'motherboard-serial')
        ib_part_number = _get_txt_field(tr, 'motherboard-part')
        bp_slot = _get_txt_field(tr, 'backplane-slot')
        bp_part_number = _get_txt_field(tr, 'backplane-part')
        bp_serial = _get_txt_field(tr, 'backplane-serial')
        # find the integer representation of the serial number if possible, in case the user specified them that way
        int_bp_serial = _to_int(bp_serial)
        int_ib_serial = _to_int(ib_serial)
        slot = _to_int(bp_slot)

        logger.debug(f"DNS-SD: Discovered motherboard {ib_part_number} SN{ib_serial} ({addr}) in "
                     f"IceCrate {bp_part_number} SN{bp_serial}  slot {bp_slot}.")

        # Check if the motherboard matches the search criteria
        iceboard_match = ib_part_number and ib_serial and any(
            match(target_model, ib_part_number)
            and (match(target_serial, ib_serial) or match(target_serial, int_ib_serial))
            for target_model, target_serial in iceboards)

        # Check if the backplane matches the search criteria
        icecrate_match = bp_part_number and bp_serial and any(
            match(target_model, bp_part_number)
            and (match(target_serial, bp_serial) or match(target_serial, int_bp_serial))
            for target_model, target_serial in icecrates)

        if icecrate_match or iceboard_match:
            if ib_part_number and ib_serial:
                ib_cls = Motherboard.get_class_by_ipmi_part_number(ib_part_number)
                ib_obj = ib_cls.get_unique_instance(serial=ib_serial, hostname=addr)
                # print(f'ib obj {ib_obj} has hostnme {ib_obj.hostname}')
                for tib in expected_ibs:
                    if tuple_match(tib, (ib_part_number, ib_serial)):
                        expected_ibs[tib] = True
            # Add the backplane if it does not already exist
            if bp_part_number and bp_serial:
                bp_cls = IceCrate.get_class_by_ipmi_part_number(bp_part_number)
                crate_number = ib_obj.crate.crate_number if ib_obj.crate else None
                bp_obj = bp_cls.get_unique_instance(new_class=bp_cls, serial=bp_serial, crate_number =crate_number)
                ib_obj.update_instance(crate=bp_obj, slot=slot)
                for tib in expected_ics:
                    if tuple_match(tib, (bp_part_number, bp_serial)):
                        expected_ics[tib] = bp_obj
        else:
            logger.debug(
                f"DNS-SD: Motherboard {ib_part_number} SN{ib_serial} (crate {bp_part_number} SN{bp_serial} slot {bp_slot}) was detected "
                f"but was not added because it did not match the motherboard serial {iceboards} "
                f"or crate serial {icecrates}")
        t = time.time()
        with time_info as ti:
            ti.dt_max = max(ti.dt_max, t - ti.last_time)
            ti.last_time = t
            ti.n += 1
    try:
        zeroconf = Zeroconf(
            ip_version=IPVersion.V4Only,
            #interfaces=['10.10.10.83'],
            unicast=True  # seems to prevent ICMP error on replies, but might just be luck
            )
        browser = ServiceBrowser(
            zeroconf,
            '_tuber-jsonrpc._tcp.local.',
            handlers=[on_service_state_change],
            # addr=_MDNS_ADDR,
            delay=100 #ms
            )
        last_msg_time = None
        while True:
            t = time.time()
            found_all_iceboards = not expected_ibs or all(expected_ibs.values())
            found_all_slots = not expected_ics or all(ic and len(ic.slot)==ic.NUMBER_OF_SLOTS for ic in expected_ics.values())
            if not wild_ibs and not wild_ics and found_all_iceboards and found_all_slots:
                logger.info('DNS-SD: All the boards and/or crates that were requested were found. Stopping the search')
                break
            with time_info as ti:
                if last_msg_time is None or t - last_msg_time > 1:
                    logger.info(f'mDNS searching: elapsed={t-t0:.1f}, elapsed since last time={t-ti.last_time:.1f}, dt_max={ti.dt_max}, n={ti.n}, last_time={ti.last_time}')
                    last_msg_time = t
                if (timeout and t - t0 > timeout):
                    break
                if inter_reply_timeout and ti.n and t-ti.last_time > inter_reply_timeout:
                    break
            await asyncio.sleep(.1)
    except BaseException as e:
        logger.error(f'mdns_discover: got the exception {e}')
        raise
    finally:
        logger.debug(f'mdns_discover: closing zeroconf')
        zeroconf.close()
    return Motherboard.get_all_instances(), IceCrate.get_all_instances()


def mdns_resolve(name, timeout=1):
    """
    Return the IP address for the specified name by issuing a mDNS query directly.

    Parameters:

        name (str): Host name to lookup. Normally ends with ".local" or
            ".local.". Thhe '.local' will be added automatically if missing.

        timeout (float): time to wait for an answer, in seconds. The function will return
            as soon as there is an answer. mDNS devices are not obligated to
            respond more than once a second, so setting a value less than 1
            might cause a timeout if the device had just been queried by some
            other system.

    Returns:
        IPV4 address as a str; None if not found

    """
    if name.lower().endswith('local'):
        name += '.'
    if not name.lower().endswith('.local.'):
        name += '.local.'
    zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
    info = zeroconf.get_service_info('.local.', name, timeout=timeout * 1000)
    # print('found', info)
    zeroconf.close()
    if info:
        ips = info.addresses_by_version(version=IPVersion.V4Only)
        if ips:
            return socket.inet_ntop(socket.AF_INET, ips[0])
    else:
        return None

def test():
    logging.basicConfig(level=logging.DEBUG)
    Motherboard.clear_hardware_map()
    ibs, ics = asyncio.run(mdns_discover(iceboards='*', icecrates='*', timeout=5))
    for ib in sorted(ibs, key=lambda ib:ib.slot):
        if ib.crate:
            crate_txt = f' in slot {ib.slot:2d} of crate {ib.crate.part_number}_SN{ib.crate.serial}'
        else:
            crate_txt = f' (standalone board in virtual slot {ib.slot})'
        print(f'Motherboard {ib.part_number}_SN{ib.serial} @ {ib.hostname}' + crate_txt)