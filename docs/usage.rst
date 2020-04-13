.. _usage:

Usage
=====

Welcome to the usage section! Below is a table of contents for this
guide. Feel free to directly jump to the topic of your interest.

.. contents::
    :local:


Installation
------------

Use can use pip to install autokernel, or run from source:

.. topic:: Using pip

    .. code-block:: bash

        pip install autokernel
        autokernel --help

.. topic:: From source

    .. code-block:: bash

        git clone "https://github.com/oddlama/autokernel.git"
        cd autokernel
        pip install --user -r requirements.txt
        ./bin/autokernel.py --help

.. topic:: Setting up the basic configuration

    If you intend to use autokernel for more than testing purposes, you should
    allow autokernel to setup a basic configuration in ``/etc/autokernel``, which can
    then be edited. This command will never override any existing configuration.

    .. code-block:: bash

        # Populates /etc/autokernel with the default configuration, if no configuration exists.
        sudo autokernel setup

    .. note::

        If you don't setup the configuration directory, autokernel will fallback to
        a minimal internal configuration to allow for testing.

Basic invokation
----------------

All invocations of autokernel follow this scheme:

.. code-block:: bash

    Usage: autokernel [opts...] command [command_opts...]

For additional information, see ``autokernel --help``.

.. topic:: Configuration

    Autokernel expects the configuration to be in ``/etc/autokernel/autokernel.conf``.
    If it doesn't exist, autokernel will use an internal fallback configuration.
    To explicitly specify a configuration file, use the option ``-C path/to/autokernel.conf``

.. topic:: Kernel location

    By default, autokernel expects the kernel to reside in ``/usr/src/linux``.
    If you want to specify another location, use the option ``-K path/to/kernel``

Detecting kernel options
------------------------

Autokernel can automatically detect kernel configuration options for your system.
This is done mainly by collecting bus and device information from the ``/sys/bus`` tree,
which is exposed by the currently running kernel. It then relates this information to
a configuration option database (LKDDb_), selects the corresponding symbols and
the necessary dependencies.

.. warning::

    Be aware that even though this detection mechanism is nice to have, it is also far from perfect.
    The option database is automatically generated from kernel sources, and so you will have
    false positives and false negatives. You should work through the list of detected options
    and decide if you really want to enable them.

.. note::

    It might be beneficial to run detection while using a very generic and
    modular kernel, such as the `kernel from Arch Linux <https://www.archlinux.org/packages/core/x86_64/linux/>`_.
    This increases the likelihood of having all necessary buses and features enabled
    detect most connected devices.

    The problem is that we cannot detect USB devices, if the current kernel does not
    support that bus in the first place.

.. hint::

    You can run autokernel directly on an Arch Linux live system.

.. topic:: Comparing to the current kernel

    .

.. topic:: Generating a module

    .

Generating the kernel configuration
-----------------------------------

.. topic:: Generating a .config file

    .

.. topic:: Comparing another config to the generated one

    .

Writing configuration
---------------------

Configuration primer
^^^^^^^^^^^^^^^^^^^^

You will most likely only need a few directives to write your kernel config.
Apart from configuring kernel options, autokernel's configuration allows you to specify
some settings for building the initramfs, and the general build and installation process.
For a more in-depth explanation of autokernel's configuration, see the sections about :ref:`syntax` and :ref:`directives`.

.. hint::

    The default configuration that is generated when using ``autokernel setup`` is
    a great starting point to write your own configuration. If you have already changed
    it, you can view the original file in ``TODO``.

The most important directives are outlined in the following and by this example:

.. topic:: Configuration excerpt

    .. code-block:: ruby

        module base {
            # Begin with the kernel defconfig
            merge "{KERNEL_DIR}/arch/{ARCH}/configs/{UNAME_ARCH}_defconfig";

            # Enable expert options
            set EXPERT y;
            # Enable the use of modules
            set MODULES y;
        }

        module net {
            # Enable basic networking support.
            set NET y;
            # Enable IP support.
            set INET y;
            # Enable ipv6
            set IPV6 y;
            # IPv6 through IPv4 tunnel
            set IPV6_SIT y;

            # Enable wireguard tunnel
            if $kernel_version >= 5.6 {
                set WIREGUARD y;
            }
        }

        # The main module
        kernel {
            # Begin with a proper base config
            use base;

            # The hardening module is provided in /etc/autokernel/modules.d,
            # if you have used `autokernel setup`.
            use hardening;
            # You can detect configuration options for your local system
            # by using `autokernel detect` and store them in /etc/autokernel/modules.d/local.conf
            use local;

            # Proceed to make your changes.
            use net;
        }

