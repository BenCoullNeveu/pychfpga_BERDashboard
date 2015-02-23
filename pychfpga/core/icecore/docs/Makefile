.PHONY: default html doctest

default: html

html doctest:
	sphinx-build -b $@ . build/$@

publish: html
	rsync -rz --delete --no-implied-dirs --rsh=ssh build/html/ \
		kingspeak.physics.mcgill.ca:/home/www/icecore_sphinx
