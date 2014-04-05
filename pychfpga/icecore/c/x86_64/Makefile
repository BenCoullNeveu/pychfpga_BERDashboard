SUBDIRS := 
default: $(SUBDIRS)
.PHONY: default tuber clean

$(SUBDIRS):
	$(MAKE) -C $@

clean:
	$(foreach d,$(SUBDIRS), $(MAKE) -C $(d) $@;)
