.. _concepts:

Concepts
========

This page is going to elaborate on some important concepts in autokernel.

.. _concepts-modules:

Modules
-------

Modules are blocks in the autokernel configuration which are used to write
the actual kernel configuration. A module can :ref:`set<directive-module-set>`
symbol values, :ref:`merge<directive-module-merge>` external kconf files,
:ref:`assert<directive-module-assert>` expressions, :ref:`use<directive-module-use>`
(include) other modules and :ref:`add commandline<directive-module-add-cmdline>` strings.
They are intended to provide a level of encapsulation for groups of symbols.

.. topic:: Example module

    .. code-block:: ruby
        :linenos:

        module example {
            # Asserts that the configured kernel is at least on version 4.0
            assert $kernel_version >= 4.0: "this kernel is too old!";

            # Merge in the x86_64 defconfig
            merge "{KERNEL_DIR}/arch/x86/configs/x86_64_defconfig";

            # Sets DEFAULT_MMAP_MIN_ADDR if X86 is set
            if X86 {
                set DEFAULT_MMAP_MIN_ADDR 65536;
            }

            # Include another module
            use some_dependency;
        }

        module some_dependency {
            # ...
        }

.. _concepts-pinning:

Pinning symbol values
---------------------

The first important concept is pinning. As soon as a symbol's value is changed or
observed, it will be pinned, meaning the value is then fixed.
In the beginning, all symbols will start with their default values,
as specified by the kernel's Kconfig.

Successive assigments to these symbols will become hard errors, if they would change
the pinned value. This allows modules to use logic based on symbol values,
without imposing implicit ordering constraints, or surprise pitfalls down the road.
Wrong ordering will lead to errors instead of silently breaking previous assumptions.

.. note::

    Conflicts are always errors. This ensures that the same conditions always
    has the same outcome, no matter where it stands in the configuration.

.. topic:: Pinning Examples

    .. code-block:: ruby
        :linenos:

        # Sets and pins NET to [y] (cause: explicit assignment)
        set NET y;

        # Pins USB to its current value (cause: evaluation in condition)
        if USB {
            set EXAMPLE y;
        }

        # Does not pin BT, because no statement depends on the condition
        if BT { }

        # Does nothing if IWLWIFI is already pinned. Otherwise assigns
        # *without* pinning. Useful to set new defaults for values
        # but still allowing explicit changes.
        try set IWLWIFI y;

.. topic:: Conflict Example

    .. code-block:: ruby
        :linenos:

        # If NET is enabled, also enable TUN. This pins NET.
        if NET {
            set TUN y;
        }

        # Assume NET was [y]. In that case NET is pinned to [y] in line 3.
        # This would break the assumption in line 3, as a re-evaluation of
        # the condition would have a different result.
        set NET n; # error: confilict

Implicit vs. explicit changes
-----------------------------

There are explicit and implict assignments of symbol values. All direct assignments
via ``set`` are explicit. An implicit assignment occurrs, when an explicit assignment
triggers a change in a symbols that depends on the assigned symbol.

.. note::

    Explicit changes will pin the value of a symbols, while implicit changes do not.

Implicit assignments also occurr when using the :ref:`directive-module-merge` statement.
They can also be forced by using :ref:`try set<directive-module-set>`
instead of just ``set``. This should only be used in special occasions, like when
you want to set a new default value for a symbol while still allowing the user to override it.

.. topic:: Correct usage of ``try set``

    It's a common pattern to use ``try set`` directly followed by a conditional on the same
    symbol. This way you can ensure a module works with either setting, but add a default
    in case the user didn't care:

    .. code-block:: ruby
        :linenos:

        # By default disable DEVMEM
        try set DEVMEM n;

        # If the user has still enabled it, at least enable STRICT mode
        if DEVMEM {
            set STRICT_DEVMEM y;
        }

.. warning::

    Do not use ``try set`` to resolve conflicts! A conflict always means that there is
    something wrong with your configuration or ordering. Only use ``try set`` to
    set new defaults.

.. topic:: Explicit assignments

    .. code-block:: ruby
        :linenos:

        # Explicitly sets NET to n
        set NET n;

        # Explicitly sets symbols mentioned in the given kconf file
        merge "{KERNEL_DIR}/arch/x86/configs/x86_64_defconfig";

.. topic:: Implicit assignments

    .. code-block:: ruby
        :linenos:

        # Implicitly sets NET to n
        try set NET n;

        # Implicitly assigns a lot of other options
        # (all that indirectly depend on MODULES)
        set MODULES n;
