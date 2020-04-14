.. _syntax:

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

.. _syntax-bool:

.. topic:: Booleans

    Boolean options recognize the following arguments:

        ============= =========================================
        Boolean value Recognized aliases
        ============= =========================================
        ``false``     ``false``, ``0``, ``no``,  ``n``, ``off``
        ``true``      ``true``,  ``1``, ``yes``, ``y``, ``on``
        ============= =========================================

.. topic:: Strings

    You can optionally quote strings with ``"double"`` or ``'single'`` quotes.
    There is no semantic difference between the two quoting styles. Quoting ist
    mostly optional, but some option parameters require quoting (will be specified).
    In quoted strings, you can use the following escape sequences:

        ================== ===========================
        Escape sequence    Meaning
        ================== ===========================
        ``\\``             Single backslash ``\``
        ``\"``             ``"``
        ``\'``             ``'``
        ``\n``             Newline
        ``\r``             Carriage Return
        ``\t``             Tab
        ``\x1b``           2-digit hex escapes
        ``\033``           Octal escapes
        ``\u2665``         4-digit unicode hex escapes
        ``\U0001f608``     8-digit unicode hex escapes
        ``\N{Dark Shade}`` Unicode characters by name
        ================== ===========================

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


.. _common-variables:

Common variables
----------------

In several places you will be able to refer to variables. Mostly
in strings and pathnames. All statements will explicitly state which
variables can be used in the description of the directive.

The common variables are:

==================== ================================================
Name                 Description
==================== ================================================
``{KERNEL_DIR}``     The current kernel directory path
``{KERNEL_VERSION}`` The current kernel version
``{ARCH}``           The host architecture as the kernel sees it
``{UNAME_ARCH}``     The host architecture as ``uname -m`` reports it
==================== ================================================

.. note::

    The internal kernel architecture differs from ``uname -m``. For example
    it will be ``x86`` for both ``x86`` and ``x86_64`` systems.

.. _conditions:

Conditional Expressions
-----------------------

Autokernel supports conditions for all statements in :ref:`directive-module` blocks.
They will only be executed if all attached conditions are met.

Overview
^^^^^^^^

Conditions can be used in both traditional form with optional ``else if`` and ``else`` blocks,
or as python like trailing conditions. The block form can of course be nested, and
styles can be mixed freely.

.. topic:: Block form

    .. code-block:: ruby

        # Traditional if clause with optional blocks
        if <expression> {
            set A y;
        } else if <expression> {
            set A n;
        } else {
            # Nested block
            if <expression> {
                set B n;
            }

            set C n;
        }

.. topic:: Inline short form

    .. code-block:: ruby

        set A y if <expression>;

        # is the same as
        if <expression> {
            set A y;
        }

    .. note::

        Trailing conditions are currently attached to the whole statement and cannot use an
        ``else`` token to specify an alternate value.

Expressions
^^^^^^^^^^^

Expressions are written as they are in most other programming languages:

.. topic:: Expression syntax

    ========================== ============================================
    Expression                 Meaning
    ========================== ============================================
    ``A or  B``, ``A || B``    (A ∨ B)
    ``A and B``, ``A && B``    (A ∧ B)
    ``A or B and C``           (A ∨ (B ∧ C))
    ``not A``, ``!A``          ¬A
    ``A``                      Shorthand for ``A != 'n'``
    ``A <cmp> B``              Comparison. See :ref:`conditions-comparison`
    ========================== ============================================

.. topic:: Operator precedence

    #. ``()``: expression grouping
    #. ``A <cmp> B``: any explicit comparison
    #. ``not``: inversion operator
    #. ``and``: and clauses
    #. ``or``: or clauses

.. _conditions-comparison:

Comparisons
^^^^^^^^^^^

All expressions boil down to comparisons.

Comparison syntax
~~~~~~~~~~~~~~~~~

========================== ===============================
Expression                 Meaning
========================== ===============================
``A == B``, ``A is B``     A is     equal to B
``A != B``, ``A is not B`` A is not equal to B
``A <= B``                 A is less    than or equal to B
``A < B``                  A is less    than             B
``A >= B``                 A is greater than or equal to B
``A > B``                  A is greater than             B
========================== ===============================

.. topic:: Chaining

    All comparison operators can be chained. This means you can write
    ``4.0 <= $kernel_version < 5.0``, or even ``A != B != C != D``.
    There is no difference between chaining and writing the expanded form.

    .. note::

        Comparisons in chained form will always compare actual values and *never*
        intermediate truth values.
        ``A != B != C`` is guaranteed to be the same as ``A != B and B != C``.

