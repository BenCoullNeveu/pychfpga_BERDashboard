#!/bin/sh

# This script is intended to be source'd, and sets environment variables
# suitable for building C code in this repository. For example, use
#
#    $ . setenv.sh
#
# In particular, we're looking for a C compiler that's built during builddroot
# compilation. Buildroot for the IceBoard lives in a separate Bitbucket
# repository. Having a working compiler is a pre-requisite for building the C
# code that lives here.

CC=arm-buildroot-linux-gnueabihf-gcc
FULL_CC=$(which $CC)

if [ $? -eq 0 ]
then
	echo "Found ARM C compiler in PATH."
else
	FULL_CC=$(locate -b \\$CC)
	#TOOLPATH=$(dirname $CC)
	#echo TOOLPATH is $TOOLPATH

	if ! [ -x $FULL_CC ]
	then
		echo "Failed to find tools! (looked for $CC)"
	else
		echo "Found ARM C compiler at $FULL_CC. Adding to PATH."
		export PATH=$PATH:$(dirname $FULL_CC)
	fi
fi
