# IceBoard base components
SUBDIRS := libiceboard fastpath iceboard-package

# Place additional subdirs here, e.g.
# SUBDIRS := libdfmux dfmux-package

default: $(SUBDIRS)
.PHONY: default clean $(SUBDIRS)

$(SUBDIRS):
	$(MAKE) -C $@

clean:
	$(foreach d,$(SUBDIRS), $(MAKE) -C $(d) $@;)
