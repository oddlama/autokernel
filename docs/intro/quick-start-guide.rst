.. _quick-start-guide:

Quick start guide
=================

Welcome to the quick start guide! Here you will see a selection of commands
to quickly get started with autokernel.

This is basically an extreme summary of the :ref:`usage` section.
It is recommended to read both the :ref:`introduction` and the :ref:`usage` section, as commands and their effects are explained in greater detail there.

Basic invokation
----------------

.. hint::

    If you are **not** using gentoo or another source distribution, which
    has kernel sources available under ``/usr/src/linux``, use ``-K kernel_dir``
    to specify the kernel directory. Autokernel will not work otherwise.

Detecting kernel options
------------------------

Detect configuration options for your system and report differences
to the running kernel:

.. code-block:: bash

    autokernel detect -c

The next command generates output as commonly seen in a .config file.
This is useful if you want to use other tools with the detected options:

.. code-block:: bash

    # Generates a kconf file for usage with other tools
    autokernel detect -t kconf -o ".config.local"

You can also generate an autokernel module from the result:

.. code-block:: bash

    # Generates a module named 'local'
    autokernel detect -o "/etc/autokernel/modules.d/local.conf"

.. warning::

    Be aware that even though this detection mechanism is nice to have, it is also far from perfect.
    The option database is automatically generated from kernel sources, and so you will have
    false positives and false negatives. You should work through the list of detected options
    and decide if you really want to enable them.

Generating the kernel configuration
-----------------------------------

Generate a ``.config`` file from your autokernel configuration with ``generate-config``:

.. code-block:: bash

    # Generates a config file at the given location
    autokernel generate-config -o .config

Alternatively, you can compare the theoretically generated config to another config by using ``check``:

.. code-block:: bash

    # Checks against the current kernel (/proc/config.gz)
    autokernel check
    # Check against the .config file of another kernel version
    autokernel check -c -k some/kernel/dir some/kernel/dir/.config

Enabling arbitrary symbols
--------------------------

You can use the ``satisfy`` command to automatically show which dependencies
are missing to enable an option:

.. code-block:: bash

    autokernel satisfy -g WLAN

Querying symbol information
---------------------------

Query symbol information (menuconfig help text) with ``info``:

.. code-block:: bash

    autokernel info WLAN

Querying symbol reverse dependencies
------------------------------------

Use the ``revdeps`` command to show all symbols that depend on the given symbol:

.. code-block:: bash

    autokernel revdeps EXPERT

Hardening the kernel
--------------------

Check out :ref:`usage-hardening` for a short description of the included hardening module.

Building and installing the kernel
----------------------------------

To build and install the kernel according to your configuration use ``build`` and ``install``:

.. code-block:: bash

    autokernel build   # Just build targets
    autokernel install # Just install targets
    autokernel all     # Do both
