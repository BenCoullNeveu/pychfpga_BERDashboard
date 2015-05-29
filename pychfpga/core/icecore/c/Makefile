default: arm x86_64
.PHONY: clean default arm x86_64

export BASE_DIR=$(CURDIR)

clean:
	$(MAKE) -C x86_64 clean
	$(MAKE) -C arm clean

arm x86_64:
	$(MAKE) -C $@

