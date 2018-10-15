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
        """ Return the PCB link transmitter node id ( a (slot, lane) tuple) that corresponds to the specified receiver node id.

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

    def get_link_map(self, group='pcb'):
        """ Return a dictionary that lists all the backplane PCB data shuffle
        lanes of the corner turn engine, and associated GTX Tx and Rx
        instances.

        The dictionary does not include the QSFP data lanes. It includes the
        internal bypass lanes (not just the physical GTX links), and links
        that have no end-to-end connectivity.

        The dictionary is in the format:

            { ('BP', tx_node_id, rx_node_id) : (tx_gtx, rx_gtx)}

        Where `tx_node_id` and `rx_node_id` are tuples in the format:
        ``(crate_id, slot_id, lane_id)``.

        Takes into account whether the links are currently in bypass mode.

        Returns:
            A dictionry in the format:
                { ('BP', (tx_crate_id, tx_slot, tx_lane), (rx_crate_id, rx_slot, rx_lane): (tx_gtx, rx_gtx)}

        """
        link_types = {
            'pcb': 'BP',
            'qsfp': 'BP_QSFP'
            }
        links = {}
        rx_crate = self.fpga.get_crate_id()
        rx_slot = self.fpga.slot

        for rx_lane in range(self.NUMBER_OF_PCB_LANES):
            # if the shuffle stage is set-up to bypass
            if self.BYPASS_PCB_SHUFFLE:
                (tx_crate, tx_slot, tx_lane) = (rx_crate, rx_slot, rx_lane)
                rx = None
                tx = None
            else:
                (tx_slot, tx_lane) = self.fpga.crate.get_matching_tx((rx_slot, rx_lane))
                rx = self.gtx[dl - self.NUMBER_OF_PCB_DIRECT_LANES] if dl >= self.NUMBER_OF_PCB_DIRECT_LANES else None
                source_ib = self.fpga.crate.slot.get(ss, None)
                tx = source_ib.BP_SHUFFLE.gtx[sl - self.NUMBER_OF_PCB_DIRECT_LANES] if source_ib else None
            link = ('BP', (sc, ss, sl), (sc, ds, dl))
            links[link] = (tx, rx)
        return links

    def get_links(self):
        """
        Return a list of all the backplane links in the format
        (link_type, (source_crate, source_slot, source_lane), (dest_crate, dest_slot, dest_lane)).

        Takes into account the BYPASS mode.
        """
        return self.get_link_map().keys()

