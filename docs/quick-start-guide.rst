.. _quick-start-guide:

Quick start guide
=================

blah for blah

Installation
------------

Some commands
-------------

> Quickly check which options are detected and what the current values are for the running kernel
./autokernel.py detect -c

Use ... to detect options for your system and compare them against your current kernel (requries /proc/config.gz) this can be abbreviated to ... if you have the sources
for your current kernel in /usr/src/linux

> Write only the suggested configuration changes to stdout in kconf format, so that you could
> theoretically merge them into a kernel .config file
./autokernel.py -q detect -t kconf

Copy .. to etc and edit it to suit your needs. Be sure to have a look at the config documentation

Use ... to compare the generated config against the running one.

Use ... to generate a .config file.

Use .. to make a full kernel build.

Be sure to check out --help and the documentation to fully understand what can be done.
