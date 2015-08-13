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
    """ Instantiates an object that represents the backplane shuffle

    A backplane shuffle object is a pure xglink_array object, so nothing is added to the class.
    """
    pass

    def get_matching_tx_node_id(self, rx_node_id):
        return self.fpga.crate.get_matching_tx(rx_node_id)

    def get_rx_net_length(self, rx_node_id):
        return self.fpga.crate.get_rx_net_length(rx_node_id)

    def get_links(self):
        """
        Return a list of all the backplane links in the format ((source_slot, source_lane), (dest_slot, dest_lane)).

        Takes into account the BYPASS mode.
        """
        ds = self.fpga.slot
        if self.BYPASS:
            return [((ds, dl), (ds, dl)) for dl in range(self.NUMBER_OF_LINKS+1)]
        else:
            return [(self.fpga.crate.get_matching_tx((ds, dl)), (ds, dl)) for dl in range(self.NUMBER_OF_LINKS+1)]
