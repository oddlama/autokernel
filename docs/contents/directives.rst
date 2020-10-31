.. _directives:

Configuration Directives
========================

This is a documentation of all configuration directives.

global
------

The following block directives may appear in the unnamed global scope:

========= ===========
Block     Description
========= ===========
module    See :ref:`directive-module`.
kernel    See :ref:`directive-kernel`.
initramfs See :ref:`directive-initramfs`.
build     See :ref:`directive-build`.
install   See :ref:`directive-install`.
========= ===========

Additionally the following statements may be used:

.. _directive-global-include-module:

include_module
^^^^^^^^^^^^^^

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

.. _directive-global-include-module-dir:

include_module_dir
^^^^^^^^^^^^^^^^^^

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
                use example_dep;

                set EXAMPLE y;
            }

.. _directive-module-if:

if
^^

.. confval:: module :: if <expr> { ... } [else if <expr> { ... }]... [else <expr> { ... }]

    **Arguments:**

        =========== =============
        ``expr``    Expressions
        =========== =============

    Guards statements with the given expressions.

    **Example:**

        .. code-block:: ruby

            module example {
                if X86 {
                    # X86 is set
                } else if $env[CC] == "gcc" {
                    # env var CC is "gcc"
                }

                if $env[HOSTNAME:""] {
                    # env var HOSTNAME is set
                } else {
                    # env var HOSTNAME is empty or unset
                }
            }

.. _directive-module-use:

use
^^^

.. confval:: module :: use <modules>... [if <cexpr>]

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

            module example {
                use foo;
                use other_example module_three;
            }

.. _directive-module-set:

set
^^^

.. confval:: module :: [try] set <symbol> [value] [if <cexpr>]

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

    Variables can be set to environment variables by using the same syntax as
    described in :ref:`expr-special-variables`.

    If the statement is prefixed with ``try``, it will only be executed if the value is not
    already pinned, and the assignment will also not cause the value to be pinned. Useful
    to set a new default value for a symbol but still allowing the user to change it.

    Repeated assignments of the same symbol are valid, as long as the same value is assigned
    each time, or the assignment uses the ``try set``. Conflicts will cause hard errors.

    **Example:**

        .. code-block:: ruby

            module example {
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
                # Set to an environment variable, throws an error if unset
                set DEFAULT_HOSTNAME $env[HOSTNAME];
                # Set to an environment variable, or uses the default value if unset
                set DEFAULT_HOSTNAME $env[HOSTNAME:"(none)"];

                # Try to set MODULES, if it isn't pinned already
                try set MODULES n;
            }

.. _directive-module-merge:

merge
^^^^^

.. confval:: module :: merge <path> [if <cexpr>]

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

            module example {
                # Merge the x86_64 defconfig file
                merge "{KERNEL_DIR}/arch/x86/configs/x86_64_defconfig";
            }

.. _directive-module-assert:

assert
^^^^^^

.. confval:: module :: assert <aexpr> [: <quoted_message>] [if <cexpr>]

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

            module example {
                # Assert that WIREGUARD is enabled if the kernel version is at least 5.6
                assert $kernel_version >= 5.6 and WIREGUARD :
                    "Refusing to compile a 5.6 kernel without wireguard";
            }

.. _directive-module-add-cmdline:

add_cmdline
^^^^^^^^^^^

.. confval:: module :: add_cmdline <quoted_args>... [if <cexpr>]

    **Arguments:**

        =============== =============
        ``quoted_args`` A list of strings to append to ``CMDLINE``
        ``cexpr``       Attached :ref:`condition <conditions>`
        =============== =============

    Adds the given parameters to the kernel commandline. Quotation is
    required. This will automatically set the ``CMDLINE`` symbol to the resulting
    string and enable the builtin commandline via ``CMDLINE_BOOL``.

    **Example:**

        .. code-block:: ruby

            module example {
                # Adds the two strings to the builtin command line.
                add_cmdline "page_alloc.shuffle=1" "second_param";
            }

.. _directive-kernel:

kernel
------

.. confval:: kernel { ... }

    A block for kernel related options. Multiple appearances of this block will be merged.
    The kernel block is also a :ref:`directive-module` block. It represents
    the main module which is included by autokernel.

    **Example:**

        .. code-block:: ruby

            kernel {
                use hardening;
                use my_module;
            }

.. _directive-initramfs:

initramfs
---------

.. confval:: initramfs { ... }

    A block for initramfs related options.
    Multiple appearances of this block will be merged.

    **Example:**

        .. code-block:: ruby

            initramfs {
                enabled true;
                builtin true;
            }

.. _directive-initramfs-enabled:

