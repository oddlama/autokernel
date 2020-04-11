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

    You can quote strings with ``"double"`` or ``'single'`` or single quotes. There is no difference
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
