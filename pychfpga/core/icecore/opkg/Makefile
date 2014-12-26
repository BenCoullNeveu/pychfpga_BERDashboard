SUBDIRS := iceboard-fastpath iceboard-runtime iceboard-www
.PHONY: default clean build $(SUBDIRS)
default: $(SUBDIRS)

$(SUBDIRS): build
	$(MAKE) -C $@

build:
	$(MAKE) -C ../c

clean:
	$(foreach d,$(SUBDIRS), $(MAKE) -C $(d) $@;)
