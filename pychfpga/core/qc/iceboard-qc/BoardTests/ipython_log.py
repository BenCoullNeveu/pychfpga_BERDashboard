# IPython log file

get_ipython().magic(u'cd ../../git/iceboard-qc/BoardTests/')
get_ipython().magic(u'pwd ')
import iceboardtest
import fpgaFun
fpgaFun.programFpga('0047',host_ip='10.10.10.218',force=True)
c
c=fpgaFun.programFpga('0047',host_ip='10.10.10.218',force=True)
c47=c[47]
c
c.open()
c.hw
c
c.get_info
c.get_info()
d=c.get_info()
d
get_ipython().magic(u'logon')
get_ipython().magic(u'logon')
get_ipython().magic(u'logstart')
c.get_info()
get_ipython().magic(u'logstate')
get_ipython().magic(u'logstop')
