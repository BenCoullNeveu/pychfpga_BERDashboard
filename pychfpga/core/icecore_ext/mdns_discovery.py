""" MDNS hardware discovery support
"""
import logging
import functools  # Used in iceboard discovery
# import tornado  # Used in iceboard discovery
import time  # Used in iceboard discovery
import socket  # used in iceboard discovery (itoa())

# from .async import async, async_return, async_moment
from .hardware_map import HardwareMap
from . import IceBoard, FMCMezzanine, IceCrate
# from .hwm_assets import IceBoard, IceBoardHandler, FMCMezzanine, IceCrate, IceCrateHandler

def mdns_discover(hwm=None, icecrates=None, iceboards=None, timeout=5, resolve_ip=True):
    """ Automatically detect IceBoards and IceCrates on the network using mDNS
    and update hardware map ``hwm`` accordingly.

    If no hardware map is provided, a new empty one is created. This can be
    used to query and further filter the discovered objects before adding them
    to a final hardware map.

    Parameters:

        hwm: (obsolete)

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

        resolve_ip (bool): If 'resolve_ip' is True, the hostname published by
            mDNS (e.g. iceboard0007.local) is resolved into its associated IP
            address. This accelerates Tuber accesses since every Tuber call
            does not have to resolve it on every tuber call (this is
            especially needed on Windows).
    """
    import pybonjour  # only needed here, and not always installed


    if hwm is None:
        hwm = HardwareMap()

    # if isinstance(icecrates, (str, int):
    #     icecrates = [icecrates]

    # if isinstance(iceboards, str):
    #     iceboards = [iceboards]

    logger = logging.getLogger(__name__)
    fds = []

    # Create a local, captive IOLoop. We use this to epoll() on
    # Bonjour file descriptors.
    io_loop = tornado.ioloop.IOLoop()

    # Normalize iceboard and icecrate target lists to the [ (model,[serial1, serial2]), ...] format
    if isinstance(iceboards, str): # include '*'
        iceboards = [('*', [iceboards])]
    iceboards = [entry if isinstance(entry, (list, tuple)) else ('*', [entry]) for entry in iceboards]
    iceboards = [(model, serials if isinstance(serials, (list, tuple)) else [serials]) for model, serials in iceboards]

    if isinstance(icecrates, str): # include '*'
        icecrates = [('*', [icecrates])]
    icecrates = [entry if isinstance(entry, (list, tuple)) else ('*', [entry]) for entry in icecrates]
    icecrates = [(model, serials if isinstance(serials, (list, tuple)) else [serials]) for model, serials in icecrates]

    def add_mdns_process(ref):
        """ Add a handler to the IOLoop that will be polled until the mDNS
        process `ref` file descriptor has data to process. The data is then
        processed with DNSServiceProcessResult() which calls the callback
        registered with that process is called.

        The mDNS process reference `ref` is also added to a list so it can be
        closed properly when discovery is complete.
        """
        fds.append(ref)
        io_loop.add_handler(
            ref.fileno(),
            lambda fd, events: pybonjour.DNSServiceProcessResult(ref),
            io_loop.READ)

    def close_mdns_processes():
        """Close all mDNS processs that have been opened during discovery.
        """
        for fd in fds:
            fd.close()

    def add_object(iface, host, txtRecord):
        """ Add iceboard and icecrate object to the hardware map if it matches the search criteria.

        """

        # Parse TXT records. That's where the IceBoard publishes data.
        tr = pybonjour.TXTRecord.parse(txtRecord)

        # Check if the required TXT motherboard serial and model fields exist, otherwise punt
        if 'motherboard-serial' not in tr or 'motherboard-part' not in tr:
            logger.warning("DNS-SD: IceBoard at %s was discovered but cannot be added to the hardware map because it does not publish a serial number" % (host))
            return
        ib_serial = tr['motherboard-serial']
        ib_part_number = tr['motherboard-part']

        # If a motherboard with the same serial is already in the hardware map, exit.
        existing_ib = [ib for ib in hwm.query(IceBoardPlus) if ib.serial == ib_serial]
        if existing_ib.count():
            logger.warning("DNS-SD: IceBoard at %s with serial %s already exists "
                           "in the hardware map. No action is taken." % (host, ib_serial))
            return

        bp_slot = tr['backplane-slot'] if 'backplane-slot' in tr else None
        bp_part_number = tr['backplane-part'] if 'backplane-part' in tr else None
        bp_serial = tr['backplane-serial'] if 'backplane-serial' in tr else None

        logger.debug("DNS-SD: Discovered IceBoard SN%s (%s) in IceCrate %s SN%s, Slot %s."
                     % (ib_serial, host, bp_part_number, bp_serial, bp_slot))

        # find the integer representation of the serial number if possible, in case the user specified them that way
        try:
            int_bp_serial = int(bp_serial)
        except (TypeError, ValueError):
            int_bp_serial = None

        try:
            int_ib_serial = int(ib_serial)
        except ValueError:
            int_ib_serial = None

        try:
            slot = int(bp_slot)
        except ValueError:
            slot = None

        # If we specify no crate number, or if we have valid backplane
        # information and the backplane match that number, Then add the
        # Iceboard
        # icecrate_match = icecrates and (icecrates == '*' or any((bp_part_number in model if isinstance(model, (tuple, list)) else bp_part_number == model) and (bp_serial in serials or int_bp_serial in serials) for (model, serials) in icecrates))
        # iceboard_match = iceboards and (iceboards == '*' or ib_serial in iceboards or int_ib_serial in iceboards)

        # Check if the motherboard matches the search criteria
        iceboard_match = any(
            (target_model == '*' or ib_part_number == target_model) and
            ('*' in target_serials or ib_serial in target_serials or int_ib_serial in target_serials)
            for target_model, target_serials in iceboards)

        # Check if the backplane matches the search criteria
        icecrate_match = any(
            (target_model == '*' or bp_part_number == target_model) and
            ('*' in target_serials or bp_serial in target_serials or int_bp_serial in target_serials)
            for target_model, target_serials in icecrates)

        # Add the motherboard and backplane objects if we have an iceboard or backplane match
        if icecrate_match or iceboard_match:
            # Add a generic IceBoard to the hwm. The user will have to be replace those  with application-specific objects
            if (ib_part_number, ib_serial) in hwm:
                logger.debug('DNS-SD: Iceboard (%s, %s) was already in the hardware map. It was replaced by a new object'
                             % (ib_part_number, ib_serial))
            ib_cls = HardwareMap.get_class(ib_part_number)
            ib_obj = ib_cls(hostname=host, serial=ib_serial)
            hwm[(ib_part_number, ib_serial)] = ib_obj

            # Add the backplane if it does not already exist
            if bp_part_number and bp_serial:
                if (bp_part_number, bp_serial) in hwm:
                    bp_obj = hwm[(bp_part_number, bp_serial)]
                else:
                    bp_cls = HardwareMap.get_class(bp_part_number)
                    bp_obj = bp_cls(serial=bp_serial)
                    hwm[(bp_part_number, bp_serial)] = bp_obj
                # if the slot number is known, assign the board to the crate and set the board slot number
                if slot:
                    bp_obj.slot[slot] = ib_obj
                    ib_obj.slot = slot

            # # Find is there is IceCrate-derived superclass that handles the
            # # reported crate part number
            # icecrate_class = None
            # for mapper in class_mapper(IceCrate).self_and_descendants:
            #     supported_part_numbers = mapper.class_.__ipmi_part_number__
            #     # If the part number is None or an empty list, this means
            #     # there is no supported part number, so skip this class
            #     if not supported_part_numbers:
            #         continue
            #     # Convert a single part number into a one-element list
            #     if not isinstance(supported_part_numbers, (list, tuple)):
            #         supported_part_numbers = [supported_part_numbers]
            #     logger.debug('DNS-SD: IceCrate class search: checking in %r if part number %s is in supported PN %s' % (mapper.class_, bp_part_number, supported_part_numbers))
            #     if bp_part_number in supported_part_numbers:
            #         icecrate_class = mapper.class_
            # # If so, create the IceCrate if needed, and fill in the IceBoard's crate and slot fields
            # if icecrate_class:  # Check if a crate with the same serial number already exists
            #     existing_crate = hwm.query(icecrate_class).filter_by(serial=bp_serial)
            #     if existing_crate.count():  # If so, assign it to this iceboard
            #         new_crate = existing_crate.one()
            #         logger.debug('DNS-SD: IceCrate Model %s SN%s (class %s) is already in the hardware map. Associating IceBoard SN%s with it on slot %s.' % (bp_part_number, bp_serial, new_crate.__class__.__name__, ib_serial, bp_slot))
            #         ib.slot = bp_slot  # Add slot before adding crate
            #         ib.crate = new_crate
            #         hwm.flush()
            #     else:  # Otherwise create a new one and assign it
            #         logger.debug('DNS-SD: Creating IceCrate Model %s SN%s using class %s and associating IceBoard SN%s with it on slot %s.' % (bp_part_number, bp_serial, icecrate_class.__name__, ib_serial, bp_slot))
            #         ib.slot = bp_slot # Add slot before adding crate
            #         new_crate = icecrate_class(serial=bp_serial)
            #         ib.crate = new_crate
            #         hwm.add(new_crate)
            #         hwm.flush() # make sure the board will pop up in queries so we can know if the board already exist in the hwm
            # else:  # oops, we did not find any class to handle that IceCrate part number...
            #     logger.warning('DNS-SD: Could not find an IceCrate-derived class to represent IceCrate Model %s. The IceBoard is added without an associated crate.' % (bp_part_number))


            # Now try to resolve the hostname into an IP address to accelerate Tuber accesses
            if resolve_ip or True:
                def a_query_callback(sdRef, flags, interfaceIndex, errorCode, fullname,
                                     rrtype, rrclass, rdata, ttl, ib):
                    if errorCode == pybonjour.kDNSServiceErr_NoError:
                        ib_ip_addr = socket.inet_ntoa(rdata)
                        logger.debug("DNS-SD: IceBoard SN%s hostname %s was resolved and updated to %s" % (ib.serial, ib.hostname, ib_ip_addr))
                        ib.hostname = ib_ip_addr

                add_mdns_process(pybonjour.DNSServiceQueryRecord(
                    interfaceIndex=iface,
                    fullname=host,
                    rrtype=pybonjour.kDNSServiceType_A,
                    callBack=functools.partial(a_query_callback, ib=ib)))
        else:
            logger.debug("DNS-SD: IceBoard SN%s (crate %s SN%s slot %s) was detected but was not added because it did not match the IceBoard serial %s or crate serial %s" % (ib_serial, bp_part_number, bp_serial, bp_slot, iceboards, icecrates))

    # def resolve_callback(sdRef, flags, iface, err, fullname,
    #                      host, port, txtRecord, io_loop):
    #     if err != pybonjour.kDNSServiceErr_NoError:
    #         return
    #     print('*** resolve Callback = host=%s, port=%s, txtrecord=%s)' % (host, port, txtRecord))

    #     add_object(iface, host, txtRecord)

    def txt_query_callback(sdRef, flags, iface, err, fullname,
                         rrtype, rrclass, rdata, ttl, io_loop, host):
        """ Callback that is called when a mDNS TXT Query process received a
        record.

        The objects described by the TXT record are added to the hardware map
        if they match the search criteria.
        """
        if err != pybonjour.kDNSServiceErr_NoError:
            return
        logger.debug('DNS-SD: TXT query got the results: fullname=%s, rrtype=%s, rrclass=%s, rdata=%r)' % (fullname, rrtype, rrclass, rdata))
        add_object(iface, host, rdata)


    def browse_callback(sdRef, flags, iface, err, service,
                        regtype, replyDomain, io_loop):
        """ Callback that is called when the mDNS browser discovers a board that has the target service type.

        When a board is found, the TXT record for that board is requested.
        """
        if (err != pybonjour.kDNSServiceErr_NoError) or \
                not (flags & pybonjour.kDNSServiceFlagsAdd):
            return
        logger.debug("DNS-SD: Browser found service=%s, regtype=%s, replyDomain=%s, callback=func())" % (service, regtype, replyDomain))

        # resolver = pybonjour.DNSServiceResolve(
        #     0, iface, service, regtype, replyDomain,
        #     callBack=functools.partial(resolve_callback, io_loop=io_loop))
        # add_mdns_process(resolver)

        hostname = service + '.' + replyDomain  # trailing '.' is ok
        add_mdns_process(pybonjour.DNSServiceQueryRecord(
            flags=0,
            interfaceIndex=iface,
            fullname=pybonjour.DNSServiceConstructFullName(service, regtype, replyDomain),
            rrtype=pybonjour.kDNSServiceType_TXT,
            rrclass=pybonjour.kDNSServiceClass_IN,
            callBack=functools.partial(txt_query_callback, io_loop=io_loop, host=hostname)))

    add_mdns_process(pybonjour.DNSServiceBrowse(
        regtype='_tuber-jsonrpc._tcp',
        callBack=functools.partial(browse_callback, io_loop=io_loop)))


    # Add a timeout and start the IOloop to monitor all the ongoing mDNS processes
    io_loop.add_timeout(time.time() + timeout, lambda: io_loop.stop())
    logger.debug("DNS-SD: Starting mDNS discovery")
    io_loop.start()  # Go!
    logger.debug("DNS-SD: mDNS discovery has ended")

    # Clean up after Bonjour
    close_mdns_processes()

    return hwm
