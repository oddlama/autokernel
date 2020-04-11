Modules
=======

Modules are blocks in the autokernel configuration which are used to write
the actual kernel configuration. A module can :ref:`set<directive-module-set>`
symbol values, :ref:`merge<directive-module-merge>` external kconf files,
:ref:`assert<directive-module-assert>` expressions and :ref:`use<directive-module-use>`
(include) other modules. They are intended to provide a level of encapsulation for
groups of symbols.

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

All directives will pin values of evaluated / assigned symbols, except if :ref:`try set<directive-module-set-try>` is used
or an assignment is caused implicitly.

.. topic:: Pinning Example

    .. code-block:: ruby
        :linenos:

        module example {
            # Sets and pins NET to [y] (cause: explicit assignment)
            set NET y;

            # Pins USB to its current value (cause: evaluation in condition)
            if USB {
                set EXAMPLE y;
            }

            # Does not pin BT, because no statement depends on the condition
            if BT { }

            # Does nothing if WIFI is already pinned. Otherwise assigns *without* pinning.
            # Useful to impose new defaults for values but still allowing explicit changes.
            try set WIFI y;
        }

.. topic:: Conflict Example

    .. code-block:: ruby
        :linenos:

        module first {
            # Implicitly default to y, if the symbol was not assigned yet.
            # This does not pin the value.
            try set NET y;

            # If NET is actually enabled, also enable TUN
            if NET {
                set TUN y;
            }
        }

        module second {
            # As NET was pinned to [y] in line 7, this would breaks the assumption in first.
            # This means a reevaluation of first after this line would have a different result,
            # and this is an error.
            set NET n;

            # Reassigning the same value does not break previous assumptions and is therefore not an error.
            set NET n;
        }

        module example {
            use first;
            use second;
        }

Implicit vs. explicit changes
-----------------------------

Some symbols have dependencies, which will be invalidated when the symbol is
assigned. One example is MODULES. When you set MODULES to n, it will cause a lot of
implicit changes in all symbols which are configured as m to either n or y. These
changes will not pin their symbol's value, but they will conflict if the
value is already pinned and would be changed.

.. topic:: Implicit assignment

    .. code-block:: ruby
        :linenos:

        module example {
            # Implicitly sets NET to n
            try set NET n;
            # Implicitly assigns a lot of other options (all that indirectly depend on MODULES)
            set MODULES n;
        }
