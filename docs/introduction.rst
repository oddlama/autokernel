Introduction
============

Autokernel is primarily a kernel configuration management tool. This means
its main purpose is to be used as a tool to generate a ``.config`` file from
your particular set of kernel options. To help you accomplish this, it
comes with a set of helpful features, which are outlined below.

To skip all of the chatter, check out the :ref:`quick-start-guide`.

What problem does it solve?
---------------------------

> *Which kernel options do I need to enable to use this USB device?*

> *Why have I enabled this kernel option again?*

> *Which kernel options did I change compared to the default?*

> *Why is this option still not enabled even though i explicitly set it?*

Does any of these question sound familiar? Then this tool might actually
solve a problem or two for you. If not, you will probably not gain
any significant benefit from this tool, but you are welcome to try it out anyway.

Some users might already be familiar with a similar workflow, in which
you collect your changes to the default kernel configuration in one or
more kconf files, which are then applied to a fresh kernel configuration
with ``./scripts/kconfig/merge_config.sh`` from the kernel tree to create the
final configuration.

While this method does work, it has some major downsides - like the total lack
of errors. If you mistype a config's name, nobody will tell you. You will notice
it eventually, when you have started the new kernel and wonder why something is
still not working. Other than that you might notice that even though you've typed
everything correctly, an option might still be unchanged because it had missing
dependencies. Its a total pain in the backside to need 4-5 iterations of diffing
configs to check if everything is finally as expected. Autokernel uses `kconfiglib`_
to parse and process the Kconfig files exactly as the kernel would, and
therefore allows to check if options are assignable or would conflict.

Feature Overview
----------------

Option detection
^^^^^^^^^^^^^^^^

Autokernel can automatically detect kernel configuration options for your system.
It does this mainly by collecting bus and device information from the ``/sys/bus`` tree,
which is exposed by the currently running kernel. It then relates this information to
a configuration option database (LKDDb_), and also selects required dependencies by
automatically finding a solution to the dependency tree for each option.

.. warning::

    Be aware that this detection mechanism is far from perfect, which means you
    should work through the detected options and decide if you really want to
    enable them.

It might also be beneficial to run detection while using a very generic and
modular kernel, such as the default kernel on Arch Linux. This increases the
likelihood of having all necessary buses and features enabled to actually detect
connected devices. We can't detect USB devices, if the current kernel does not
support that bus in the first place. If you want this, but also don't want to
waste any time, consider running autokernel directly off an Arch Linux live system.

Config Management
^^^^^^^^^^^^^^^^^

- Merge external kconf files
- Detect configuration conflicts
- Conditional configuration based on kernel option values
- Reusable modules for multiple systems
- It provides a basic but still powerful configuration language, which
  is used to express your kernel configuration. This allows autokernel
  to detect errors immediately when exectiYou can even write generic modules,
  which are especially useful, if you want to reuse parts of your config for
  other systems.
- Automatically satisfy option dependencies

TODO.

Building the kernel
^^^^^^^^^^^^^^^^^^^

Autokernel can also be used as a full kernel build script.

TODO.

.. _kconfiglib: https://github.com/ulfalizer/Kconfiglib
.. _lkddb: https://cateee.net/lkddb/
