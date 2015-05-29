.. _SectionGTXselection:

GTX connection selection resistors
----------------------------------

GTX Banks 111,112,113 and 114 each contain 4 multi-gigabit transceivers (MGT)
that can be connected either to the FMC DP lines or to the backplane high speed
(shuffle) lines. Each link can operate at speeds up to 12.5 Gbps. The routing
of the link is set by soldering resistors to the proper pads.
:ref:`FigGTXSelectionResistors` shows which block of resistors control the
routing of which GTX signals.

.. _FigGTXSelectionResistors:
.. figure:: ../images/gtx_selection_resistors.svg
    :align: center
    :width: 800 px

    GTX Selection Resistors

.. vim: sts=3 ts=3 sw=3 tw=78 smarttab expandtab