enabled
^^^^^^^

.. confval:: initramfs :: enabled <bool>

    **Arguments:**

        ======== =============
        ``bool`` A :ref:`boolean value <syntax-bool>`
        ======== =============

    **Default:** ``false``

    Enables or disables building an initramfs. When using autokernel
    to build the kernel.

    **Example:**

        .. code-block:: ruby

            # Enable the initramfs
            enabled true;

.. _directive-initramfs-builtin:

builtin
^^^^^^^

.. confval:: initramfs :: builtin <bool>

    **Arguments:**

        ======== =============
        ``bool`` A :ref:`boolean value <syntax-bool>`
        ======== =============

    **Default:** ``false``

    This will determine if the initramfs will be integrated into the kernel. It will
    cause an automatic second kernel build pass, to first allow the initramfs
    to include any modules for the newly built kernel, and secondly to pack the initramfs
    into the kernel. The second build will not require any rebuilds of previously
    compiled components, and should thus be quick.

    **Example:**

        .. code-block:: ruby

            # Use a builtin initramfs
            builtin true;

.. _directive-initramfs-build-command:

build_command
^^^^^^^^^^^^^

.. confval:: initramfs :: build_command <exe> [<args>...]

    **Arguments:**

        ======== =============
        ``exe``  The command to execute
        ``args`` parameters to the command
        ======== =============

    **Default:** ``None``

    **Variables:**

        Allowed in ``exe`` and ``args``.

        - Any of the :ref:`common-variables`

        - ``{MODULES_PREFIX}``

            A directory which contains all installed modules.
            This means the subdirectory ``{MODULES_PREFIX}/lib/modules``
            exists and can be used by the initramfs generator
            to include compiled modules for the new kernel.

        - ``{INITRAMFS_OUTPUT}``

            The desired output file for the initramfs.
            If your generator doesn't support this, you can
            specify an alternate location with :ref:`directive-initramfs-build-output`.

    Specifies the command used to build the initramfs. The resulting initramfs
    should directly be placed at ``{INITRAMFS_OUTPUT}``. If your generator
    does not support this, you can fallback to the :ref:`directive-initramfs-build-output` statement
    to specify where the finished initramfs will be.

    .. note::

        Each string in ``<args>`` is a separate argument to the command, and arguments
        will never be interpreted or split on spaces. If you need more logic here,
        please execute a wrapper script to do so.

    This statement is required, if the initramfs is enabled.

    **Example:**

        .. code-block:: ruby
            :caption: Building an initramfs with dracut

            # You can use a command like this to build an initramfs with dracut
            build_command "dracut"
                "--conf"          "/dev/null" # Disables external configuration
                "--confdir"       "/dev/null" # Disables external configuration
                "--kmoddir"       "{MODULES_PREFIX}/lib/modules/{KERNEL_VERSION}"
                "--kver"          "{KERNEL_VERSION}"
                "--no-compress"   # Only if the initramfs is to be integrated into the kernel
                "--no-hostonly"
                "--ro-mnt"
                "--add"           "bash crypt crypt-gpg"
                "--force"         # Overwrite existing files
                "{INITRAMFS_OUTPUT}";

        .. code-block:: ruby
            :caption: Building an initramfs with genkernel

            # You can use a command like this to build an initramfs with genkernel
            build_command "genkernel"
                "--kernel-modules-prefix={MODULES_PREFIX}"
                "--cachedir=/var/tmp/genkernel/cache"
                "--tmpdir=/var/tmp/genkernel"
                "--logfile=/var/tmp/genkernel/genkernel.log"
                "--kerneldir={KERNEL_DIR}"
                "--no-install"
                "--no-mountboot"
                "--no-compress-initramfs"
                "--no-ramdisk-modules"
                "--luks"
                "--gpg"
                "initramfs";
            build_output "/var/tmp/genkernel/initramfs-{UNAME_ARCH}-{KERNEL_VERSION}";

.. _directive-initramfs-build-output:

build_output
^^^^^^^^^^^^

.. confval:: initramfs :: build_output <path>

    **Arguments:**

        ========== =============
        ``path``   The path where the finished initramfs will be
        ========== =============

    **Default:** ``None``

    **Variables:**

        Same as for :ref:`directive-initramfs-build-command`.

    Optional. Specifies where the output from the initramfs build
    command will be. You do not need to specify this, if your generator placed
    the initramfs at location given via ``{INITRAMFS_OUTPUT}``.

.. _directive-build:

build
-----

.. confval:: build { ... }

    A block for build related options.
    Multiple appearances of this block will be merged.

    **Example:**

        .. code-block:: ruby

            build {
                umask 0077;
            }