.. topic:: Modules

    Kernel configuration is done in module blocks. Modules provide encapsulation for options
    that belong together and help to keep the config organized. The main module is the
    ``kernel { ... }`` block. You need to ``use`` (include) modules in this block to include them
    in your config. Module can also include other modules, cyclic or recursive includes are impossible
    by design.

.. topic:: Assigning symbols

    To write your configuration, you need to assign values to kernel symbols. This must
    be done inside a module. Here is an example which shows the most common usage patterns.

    .. code-block:: ruby

        module test {
            set USB y;    # Enable usb support
            set USB;      # Shorthand syntax for y
            set USB "y";  # All parameters may be quoted

            set KVM m;    # Build KVM as module
            # Example of setting a non-tristate option.
            set DEFAULT_MMAP_MIN_ADDR 65536;
            set DEFAULT_MMAP_MIN_ADDR "65536";

            # Set a string symbol
            set DEFAULT_HOSTNAME refrigerator;   # OK
            set DEFAULT_HOSTNAME "refrigerator"; # Also OK

            # Inline condition example
            set WIREGUARD if $kernel_version >= 5.6;

            # Conditions work with usual expression syntax
            # and you can examine symbols
            if X86 and not X86_64 {
                set DEFAULT_HOSTNAME "linux_x86";
            else if (X86_64) {
                set DEFAULT_HOSTNAME "linux_x86_64";
            } else if $arch == "mips" {
                set DEFAULT_HOSTNAME "linux_mips";
            } else {
                set DEFAULT_HOSTNAME "linux_other";
            }
        }

.. topic:: Best practices

    Here are some general best practices for writing autokernel configurations:

    - Always start by merging a ``defconfig`` file, to use the equivalent of
      ``make defconfig`` as the base.
    - Use modules to organize your configuration.
    - Document your choices with comments.
    - Use conditionals to write generic modules so they can be used for multiple
      kernel versions and maybe even across machines.

Enabling arbitrary symbols
^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes you want to enable a symbol, but don't know which dependencies
you have to enable first. Use the ``satisfy`` command to let autokernel
find a valid configuration for you. By default the output is based on the
generated config. If you want to use a clean default config, use ``satisfy -g``.

.. code-block:: bash

    autokernel satisfy -g DVB_USB_RTL28XXU

.. hint::

    To preserve the dependency structure and avoid duplication, autokernel will
    output one module per encountered option. You can and probably should extract
    only the relevant symbols assignments.

.. note::

    Even though modules are used, autokernel guarantees to set dependencies before
    dependents. You can therefore simply extract all set statemtents and write them
    one after another for the same result.

Will output the following on kernel version 5.6.1:

.. code-block:: bash

    # Generated by autokernel on 2020-04-13 13:58:31 UTC
    # vim: set ft=ruby ts=4 sw=4 sts=-1 noet:
    # required by config_media_usb_support
    # required by config_media_digital_tv_support
    module config_media_support {
        set MEDIA_SUPPORT y;
    }

    # required by config_media_usb_support
    module config_usb {
        set USB y;
    }

    module config_media_usb_support {
        use config_media_support;
        use config_usb;
        set MEDIA_USB_SUPPORT y;
    }

    module config_media_digital_tv_support {
        use config_media_support;
        set MEDIA_DIGITAL_TV_SUPPORT y;
    }

    # required by config_i2c_mux
    module config_i2c {
        set I2C y;
    }

    module config_i2c_mux {
        use config_i2c;
        set I2C_MUX y;
    }

Querying symbol information
^^^^^^^^^^^^^^^^^^^^^^^^^^^

In case you have forgotten the meaning of a kernel symbol,
you can use the ``info`` command to show the attached help text
as you would encounter it in ``make menuconfig``.

.. code-block:: bash

    autokernel info DVB_USB_RTL28XXU

Querying symbol reverse dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the ``revdeps`` command to show all symbols that somehow
depend on the given symbol.

.. code-block:: bash

    autokernel revdeps EXPERT

Building and installing the kernel
----------------------------------

Building and installation can be executed separately by using...

.. warning::

    Be careful with file and directory permissions, autokernel will do sanity checks
    and abort when it detects that another user can inject commands.

.. topic:: Just the kernel

    .

.. topic:: With initramfs

    To use builtin do.

.. hint::

    CMDLINE is always included when used.

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

.. _LKDDb: https://cateee.net/lkddb/