Type inference
~~~~~~~~~~~~~~

The result of a comparison depends on the inferred type, as for example strings
comparisons are different to integer comparisons. The rules are simple:

#. Literals have no type and will inherit the type from the rest of the expression.
#. Kernel symbols and special variables have fixed types.
#. If no type can be inferred, string comparison will be used (e.g. when comparing two literals).
#. Variables of different types cannot be mixed.

.. _expr-special-variables:

Special variables
~~~~~~~~~~~~~~~~~

There are several special variables which you can use in comparison expressions.
They must be used in unquoted form and will allow you to depend on runtime information.

========================== ======== =================================================
Variable                   Type     Description
========================== ======== =================================================
``$kernel_version``        semver   Expands to the semver of the specified kernel
``$uname_arch``            string   The uname as reported by ``uname -m``
``$arch``                  string   The architecture as seen by the kernel internally
``$false``                 tristate Always ``'n'``
``$true``                  tristate Always ``'y'``
``$env[VAR]``              string   Environment variable ``VAR``, throws an error if unset
``$env[VAR:<quoted_str>]`` string   Environment vairable ``VAR`` or the given default
========================== ======== =================================================

Comparison types
~~~~~~~~~~~~~~~~

These are the existing comparison types:

============ =========================================================================
Type         Description
============ =========================================================================
``string``   Lexicographical comparison
``int``      Integer comparison, base 10
``hex``      Integer comparison, base 16, requires ``0x`` prefix
``tristate`` Same as for string, but arguments are restricted to ``n``, ``m`` or ``y``
``semver``   Semantic versioning comparison
============ =========================================================================

.. note::

    The format for semver versions is ``major[.minor[.patch[-ignored]]]``.
    Missing parts are treated as ``0``, which makes ``4`` equal to ``4.0.0``.

.. topic:: Valid expression examples

    ============================ =======================================
    Comparison expression        Type
    ============================ =======================================
    ``SOME_STRING == abc``       string
    ``SOME_STRING == "abc"``     string
    ``SOME_INT < 1``             int
    ``SOME_INT < "1"``           int
    ``SOME_HEX == 0x1``          hex
    ``SOME_TRISTATE == 'n'``     tristate
    ``SOME_TRISTATE == 'm'``     tristate
    ``SOME_TRISTATE == 'y'``     tristate
    ``12345 != 12``              string
    ``$env[CC] == "gcc"``        string
    ``$kernel_version >= 5.6``   semver
    ``SOME_TRISTATE``            tristate (implicit bool conversion)
    ``SOME_STRING``              string (implicit bool conversion)
    ``$env[HOSTNAME]``           string (implicit bool conversion)
    ============================ =======================================

.. topic:: Invalid expression examples

    ================================ =======================================
    Comparison expression            Type and reason for invalidity
    ================================ =======================================
    ``SOME_STRING <= "abc"``         string, invalid operator for string
    ``SOME_STRING < 1``              string, invalid operator for string
    ``SOME_HEX > 1``                 hex, invalid prefix
    ``SOME_INT == SOME_HEX``         cannot mix types
    ``$kernel_version >= SOME_INT``  cannot mix types
    ``SOME_HEX``                     hex, invalid implicit bool conversion
    ================================ =======================================

Implicit bool conversion
~~~~~~~~~~~~~~~~~~~~~~~~

All kernel symbols, all tristate special variables and ``$env[...]`` variables can implicitly be converted to bool.
This means you can use these short forms:

.. code-block:: ruby

    # Same as X86 != n (X86 is a tristate symbol)
    if X86 { ... }

    # Same as DEFAULT_HOSTNAME != "" (DEFAULT_HOSTNAME is a string symbol)
    if DEFAULT_HOSTNAME { ... }

    # Same as $false != n
    if $false { ... }

    # Same as $env[TEST] != ""
    if $env[TEST] { ... }

Short-circuiting (early-out)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All expressions support short-circuiting. The main reason is for this is
that it allows conditional pinning. Consider the symbol ``USB4``, which
was first introduced in kernel version ``5.6``. Just writing the conditional
block

.. code-block:: ruby

    if USB4 {
        # ...
    }

would fail on all kernels older than ``5.6``, since the symbol ``USB4`` does not
exist and therefore will raise an error in the expression. But if you change the
statement to

.. code-block:: ruby

    if $kernel_version >= 5.6 and USB4 {
        # ...
    }

the short circuiting of the expression will prevent the ``USB4`` part from
being evaluated when the kernel version constraint is not met.
This allows to maintain compatibility to several kernel versions.
