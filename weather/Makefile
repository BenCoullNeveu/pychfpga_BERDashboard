BIN=ch_translate_weather
CRON=ch_scrape_weather
CONF=weather.conf
TAG=version
BINDIR=/usr/local/bin
CRONDIR=/etc/cron.daily
CHIMEDIR=/etc/chime

install: $(BIN) $(CRON) $(CONF)
	if [ ! -d $(CHIMEDIR) ]; then mkdir $(CHIMEDIR); fi
	install -m 775 $(BIN) $(BINDIR)
	install -m 775 $(CRON) $(CRONDIR)
	install -m 644 $(CONF) $(CHIMEDIR)
	echo "`git describe --tags`" > $(CHIMEDIR)/$(TAG)
