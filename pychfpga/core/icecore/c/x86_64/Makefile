SUBDIRS := fastpath
default: $(SUBDIRS)
.PHONY: default $(SUBDIRS) clean

$(SUBDIRS):
	$(MAKE) -C $@

clean:
	$(foreach d,$(SUBDIRS), $(MAKE) -C $(d) $@;)
