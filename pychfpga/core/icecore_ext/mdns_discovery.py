""" MDNS hardware discovery
"""

# Standard library
import logging
import functools  # Used in iceboard discovery
import time  # Used in iceboard discovery
import socket  # used in iceboard discovery (itoa())
import asyncio


# PyPI packages
from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf

# Local packages
from . import IceBoard, IceCrate

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

async def mdns_discover(icecrates=None, iceboards=None, timeout=None, clear_hardware_map=False):
    """ Automatically detect IceBoards and IceCrates on the network using mDNS
    and update hardware map ``hwm`` accordingly.

    If no hardware map is provided, a new empty one is created. This can be
    used to query and further filter the discovered objects before adding them
    to a final hardware map.

    Parameters:

        icecrates: If ``icecrates`` is specified,  all the IceBoards that
            are on crates having the model number and serial number listed in
            ``icecrates`` are selected.

            ''icecrates''   can be in the format

                [(model1, [serial1, serial2 ...]), (model2, [serial3, serial4, ...]), ...]

                [(model1, serial1), (model2, serial2), ...]

                [serial1, serial2, ...] # will match any crate model

                "*" # will match any crate


            If ``icecrates`` is None or an empty list, no crate is added.

            If ``icecrates='*'``, all discovered Iceboards from all crates are added.

        iceboards:  If ``iceboards`` is specified,  all the IceBoards with the
            serial number found in the ``iceboards`` list are selected. If
            None or an empty list, no board is added. If ``iceboards='*'``,
            all discovered Iceboards are added.
    """
    logger = logging.getLogger(__name__)

    if clear_hardware_map:
        IceBoard.clear_hardware_map()

    # Normalize iceboard and icecrate target lists to the [ (model,[serial1, serial2]), ...] format
    if isinstance(iceboards, str): # include '*'
        iceboards = [('*', [iceboards])]
    iceboards = [entry if isinstance(entry, (list, tuple)) else ('*', [entry]) for entry in iceboards or []]
    iceboards = [(model, serials if isinstance(serials, (list, tuple)) else [serials]) for model, serials in iceboards]

    if isinstance(icecrates, str): # include '*'
        icecrates = [('*', [icecrates])]
    icecrates = [entry if isinstance(entry, (list, tuple)) else ('*', [entry]) for entry in icecrates or []]
    icecrates = [(model, serials if isinstance(serials, (list, tuple)) else [serials]) for model, serials in icecrates]

    t0 = time.time()
    time_info = dict(last_time=t0, dt_max=0)

    def on_service_state_change(zeroconf: Zeroconf, service_type: str,
                                name: str, state_change: ServiceStateChange, time_info=time_info) -> None:
        # print("Service %s of type %s state changed: %s" % (name, service_type, state_change))

        if state_change is not ServiceStateChange.Added:
            return
        info = zeroconf.get_service_info(service_type, name)
        # print("Info from zeroconf.get_service_info: %r" % (info))
        if not info:
            return
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

        logger.debug(f"DNS-SD: Discovered IceBoard SN{ib_serial} ({addr}) in "
                     f"IceCrate {bp_part_number} SN{bp_serial}  slot {bp_slot}.")

        # Check if the motherboard matches the search criteria
        iceboard_match = ib_part_number and ib_serial and any(
            (target_model == '*' or ib_part_number == target_model) and
            ('*' in target_serials or ib_serial in target_serials or int_ib_serial in target_serials)
            for target_model, target_serials in iceboards)

        # Check if the backplane matches the search criteria
        icecrate_match = bp_part_number and bp_serial and any(
            (target_model == '*' or bp_part_number == target_model) and
            ('*' in target_serials or bp_serial in target_serials or int_bp_serial in target_serials)
            for target_model, target_serials in icecrates)

        if icecrate_match or iceboard_match:
            if ib_part_number and ib_serial:
                # ib_cls = IceBoard.get_class_by_ipmi_part_number(ib_part_number)
                ib_obj = IceBoard.get_unique_instance(serial=ib_serial, hostname=addr)
                # print(f'ib obj {ib_obj} has hostnme {ib_obj.hostname}')

            # Add the backplane if it does not already exist
            if bp_part_number and bp_serial:
                bp_cls = IceCrate.get_class_by_ipmi_part_number(bp_part_number)
                bp_obj = bp_cls.get_unique_instance(serial=bp_serial)
                if slot:
                    ib_obj.update_instance(crate=bp_obj, slot=slot)
        else:
            logger.debug(
                f"DNS-SD: IceBoard SN{ib_serial} (crate {bp_part_number} SN{bp_serial} slot {bp_slot}) was detected "
                f"but was not added because it did not match the IceBoard serial {iceboards} "
                f"or crate serial {icecrates}")
        t = time.time()
        time_info['dt_max'] = max(time_info['dt_max'], t - time_info['last_time'])
        time_info['last_time'] = t

    zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
    services = ["_tuber-jsonrpc._tcp.local."]
    browser = ServiceBrowser(zeroconf, services, handlers=[on_service_state_change])
    try:
        while True:
            print(f'{time_info}')
            t = time.time()
            if (timeout and t - t0 > timeout) or (not timeout and time_info['dt_max'] and (t-time_info['last_time'] > 10 * time_info['dt_max'])):
                break
            await asyncio.sleep(.1)
    finally:
        zeroconf.close()
    return IceBoard.get_all_instances(), IceCrate.get_all_instances()


def test():
    logging.basicConfig(level=logging.DEBUG)
    IceBoard.clear_hardware_map()
    ibs, ics = asyncio.run(mdns_discover(iceboards='*', icecrates='*', timeout=5))
    for ib in sorted(ibs, key=lambda ib:ib.slot):
        if ib.crate:
            crate_txt = f' in slot {ib.slot:2d} of crate {ib.crate.part_number}_SN{ib.crate.serial}'
        else:
            crate_txt = f' (standalone board in virtual slot {ib.slot})'
        print(f'IceBoard {ib.part_number}_SN{ib.serial} @ {ib.hostname}' + crate_txt)