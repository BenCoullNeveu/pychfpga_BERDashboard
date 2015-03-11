NFS Root
========

NFS root is not currently supported, but here's how to make it work:

#. Unfortunately, you seem to need to re-associate the PHY before it'll work.
   This is the only real impediment. You can see that this is necessary by
   watching RS-232 for DHCP attempts from the kernel; you can remove and
   insert the Ethernet cable to get past it.

#. Use the following boot script for u-boot::

	setenv loadaddr 0x80010000
	setenv bootargs 'console=ttyO0,115200n8 root=/dev/nfs ip=dhcp nfsroot=192.168.1.1:/srv/nfs'
	dhcp
	bootm 0x80010000

#. Use the following /etc/exports on the NFS server::
   
	/srv/nfs *(ro,sync,no_subtree_check,no_root_squash)

#. Modify /etc/network/interfaces on the rootfs image, and comment out the
   eth0 section.
