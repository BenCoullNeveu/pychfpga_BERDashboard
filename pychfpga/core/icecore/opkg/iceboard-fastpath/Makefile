TARGET=data
BUILD=..

.PHONY: iceboard-fastpath.opk control.tar.gz data.tar.gz

iceboard-fastpath.opk: control.tar.gz data.tar.gz debian-binary
	rm -f $@
	ar -r $@ $^

control.tar.gz: $(shell find control/)
	cd control/ && tar czf ../$@ *

data.tar.gz: $(shell find data/)
	cd data/ && tar czf ../$@ --dereference *

.PHONY: clean
clean:
	rm -f *.opk *.tar.gz
