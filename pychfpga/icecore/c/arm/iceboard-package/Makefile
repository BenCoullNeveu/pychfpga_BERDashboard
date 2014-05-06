default: prepare iceboard-runtime.opk
.PHONY: prepare default

TARGET=data
BUILD=..

prepare:
	@# Ensure directories exist
	mkdir -p $(TARGET)/usr/sbin/
	mkdir -p $(TARGET)/usr/share/tuber/
	mkdir -p $(TARGET)/home/www/

	@# Copy files into data
	cp -ua $(BUILD)/fastpath/fastpath $(TARGET)/usr/sbin/
	cp -ua $(BUILD)/libiceboard/libiceboard.so $(TARGET)/usr/share/tuber/

iceboard-runtime.opk: control.tar.gz data.tar.gz debian-binary
	rm -f $@
	ar -r $@ $^

control.tar.gz: $(shell find control/)
	cd control/ && tar czf ../$@ *

data.tar.gz: $(shell find data/)
	cd data/ && tar czf ../$@ *
