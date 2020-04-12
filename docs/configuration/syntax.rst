Configuration Syntax
====================

First of all, here is a short example for a configuration that is builds upon
on the ``x86_64_defconfig``, disables ``MODULES`` and enables ``WIREGUARD`` if the
kernel version is greater than 5.6:

.. code-block:: ruby
    :caption: Short configuration example
    :linenos:

    module base {
        # Begin with the x86_64 defconfig
        merge "{KERNEL_DIR}/arch/x86/configs/x86_64_defconfig";
        # Disable modules
        set MODULES n;
    }

    kernel {
        use base;

        # Enable wireguard on new kernels
        set WIREGUARD y if $kernel_version >= 5.6;
    }

General Syntax
--------------

.. topic:: Whitespace

    The configuration format is not sensitive to whitespace. Sometimes, a whitespace
    character is needed to separate tokens, but other than that whitespace is ignored.

.. topic:: Comments

    The comment character is '#'. It can be appended to any line and will
    comment everything until the end of that line.

.. topic:: Booleans

    Boolean options recognize the following arguments:

        +---------------+------------------------+
        | Boolean value | Recognized aliases     |
        +===============+========================+
        | ``false``     | false, 0, no,  n, off  |
        +---------------+------------------------+
        | ``true``      | true,  1, yes, y, on   |
        +---------------+------------------------+

.. topic:: Strings

    You can quote strings with ``"double"`` or ``'single'`` quotes. There is no difference
    between the two. In quoted strings, you can use the following escape sequences:

        +--------------------+-----------------------------+
        | Escape sequence    | Meaning                     |
        +====================+=============================+
        | ``\\``             | Single backslash ``\``      |
        +--------------------+-----------------------------+
        | ``\"``             | ``"``                       |
        +--------------------+-----------------------------+
        | ``\'``             | ``'``                       |
        +--------------------+-----------------------------+
        | ``\n``             | Newline                     |
        +--------------------+-----------------------------+
        | ``\r``             | Carriage Return             |
        +--------------------+-----------------------------+
        | ``\t``             | Tab                         |
        +--------------------+-----------------------------+
        | ``\x1b``           | 2-digit hex escapes         |
        +--------------------+-----------------------------+
        | ``\033``           | Octal escapes               |
        +--------------------+-----------------------------+
        | ``\u2665``         | 4-digit unicode hex escapes |
        +--------------------+-----------------------------+
        | ``\U0001f608``     | 8-digit unicode hex escapes |
        +--------------------+-----------------------------+
        | ``\N{Dark Shade}`` | Unicode characters by name  |
        +--------------------+-----------------------------+

.. topic:: Blocks

    Blocks are enclosed in brackets, like ``blockname { }``.
    Empty blocks may be omitted.

.. topic:: Statements

    Statements are terminated with a semicolon ``;``.
    Different blocks allow different statements.

.. topic:: Formal specification (EBNF)

    For an EBNF like description of the config syntax, refer to
    the `config.lark <https://github.com/oddlama/autokernel/blob/master/autokernel/config.lark>`_
    file inside the autokernel python module directory.

.. topic:: Syntax highlighting

    You can use ruby syntax highlighting, which gives quite good results (at least in vim).


Common variables
----------------

In several places you will be able to refer to variables.
Those cases will be explicitly stated in the description of the directive.
The common variables are:

+----------------------+--------------------------------------------------+
| Name                 | Description                                      |
+======================+==================================================+
| ``{KERNEL_DIR}``     | The current kernel directory path.               |
+----------------------+--------------------------------------------------+
| ``{KERNEL_VERSION}`` | The current kernel version.                      |
+----------------------+--------------------------------------------------+
| ``{ARCH}``           | The host architecture as the kernel sees it      |
+----------------------+--------------------------------------------------+
| ``{UNAME_ARCH}``     | The host architecture as ``uname -m`` reports it |
+----------------------+--------------------------------------------------+

Conditions
----------

Statements in module blocks may have conditions attached to them. They will
only be executed if all conditions are met.

Conditions are expressions in traditional form, operator precedence is
not, and, or. The following expressions are allowed:

- A or  B, A || B    # (A ∨ B)
- A and B, A && B    # (A ∧ B)
- A or B and C       # (A ∨ (B ∧ C))
- not A, !A          # ¬A
- A                  # Shorthand for A != 'n'
- A == B, A is B     # A is     equal to B
- A != B  A is not B # A is not equal to B
- A <= B             # A is less    than or equal to B
- A <  B             # A is less    than             B
- A >= B             # A is greater than or equal to B
- A >  B             # A is greater than             B

