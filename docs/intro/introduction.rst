.. _introduction:

Introduction
============

Autokernel is primarily a kernel configuration management tool. This means
its main purpose is to be used as a tool to generate a ``.config`` file from
your particular set of kernel options. You can use it to document and build
your configuration, and it will ensure that the configuration has no conflicts.
To help you to write a good config, it comes with a set of helpful features
which are outlined below.

To skip all of the chatter, head over to :ref:`usage` to begin using autokernel
or :ref:`concepts` to learn about some important concepts in autokernel.

What problem does it solve?
---------------------------

    | » *Which kernel options do I need to enable to use this USB device?*
    | » *Why have I enabled this kernel option again?*
    | » *Which kernel options did I change compared to the default?*
    | » *Why is this option still not enabled even though i did explicitly set it?*

Does any of these question sound familiar? Then this tool might actually
solve a problem or two for you. On the other hand, if you are now thinking
what all this means, you will likely not gain any significant benefit from this tool.
But obviously you are welcome to try it out!

Feature Overview
----------------

The main feature of autokernel is kernel configuration management. In practice
this means you write an autokernel configuration and it generates a ``.config`` for
your kernel version, but with additional features:

Conflict detection
^^^^^^^^^^^^^^^^^^

    Usually, enabling an option (for example ``SECURITY_SELINUX``) but later disabling
    a direct or indirect dependency (like ``AUDITING``) will lead to the first option
    being deselected again. This is annoying and misses the original intent.
    Autokernel will exit with a conflict error in this case and present the offending
    lines in the configuration. Once set, a symbol's value will be internally pinned
    and any assignments that would change it present an error.
    See :ref:`concepts-pinning` for more info.

Satisfying dependencies
^^^^^^^^^^^^^^^^^^^^^^^

    If you enable a symbol (for example ``WLAN``), but forget to enable some of
    its dependencies (like ``NETDEVICES``), autokernel will throw an error.
    But it can also help you to resolve these dependencies and
    present you with a list of options that need to be enabled to allow the assignment.
    See :ref:`usage-command-satisfy` for more info.

Symbol validation
^^^^^^^^^^^^^^^^^

    If you mistype an option, you will get an error when building the config.
    This also works when symbols get renamed or removed in a future kernel version
    (like ``THUNDERBOLT`` is now effectively ``USB4`` since 5.6). As invalid symbol
    usage is a hard error, you will notice them before your kernel is built.

Conditionals
^^^^^^^^^^^^

    Sometimes you want to support different machines or kernel versions,
    but as the kernel evolves, symbols might get added, renamed or removed.
    By allowing simple conditional expressions in the configuration, you
    can easily evolve your config while staying backwards compatible to
    previous versions, and have one configuration for multiple machines.
    See :ref:`conditions` for more info.

Structure and Documentation
^^^^^^^^^^^^^^^^^^^^^^^^^^^

    In the configuration you will be able to properly document your choices,
    which is often neglected when using menuconfig. If done correctly, you will
    never loose track of what has been changed and more importantly why it was
    changed. You can also structure parts of the configurations into individual
    modules, which is useful if you want to use the same configuration base
    on different machines.

Detecting options
^^^^^^^^^^^^^^^^^

    Autokernel can automatically detect kernel configuration options for your system.
    This works by gathering system information from ``/sys`` and relating it to
    a configuration option database (LKDDb_). For more information
    on how it works and how to use it see :ref:`usage-detecting-options`.

Build system
^^^^^^^^^^^^

    Autokernel can optionally be used as a full kernel build system. It sounds like a lot, but
    it is actually nothing more than executing ``make`` and the specified command
    to build your initramfs (optional) for you. Eventually, a second build pass
    is needed to integrate the initramfs into the kernel. Other than that,
    it supports mounting target directories, and keeping your installation directory
    clean by only keeping the last :math:`N` builds.
    See :ref:`usage-building-installing` for more information.

Kernel hardening
^^^^^^^^^^^^^^^^

    Autokernel provides a preconfigured module for kernel hardening.
    Every choice is fully documented and explanined.
    See :ref:`usage-hardening` for more information.

But advantages never come without disadvantages. The obvious ones here are the additional
effort of writing a proper configuration instead of simply using menuconfig, and also
needing an additional tool for a task that shouldn't.

Alternative: Merging .config files
----------------------------------

Some users might already be familiar with a similar workflow, in which
you collect your changes to the default kernel configuration in one or
more kconf files, which are then applied to a fresh kernel configuration
with ``./scripts/kconfig/merge_config.sh`` from the kernel tree to create the
final configuration.

While this method does work, it has some major downsides - like the total lack
of error messages. If you mistype a config's name, nobody will tell you. You will notice
it eventually, when you have started the new kernel and wonder why something is
still not working. Other than that you might notice that even though you've typed
everything correctly, an option might still be unchanged because it had missing
dependencies. It can be a total pain to need 3 to 4 iterations of diffing config files
just to ensure everything is finally as expected.

As autokernel uses `kconfiglib`_ to parse and process the Kconfig files exactly
as the kernel would, it can directly check if options are assignable or would otherwise
conflict, and report this as a warning or error to the user.

.. _LKDDb: https://cateee.net/lkddb/
.. _kconfiglib: https://github.com/ulfalizer/Kconfiglib