.. _directive-build-umask:

umask
^^^^^

.. confval:: build :: umask <value>

    **Arguments:**

        ========== =============
        ``value``  Octal umask value to use
        ========== =============

    **Default:** ``0077``

    Specifies the umask used while building the kernel and the initramfs.

    .. note::

        If you are tempted to set this to 022 (allow read for others), you should probably
        rethink your build process. This can expose valuable information about your kernel
        to other users and renders some hardening methods useless.

    **Example:**

        .. code-block:: ruby

            build {
                # Set umask to 0027.
                umask 0027;
            }

.. _directive-build-hooks:

hooks
^^^^^

.. confval:: build :: hooks { ... }

    **Default:** ``None``

    See :ref:`directive-hooks` for more information.
    Specifies hooks for the build phase.

    **Example:**

        .. code-block:: ruby

            build {
                hooks {
                    pre "echo" "pre-build";
                }
            }

.. _directive-install:

install
-------

.. confval:: install { ... }

    A block for options related to target installation.
    Multiple appearances of this block will be merged.

    **Example:**

        .. code-block:: ruby

            install {
                # Disable initramfs installation
                target_initramfs false;
            }

.. _directive-install-umask:

umask
^^^^^

.. confval:: install :: umask <value>

    **Arguments:**

        ========== =============
        ``value``  Octal umask value to use
        ========== =============

    **Default:** ``0077``

    Specifies the umask used while installing files.

    **Example:**

        .. code-block:: ruby

            install {
                # Set umask to 0027.
                umask 0027;
            }

.. _directive-install-assert-mounted:

assert_mounted
^^^^^^^^^^^^^^

.. confval:: install :: assert_mounted <path>

    **Arguments:**

        ========== =============
        ``path``   The directory to assert is mounted
        ========== =============

    Asserts that the given directory is a mountpoint.
    Otherwise, autokernel will abort installation.

    **Example:**

        .. code-block:: ruby

            install {
                # Abort installation if /boot is not mounted
                assert_mounted "/boot";
            }

.. _directive-install-mount:

mount
^^^^^

.. confval:: install :: mount <path>

    **Arguments:**

        ========== =============
        ``path``   The directory to mount
        ========== =============

    Temporarily mounts the given directory. Will be unmounted after installation, in
    case it had to be mounted. Requires an fstab entry for the directory.
    Autokernel will abort if the directory could not be mounted.
    If you use this, an additional :ref:`directive-install-assert-mounted` entry is unnecessary.

    **Example:**

        .. code-block:: ruby

            install {
                # Mount /boot before installation
                mount "/boot";
            }

.. _directive-install-modules-prefix:

modules_prefix
^^^^^^^^^^^^^^

.. confval:: install :: modules_prefix <path>

    **Arguments:**

        ========== =============
        ``path``   The prefix path for ``make modules_install``
        ========== =============

    **Default:** ``/``

    **Variables:**

        Allowed in ``path``.
        See :ref:`common-variables`.

    The prefix path for ``make modules_install``. This must an absolute path.
    Installation can be disabled by setting this to a false :ref:`boolean value <syntax-bool>`.

    **Example:**

        .. code-block:: ruby

            install {
                # Install into '/' (default)
                modules_prefix "/";

                # Disable installing modules
                modules_prefix false;
            }

.. _directive-install-target-dir:

target_dir
^^^^^^^^^^

.. confval:: install :: target_dir <path>

    **Arguments:**

        ========== =============
        ``path``   The target directory when installing files
        ========== =============

    **Default:** ``/boot``

    **Variables:**

        Allowed in ``path``.
        See :ref:`common-variables`.

    The target installation directory. All other ``target_*`` statements will be relative
    to this directory. Must be an absolute path.

    **Example:**

        .. code-block:: ruby

            install {
                # Proper target directory for an efi partition mounted in /boot/efi
                target_dir "/boot/efi/EFI";
            }

.. _directive-install-target-kernel:

target_kernel
^^^^^^^^^^^^^

.. confval:: install :: target_kernel <path>

    **Arguments:**

        ========== =============
        ``path``   The kernel target path
        ========== =============

    **Default:** ``bzImage-{KERNEL_VERSION}``

    **Variables:**

        Allowed in ``path``.
        See :ref:`common-variables`.

    The target path for the kernel image. This is relative to :ref:`directive-install-target-dir`,
    but may also be an absolute path if desired. Installation can be disabled by
    setting this to a false :ref:`boolean value <syntax-bool>`.

    **Example:**

        .. code-block:: ruby

            install {
                # Don't include version number and use .efi suffix
                target_kernel "bzImage.efi";
                # Disable installing the kernel image
                target_kernel false;
            }

