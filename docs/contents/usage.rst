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
        pip install -r requirements.txt
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

    Usage: autokernel [opts...] <command> [command_opts...]

For additional information, refer to the help texts:

.. code-block:: bash

    autokernel --help            # General help
    autokernel <command> --help  # Command specific help

.. topic:: Configuration

    Before proceeding, you might want to have a look at the
    default configuration in ``/etc/autokernel`` to familiarize yourself
    with the general format.

    To explicitly specify a configuration, use the option ``-C path/to/autokernel.conf``

.. topic:: Kernel location

    By default, autokernel expects the kernel to reside in ``/usr/src/linux``.
    If you want to specify another location, use the option ``-K path/to/kernel``

.. hint::

    If you are **not** using gentoo or another source distribution,
    use ``-K kernel_dir`` to specify the kernel directory. Autokernel will
    not work otherwise.

.. _usage-detecting-options:

Detecting kernel options
------------------------

Autokernel can automatically detect kernel configuration options for your system.
This is done mainly by collecting bus and device information from the ``/sys/bus`` tree,
which is exposed by the currently running kernel. It then relates this information to
a configuration option database (LKDDb_), selects the corresponding symbols and
the necessary dependencies.

It might be beneficial to run detection while using a very generic and
modular kernel, such as the `kernel from Arch Linux <https://www.archlinux.org/packages/core/x86_64/linux/>`__.
This increases the likelihood of having all necessary buses and features enabled
to detect connected devices.

The problem is that we cannot detect USB devices, if the current kernel does not
support that bus in the first place.

.. hint::

    You can run autokernel directly on an Arch Linux live system.

Comparing to the current kernel
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    autokernel detect -c

This command detects option values and outputs a summary in which you
can easily see the current value of the symbol and the suggested one.
This gives a good overview over what would be changed.

.. note::

    Be aware that autokernel never suggests to build modules, so you might
    see several ``[m] → [y]`` changes. You should build commonly used features
    into the kernel to cut down on load times and attack surface (if you manage to disable ``MODULES``).

Generating an autokernel module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can generate a module from the detected options, which can then
be put into ``/etc/autokernel/modules.d`` and included in your configuration.

.. code-block:: bash

    # Generates a module named 'local_detected'
    autokernel detect -o "/etc/autokernel/modules.d/local_detected.conf"

Alternatively, autokernel can output kconf files (like ``.config``)
if you want to use other tools:

.. code-block:: bash

    # Generates a kconf file for usage with other tools
    autokernel detect -t kconf -o ".config.local"

.. warning::

    Be aware that even though this detection mechanism is nice to have, it is also far from perfect.
    The option database is automatically generated from kernel sources, and so you will have
    false positives and false negatives. You should work through the list of detected options
    and decide if you really want to enable them.

Generating the kernel configuration
-----------------------------------

Generating a .config file
^^^^^^^^^^^^^^^^^^^^^^^^^

To generate a ``.config`` file, all you need to do is execute the following command:

.. code-block:: bash

    # Generates .config directly in the kernel directory (see -K)
    autokernel generate-config
    # Generates a config file at the given location
    autokernel generate-config -o test.config

Comparing to another config
^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you instead want to see differences to another kconf file (.config), you can
use the ``check`` command. This is especially useful to see what has changed
between kernel versions.

.. code-block:: bash

    # Checks against the current kernel (/proc/config.gz)
    autokernel check
    # Check against explicit file
    autokernel check -c some/.config
    # Check against the .config file of another kernel version
    autokernel check -c -k some/kernel/dir some/kernel/dir/.config

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
    it, you can view the original files `on github <https://github.com/oddlama/autokernel/tree/master/autokernel/contrib/etc>`__
    or in the autokernel module directory under ``autokernel/contrib/etc``.

The most important directives are outlined in the following and by this example:

Configuration excerpt
~~~~~~~~~~~~~~~~~~~~~

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
        # by using `autokernel detect` and store them in /etc/autokernel/modules.d/local_detected.conf
        use local_detected;

        # Proceed to make your changes.
        use net;
    }

Modules
~~~~~~~

Kernel configuration is done in module blocks. Modules provide encapsulation for options
that belong together and help to keep the config organized. The main module is the
``kernel { ... }`` block. You need to ``use`` (include) modules in this block to include them
in your config. Module can also include other modules, cyclic or recursive includes are impossible
by design.

Assigning symbols
~~~~~~~~~~~~~~~~~

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
        set DEFAULT_MMAP_MIN_ADDR "65536"; # or with quotes

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

Adding to the kernel command line
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By using a statement like

.. code-block:: ruby

    add_cmdline "rng_core.default_quality=512";

you can directly append options to the builtin commandline.

.. note::

    This will cause ``CMDLINE_BOOL`` to be enabled and ``CMDLINE`` to
    be set to the resulting string.

Best practices
~~~~~~~~~~~~~~

Here are some general best practices for writing autokernel configurations:

- Always start by merging a ``defconfig`` file, to use the equivalent of
  ``make defconfig`` as the base.
- Use modules to organize your configuration.
- Document your choices with comments.
- Use conditionals to write generic modules so they can be used for multiple
  kernel versions and maybe even across machines.

.. _usage-command-satisfy:

Enabling arbitrary symbols
^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes you want to enable a symbol, but don't know which dependencies
you have to enable first. Use the ``satisfy`` command to let autokernel
find a valid configuration for you. By default the output will be based
on the kernel configuration managed by autokernel.
If you want to use a clean default config, use ``satisfy -g``.

.. code-block:: bash

    autokernel satisfy -g WLAN

Will output the following on kernel version 5.6.1:

.. code-block:: ruby

    # Generated by autokernel on 2020-04-13 13:37:42 UTC
    # vim: set ft=ruby ts=4 sw=4 sts=-1 noet:
    # required by config_netdevices
    # required by config_wlan
    module config_net {
            set NET y;
    }

    # required by config_wlan
    module config_netdevices {
            use config_net;
            set NETDEVICES y;
    }

    # required by rename_me
    module config_wlan {
            use config_netdevices;
            use config_net;
            set WLAN y;
    }

    module rename_me {
            use config_wlan;
    }

.. hint::

    To preserve the dependency structure and avoid duplication, autokernel will
    output one module per encountered option. You can and probably should extract
    only the relevant symbols assignments.

.. note::

    Even though modules are used, autokernel guarantees to set dependencies before
    dependents. You can therefore simply extract all set statemtents and write them
    one after another for the same result.

Querying symbol information
^^^^^^^^^^^^^^^^^^^^^^^^^^^

In case you have forgotten the meaning of a kernel symbol,
you can use the ``info`` command to show the attached help text
as you would encounter it in ``make menuconfig``.

.. code-block:: bash

    autokernel info WLAN

Querying symbol reverse dependencies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the ``revdeps`` command to show all symbols that somehow
depend on the given symbol.

.. code-block:: bash

    autokernel revdeps EXPERT

.. _usage-hardening:

Hardening the kernel
--------------------

Autokernel provides a preconfigured module for kernel hardening,
which is installed to ``/etc/autokernel/modules.d/hardening.conf`` if
you used ``autokernel setup``. Otherwise you will find it `on github <https://github.com/oddlama/autokernel/tree/master/autokernel/contrib/etc/modules_d/hardening.conf>`__ or
in the autokernel module directory under ``autokernel/contrib/etc/modules_d/hardening.conf``.

The hardening module is compatible with any kernel version >= 4.0.
Every choice is also fully documented and explanined. Feel free to adjust it to your needs.

If the file is included, you can enable it like this:

.. code-block:: ruby

    kernel {
        # Use hardening early in your config. Errors will then be caused by
        # the offending assignment instead of the assignments in the hardening
        # module, which makes error messages easier to read.
        use hardening;

        # ...
    }

.. _usage-building-installing:

Building and installing the kernel
----------------------------------

Autokernel can be used to build the kernel and to install the resulting files.
The respective commands are ``build`` and ``install``, but they can be combined by using the ``all`` command.

.. code-block:: bash

    autokernel all # Build the kernel and install it

.. hint::

    You can use :ref:`build hooks<directive-build-hooks>` and :ref:`install hooks<directive-install-hooks>`
    to add additional functionality before and after execution of the respective phase.

.. warning::

    Be especially careful with file and directory permissions for hook scripts!
    Autokernel will do a sanity check to ensure that no other user can inject commands
    by editing the autokernel configuration, but in the end it is your responsibility.

Just the kernel
^^^^^^^^^^^^^^^

This is an example that shows how the configuration can be used to:

- disable initramfs generation
- install the kernel to ``/boot``
- install modules to the default location

.. code-block:: ruby

    initramfs {
        enable false;
    }

    install {
        target_dir "/boot";
        target_initramfs false;
        target_config false;
        # ...
    }

Using dracut to build an initramfs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Here is an example which builds an initramfs with dracut
and integrates the result back into the kernel.
This means you still only need to install the kernel.

.. hint::

    When using builtin initramfs, setting any of the ``INITRAMFS_COMPRESSION_*`` options will
    still compress it on integration.

.. code-block:: ruby

    kernel {
        # Optional: Use LZ4 as compression algorithm for built-in initramfs
        set RD_LZ4 y if BLK_DEV_INITRD;
        set INITRAMFS_COMPRESSION_LZ4 y if INITRAMFS_SOURCE;
    }

    initramfs {
        enable true;
        builtin true;

        # Adjust this to your needs
        build_command "dracut"
            "--conf"          "/dev/null" # Disables external configuration
            "--confdir"       "/dev/null" # Disables external configuration
            "--kmoddir"       "{MODULES_PREFIX}/lib/modules/{KERNEL_VERSION}"
            "--kver"          "{KERNEL_VERSION}"
            "--no-compress"   # Only if the initramfs is to be integrated into the kernel
            "--no-hostonly"
            "--ro-mnt"
            "--add"           "bash crypt crypt-gpg"
            "--force"         # Overwrite existing files
            "{INITRAMFS_OUTPUT}";
    }

Mounting directories and purging files
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have an fstab entry for a directory used in the target directory,
you can have autokernel mount the directory on install. See :ref:`directive-install-mount`
for more information.

If you want to purge old builds from the target directory, you can
use the :ref:`directive-install-keep-old` directive.

.. code-block:: ruby

    install {
        # ...

        # Mount /boot when installing and unmount afterwards
        mount "/boot";

        # Keeps the last two builds and removes the rest from the
        # target directory
        keep_old 2;
    }

.. _LKDDb: https://cateee.net/lkddb/
