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

module
------

.. _directive-module:

.. confval:: module <name>

    **Arguments:**

        ``name``: The module name

    Defines a new module. Definition order is not important.
    Modules can be included in other modules to provide a level
    of encapsulation for different tasks. See :ref:`Concepts → Modules<concepts-modules>`
    and :ref:`Concepts → Pinning symbol values<concepts-pinning>` for more information.

    **Example:**

        .. code-block:: ruby

            module example {
                # ...
            }

..

    **Statements:**

        .. _directive-module-set:

        .. confval:: set

                Blah


                Try does lol

        .. _directive-module-merge:

        .. confval:: merge

                Blah

        .. _directive-module-assert:

        .. confval:: assert

                Blah

        .. _directive-module-use:

        .. confval:: use

                Blah


kernel
------

initramfs
---------

build
-----

install
-------
