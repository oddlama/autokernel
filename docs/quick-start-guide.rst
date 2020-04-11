.. _quick-start-guide:

Quick start guide
=================

Installation
------------

Use pip to install autokernel:

.. code-block::

    pip install autokernel

.. topic:: Setting up the basic configuration

    If you intend to use autokernel for more than testing purposes, you should
    allow autokernel to setup a basic configuration in ``/etc/autokernel``, which can
    then be edited. This command will never override any existing configuration.

    .. code-block::

        # Populates /etc/autokernel with the default configuration, if no configuration exists.
        sudo autokernel setup

.. note::

    If you don't setup the configuration directory, autokernel will fallback to
    a minimal internal configuration to allow for testing.

Basic options
-------------

-q mute all logging output
-C <config>
-K <kernel_dir>

Detecting kernel options
------------------------

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
