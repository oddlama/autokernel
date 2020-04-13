.. _usage:

Usage
=====

Welcome to the usage section. Here you will find several examples of how to use
autokernel for different tasks.

.. warning::

    Be careful with file and directory permissions, autokernel will do sanity checks
    and abort when it detects that another user can inject commands.

.. _usage-detecting-options:

Detecting options
-----------------

Autokernel can automatically detect kernel configuration options for your system.
It does this mainly by collecting bus and device information from the ``/sys/bus`` tree,
which is exposed by the currently running kernel. It then relates this information to
a configuration option database (LKDDb_), and also selects required dependencies by
automatically finding a solution to the dependency tree for each option.

.. warning::

    Be aware that while this detection mechanism is nice, it is also far from perfect.
    You should work through the list of detected options and decide if you really want
    to enable them.

It might also be beneficial to run detection while using a very generic and
modular kernel, such as the default kernel on Arch Linux. This increases the
likelihood of having all necessary buses and features enabled to actually detect
connected devices. We can't detect USB devices, if the current kernel does not
support that bus in the first place. If you want this, but also don't want to
waste any time, consider running autokernel directly off an Arch Linux live system.

Comparing against the current configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Generating a module
^^^^^^^^^^^^^^^^^^^

Configuration examples
----------------------

.. _usage-build-system:

Building the kernel
-------------------

buildsystem

Command line options
--------------------

.. _usage-command-deps:

command: deps
^^^^^^^^^^^^^

abc

.. _LKDDb: https://cateee.net/lkddb/
