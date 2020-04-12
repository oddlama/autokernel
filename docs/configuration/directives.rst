Configuration Directives
========================

This is a collection of all configuration directives.

global
------

These statements can be used in the global scope outside of any block.

.. confval:: include_module <path>

    **Arguments:**

        ``path``: The path to the ``.conf`` file

    Include module definitions from a single file. Path can be absolute, or relative to
    the current working directory when executing the script. Using absolute paths is recommended,
    but relative paths can be beneficial when testing different configurations. All module files
    should end with the ``.conf`` extension.

    **Example:**

        .. code-block:: ruby

            include_module "/usr/share/autokernel/modules.d/security.conf";

.. confval:: include_module_dir <path>

    **Arguments:**

        ``path``: The path to the directory with ``.conf`` files

    Include module definitions from all ``.conf`` files in the given folder.
    Path can be absolute or relative.

    **Example:**

        .. code-block:: ruby

            include_module_dir "/etc/autokernel/modules.d";

.. _directive-module:

module
------

.. confval:: module <name> { ... }

    **Arguments:**

        ======== =============
        ``name`` The module name
        ======== =============

    Defines a new module. Definition order is not important.
    Modules can be included in other modules to provide a level
    of encapsulation for different tasks. See :ref:`Concepts → Modules<concepts-modules>`
    and :ref:`Concepts → Pinning symbol values<concepts-pinning>` for more information.

    **Example:**

        .. code-block:: ruby

            module example {
                # ...
            }

.. _directive-module-use:

use
^^^

.. confval:: use <modules>... [if <cexpr>]

    **Arguments:**

        =========== =============
        ``modules`` A list of modules to include
        ``cexpr``   Attached :ref:`condition <conditions>`
        =========== =============

    Include one or multiple a modules at this point. Referenced modules do not
    need to be defined before usage, as definition order is not important.

    If a module has already been included before, it will be skipped.
    Modules will be included in the order they are encountered in
    use statements. Due to skipping, cyclic and duplicate inclusions are impossible.
    This statement may occurr multiple times.

    **Example:**

        .. code-block:: ruby

            use foo;
            use example module_three;


.. _directive-module-set:

set
^^^

.. confval:: [try] set <symbol> [value] [if <cexpr>]

    **Arguments:**

        ========== =============
        ``symbol`` Kernel symbol name, the ``CONFIG_`` prefix is optional but discouraged.
        ``value``  The new value for the symbol (or ``y`` by default)
        ``cexpr``  Attached :ref:`condition <conditions>`
        ========== =============

    Sets the value of a symbol. Omitting the value will default to setting the symbol to ``y``.
    Prefixing symbol names with ``CONFIG_`` is allowed, but considered bad style.

    Valid values for tristate symbols are ``y`` (yes), ``m`` (as module) and ``n`` (no).
    Symbols are always assigned by string, but restrictions for type conversion apply
    (e.g. integer symbols will only take valid integers).

    If the statement is prefixed with ``try``, it will only be executed if the value is not
    already pinned, and the assignment will also not cause the value to be pinned. Useful
    to set a new default value for a symbol but still allowing the user to change it.

    Repeated assignments of the same symbol are valid, as long as the same value is assigned
    each time, or the assignment uses the ``try set``. Conflicts will cause hard errors.

    **Example:**

        .. code-block:: ruby

            # Enable WIREGUARD if kernel version is at least 5.6
            set WIREGUARD y if $kernel_version >= 5.6;
            # Build KVM as module
            set KVM m;
            # Set a hex symbol
            set MAGIC_SYSRQ_DEFAULT_ENABLE 0x1;
            # Set an integer symbol
            set DEFAULT_MMAP_MIN_ADDR 65536;
            # Set a string symbol
            set DEFAULT_HOSTNAME "my_host";
            # Try to set MODULES, if it isn't pinned already
            try set MODULES n;

.. _directive-module-merge:

merge
^^^^^

.. confval:: merge <path> [if <cexpr>]

    **Arguments:**

        ========= =============
        ``path``  The path to the kconf file
        ``cexpr`` Attached :ref:`condition <conditions>`
        ========= =============

    **Variables:**

        Allowed in ``path``.
        See :ref:`common-variables`.

    Merges an external kernel configuration file. This can be a whole .config file
    or just a collection of random symbol assignments (as it is the case for the defconfig files).
    All merged values will count as implicit changes (no pinning). They will trigger
    conflicts if a variable is already pinned.

    .. warning::

        Because of the implicit nature, the merge statement should only be used to include
        default values, and not to externalize parts of the config.

    **Example:**

        .. code-block:: ruby

            # Merge the x86_64 defconfig file
            merge "{KERNEL_DIR}/arch/x86/configs/x86_64_defconfig";


.. _directive-module-assert:

assert
^^^^^^

.. confval:: assert <aexpr> [<quoted_message>] [if <cexpr>]

    **Arguments:**

        ================== =============
        ``aexpr``          Expression to assert
        ``quoted_message`` An error message to display in case the assertion fails
        ``cexpr``          Attached :ref:`condition <conditions>`
        ================== =============

    Asserts that a given expression evaluates to true,
    otherwise causes an error and optionally prints the given error message.

    **Example:**

        .. code-block:: ruby

            # Assert that WIREGUARD is enabled if the kernel version is at least 5.6
            assert $kernel_version >= 5.6 and WIREGUARD
                "Refusing to compile a 5.6 kernel without wireguard";

.. _directive-module-add-cmdline:

add_cmdline
^^^^^^^^^^^

.. confval:: add_cmdline <quoted_params>... [if <cexpr>]

    **Arguments:**

        ================= =============
        ``quoted_params`` A list of strings to append to ``CMDLINE``
        ``cexpr``         Attached :ref:`condition <conditions>`
        ================= =============

    Adds the given parameters to the kernel commandline. Quotation is
    required. This will automatically set the ``CMDLINE`` symbol to the resulting
    string and enable the builtin commandline via ``CMDLINE_BOOL``.

    **Example:**

        .. code-block:: ruby

            # Adds the two strings to the builtin command line.
            add_cmdline "page_alloc.shuffle=1" "second_param";


kernel
------

initramfs
---------

build
-----

install
-------
