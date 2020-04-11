Conditions
==========

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
------------------------------

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
----------------------------

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
----------------------------

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
----------------

Conditions can be used in traditional block form with optional else if and else clauses,
or as python like trailing inline conditions. The block form can of course be nested, and
styles can be mixed.

Block form
^^^^^^^^^^

.. code-block:: ruby

    if <expression> {
      set A y;
    } else if <expression> {
      set A n;
    } else {
      set B n;
      set C n;
    }

Inline form
^^^^^^^^^^^

.. code-block:: ruby

    set A y if <expression>;

Is the same as

.. code-block:: ruby

    if <expression> { set A y; }


Common variables
----------------

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

TODO dont mind the ruby, it is in fact not.

This site documents autokernel's configuration file format, and shows some examples.
