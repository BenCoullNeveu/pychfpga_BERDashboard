"""
shuffle.py module
    Implements interface to the backplane or intercrate shuffle module

History:
    2013-10-29 : JFC : Created
"""
import xglink

from Module import BitField

# Types of memory-mapped registers
CONTROL = BitField.CONTROL
STATUS = BitField.STATUS
DRP = BitField.DRP


class Shuffle(xglink.XGLinkArray):
    """ Object that represents the GTX data links of the FPGA-based
    corner-turn engine. Both the PCB links (between boards in the same crate)
    and the backplane QSFP links (between boards in two different crates) are
    included.

    The `Shuffle` inherits from XGLinkArray, with some application-specific
    methods added.
    """
    pass

    def get_matching_tx_node_id(self, rx_node_id):
        """ Return the PCB link transmitter node id ( a (slot, lane) tuple)
        that corresponds to the specified receiver node id.

        Parameters:

            rx_node_id (tuple): A (slot, lane) tuple that identifies the PCB link receiver

        Returns:

            A (slot, lane) tuple that corresponds to the specified receiver node id
        """
        return self.fpga.crate.get_matching_tx(rx_node_id)

    def get_rx_net_length(self, rx_node_id):
        """ Return the length of the PCB link connected to the specified receiver node.

        This method can be useful if we need to optimize the transmit power as a function of estimated losses in the link.

        Parameters:

            rx_node_id (tuple): A (slot, lane) tuple that identifies the PCB link receiver

        Returns:

            float that indicates the trace length in mils.
        """
        return self.fpga.crate.get_rx_net_length(rx_node_id)

    def get_link_map(self, lane_group='pcb'):
        """ Return a dictionary that lists all the backplane PCB data shuffle
        lanes of the corner turn engine, and associated GTX Tx and Rx
        instances.

        The dictionary does not include the QSFP data lanes. It includes the
        internal bypass lanes (not just the physical GTX links), and links
        that have no end-to-end connectivity.

        The dictionary is in the format:

            { (link_type, tx_node_id, rx_node_id) : (tx_gtx, rx_gtx)}

        Where link_type is either 'BP' or 'BP_QSFP', and where `tx_node_id`
        and `rx_node_id` are tuples in the format: ``(crate_id, slot_id,
        lane_id)``. All id's are zero-based.

        A link is resolved when the node_id is known at both ends of the link,
        whether or not there is hardware at each end of the link.the
        Consequently, a link that is not resolved has either its `tx_node_id`
        or `rx_node_id` instance set to `None`:

            ('BP_QSFP', None, rx_id) : (None, rx_gtx_instance)

        Links that are (resolved) but are missing *one* gtx instance are broken (i.e.
        missing board):

            ('BP', tx_id, rx_id) : (tx_gtx, None) 
            ('BP', tx_id, rx_id) : (None, rx_gtx) 

        A relolved link that is missing *both* the rx and tx gtx in a valid
        internal direct link.

            ('BP', tx_id, rx_id) : (None, None) 

        'pcb' links are always resolved, since the method has access to the
        icecrate object, which is aware of which node should be at the other
        end.  Links will be roken if the board is missing at the other end.
        Lane 0 is always the internal link that connect to the same lane of
        the same board.

        With the exception of the internal direct links, 'qsfp' links are
        always unresolved, since this method has no knowledge of other crates.

        The link map takes into account whether the transmitters are are
        currently in bypass mode and are sending the data to itself instead of
        an other board.


        Returns:
            A dictionry in the format:
                { ('BP', (tx_crate_id, tx_slot, tx_lane), (rx_crate_id, rx_slot, rx_lane): (tx_gtx, rx_gtx)}

        """
        links = {}
        (rx_crate, rx_slot) = self.fpga.get_id()
        # Create the pcb link map. We scan all receiver links
        if lane_group == 'pcb' or lane_group is None:
            for rx_lane, (phys_lane, gtx_ix, rx_gtx) in self.lane_map['pcb'].items:
                rx_id = (rx_crate, rx_slot, rx_lane)
                if rx_gtx:
                    tx_crate = rx_crate
                    (tx_slot, tx_lane) = self.get_matching_tx_node_id((rx_slot, rx_lane))
                    tx_id = (tx_crate, tx_slot, tx_lane)
                    tx_ib = self.fpga.crate.slot.get(tx_slot + 1, None)
                    if tx_ib:
                        tx_gtx = tx_ib.BP_SHUFFLE.get_gtx(tx_lane, 'pcb')
                    else:
                        tx_id = None
                        tx_gtx = None
                else: # direck internal link
                    tx_id = rx_id
                    tx_gtx = None
                links[('BP', tx_id, rx_id)] = (tx_gtx, rx_gtx)
            return links

        # Add unresolved QSFP links for both the transmitter and receivers ends
        if lane_group == 'qsfp' or lane_group is None:
            for rx_lane, (phys_lane, gtx_ix, rx_gtx) in self.lane_map['qsfp'].items:
                rx_id = (rx_crate, rx_slot, rx_lane)
                links[('BP_QSFP', None, rx_id)] = (None, rx_gtx)
                links[('BP_QSFP', rx_id, None)] = (rx_gtx, None)
            return links
        


    def get_links(self):
        """
        Return a list of all the backplane links in the format
        (link_type, (source_crate, source_slot, source_lane), (dest_crate, dest_slot, dest_lane)).

        Takes into account the BYPASS mode.
        """
        return self.get_link_map().keys()