All comparison operators can be chained: A <= B <= C, or even A != B != C, and are
always exactly the same as writing them in expanded form like A <= B and B <= C,
or A != B and B != C. Autokernel will fold these expressions and compare results of
intermediate truth values.

Comparisons and variable types
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All expressions boil down to comparisons, and how variables are compared depends
on their type:

- Literals have no type and will inherit the type from the rest of the expression.
- Kernel options and special variables have fixed types.
- Comparing two literals will always fall back to string comparison.

Comparison types
^^^^^^^^^^^^^^^^

- string   → does lexicographical comparison
- int      → integer comparison, base 10
- hex      → integer comparison, base 16, and requires 0x prefix.
- tristate → same as string, but restricts arguments to n, m, y
- semver   → semantic versioning comparison, format is major[.minor[.patch[-ignored]]],
             4 is the same as 4.0.0

Have a look at the following comparisons, their comparison type and their validity:
- SOME_STRING     == abc   (string, valid)
- SOME_STRING     == "abc" (string, valid)
- SOME_STRING     <= "abc" (string, invalid operator for string)
- SOME_STRING     <   1    (string, invalid operator for string)
- SOME_INT        <   1    (int, valid)
- SOME_INT        <  "1"   (int, valid)
- SOME_HEX        <=  1    (hex, invalid prefix)
- SOME_HEX        ==  0x1  (hex, valid)
- SOME_TRISTATE   == 'n'   (tristate, valid)
- SOME_TRISTATE   == 'm'   (tristate, valid)
- SOME_TRISTATE   == 'y'   (tristate, valid)
- 12345           !=  12   (string, valid)
- $kernel_version >=  5.6  (semver, valid)


Special comparison variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There are several special variables which must be used in unquoted form
and will allow you to depend on runtime information.

+---------------------+----------+--------------------------------------------------------------------------------------+
| Variable            | Type     | Description                                                                          |
+=====================+==========+======================================================================================+
| ``$kernel_version`` | semver   | Expands to the semver of the specified kernel                                        |
+---------------------+----------+--------------------------------------------------------------------------------------+
| ``$uname_arch``     | string   | The uname as reported by uname -m                                                    |
+---------------------+----------+--------------------------------------------------------------------------------------+
| ``$arch``           | string   | The architecture as seen by the kernel internally (e.g. x86 for both x86 and x86_64) |
+---------------------+----------+--------------------------------------------------------------------------------------+
| ``$false``          | tristate | Always 'n'                                                                           |
+---------------------+----------+--------------------------------------------------------------------------------------+
| ``$true``           | tristate | Always 'y'                                                                           |
+---------------------+----------+--------------------------------------------------------------------------------------+


Short-circuiting (early-out)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All expressions support short-circuiting. The main reason is that you can do conditional
pinning with short circuiting.

Consider the symbol USB4, which was first introduced in kernel 5.6. The statement

.. code-block:: ruby

    if USB4 { ... }

would fail on older kernels, since the symbol USB4 cannot be found there.
If you change the statement to

.. code-block:: ruby

    if $kernel_version >= 5.6 and USB4 { ... }

the USB4 will only be evaluated when the kernel version constraint is already met.
This allows the code to be used on all kernel versions.

Using conditions
^^^^^^^^^^^^^^^^

Conditions can be used in traditional block form with optional else if and else clauses,
or as python like trailing inline conditions. The block form can of course be nested, and
styles can be mixed.

.. topic:: Block form

    .. code-block:: ruby

        if <expression> {
            set A y;
        } else if <expression> {
            set A n;
        } else {
            set B n;
            set C n;
        }

.. topic:: Inline form

    .. code-block:: ruby

        set A y if <expression>;

    Is the same as

    .. code-block:: ruby

        if <expression> { set A y; }

TODO dont mind the ruby, it is in fact not.

This site documents autokernel's configuration file format, and shows some examples.

Directives
----------

.. _directive-module-set:
.. _directive-module-set-try:
.. _directive-module-merge:
.. _directive-module-assert:
.. _directive-module-use:

module
^^^^^^

.. glossary::

    set

        Blah


        Try does lol

    merge
        Blah

    assert
        Blah

    use
        Blah


kernel
^^^^^^

initramfs
^^^^^^^^^

build
^^^^^

install
^^^^^^^