.. _directive-install-target-config:

target_config
^^^^^^^^^^^^^

.. confval:: install :: target_config <path>

    **Arguments:**

        ========== =============
        ``path``   The config target path
        ========== =============

    **Default:** ``config-{KERNEL_VERSION}``

    **Variables:**

        Allowed in ``path``.
        See :ref:`common-variables`.

    The target path for a backup of the generated config. This is relative to
    :ref:`directive-install-target-dir`, but may also be an absolute path if desired.
    Installation can be disabled by setting this to a false :ref:`boolean value <syntax-bool>`.

    **Example:**

        .. code-block:: ruby

            install {
                # Disable installing the config
                target_config false;
            }

.. _directive-install-target-initramfs:

target_initramfs
^^^^^^^^^^^^^^^^

.. confval:: install :: target_initramfs <path>

    **Arguments:**

        ========== =============
        ``path``   The initramfs target path
        ========== =============

    **Default:** ``initramfs-{KERNEL_VERSION}.cpio``

    **Variables:**

        Allowed in ``path``.
        See :ref:`common-variables`.

    The target path for the initramfs image. This is relative to :ref:`directive-install-target-dir`,
    but may also be an absolute path if desired. Installation can be disabled by
    setting this to a false :ref:`boolean value <syntax-bool>`.
    This option only has an effect if the initramfs is enabled.

    **Example:**

        .. code-block:: ruby

            install {
                # Disable installing the initramfs image
                target_initramfs false;
            }

.. _directive-install-keep-old:

keep_old
^^^^^^^^

.. confval:: install :: keep_old <number>

    **Arguments:**

        ========== =============
        ``number`` Number of old builds to keep
        ========== =============

    **Default:** ``-1`` (disable purging)

    Automatic purging of old files. Determines the amount of old installed files to keep.
    Only has an effect on ``target_dir`` and ``target_*`` if ``{KERNEL_VERSION}`` is used
    in the path. A negative value like ``-1`` disables purging completely, which is the default.

    .. warning::

        Purging is done immediately after installing a file. The ``{KERNEL_VERSION}`` token
        will be replaced in all paths with a semver wildcard. All matching paths older than
        the given amount of builds will be removed.

    **Example:**

        .. code-block:: ruby

            install {
                # Keep previous two builds, purge the rest
                keep_old 2;
            }

.. _directive-install-hooks:

hooks
^^^^^

.. confval:: install :: hooks { ... }

    **Default:** ``None``

    See :ref:`directive-hooks` for more information.
    Specifies hooks for the install phase.

    **Example:**

        .. code-block:: ruby

            install {
                hooks {
                    pre "echo" "pre-install";
                }
            }

.. _directive-hooks:

hooks
-----

.. confval:: hooks { ... }

    A block for hooks. Multiple appearances of this block will be merged.
    Specifies pre and post hooks for the phase in which the block is included.

    **Example:**

        .. code-block:: ruby

            hooks {
                pre  "echo" "pre-hook";
                post "echo" "post-hook";
            }

.. _directive-hooks-pre:

pre
^^^

.. confval:: hooks :: pre <exe> [<args>...]

    **Arguments:**

        ======== =============
        ``exe``  The command to execute
        ``args`` parameters to the command
        ======== =============

    **Default:** ``None``

    **Variables:**

        Allowed in ``exe`` and ``args``.
        See :ref:`common-variables`.

    Optional. Defines a pre hook. If the hook returns an
    unsuccessful exit code, autokernel will abort.

    .. note::

        Each string in ``<args>`` is a separate argument to the command, and arguments
        will never be interpreted or split on spaces. If you need more logic here,
        please execute a wrapper script to do so.

    **Example:**

        .. code-block:: ruby

            hooks {
                pre "echo" "pre-hook";
            }

.. _directive-hooks-post:

post
^^^^

.. confval:: hooks :: post <exe> [<args>...]

    **Arguments:**

        ======== =============
        ``exe``  The command to execute
        ``args`` parameters to the command
        ======== =============

    **Default:** ``None``

    **Variables:**

        Allowed in ``exe`` and ``args``.
        See :ref:`common-variables`.

    Optional. Defines a post hook. If the hook returns an
    unsuccessful exit code, autokernel will abort.

    .. note::

        Each string in ``<args>`` is a separate argument to the command, and arguments
        will never be interpreted or split on spaces. If you need more logic here,
        please execute a wrapper script to do so.

    **Example:**

        .. code-block:: ruby

            hooks {
                post "echo" "post-hook";
            }
