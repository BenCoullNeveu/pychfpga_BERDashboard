all: chi-exec

clean:
	rm -f chi-exec *~

install: chi-exec
	install -g data-acq -o root -m 4750 $< /usr/local/sbin/chi-exec
