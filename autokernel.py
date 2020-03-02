#!/usr/bin/env python3

import autokernel
import argparse
from autokernel import log, Lkddb, NodeDetector, Kconfig, print_expr_tree, Config, ConfigParsingException
from kconfiglib import TRI_TO_STR

import subprocess
import os
import sys
from pathlib import Path

def set_env_default(var, default_value):
    """
    Sets an environment variable to the given default_value if it is currently unset.
    """
    if var not in os.environ:
        os.environ[var] = default_value

def load_environment_variables(dir):
    """
    Loads important environment variables from the given kernel source tree.
    """
    log.info("Loading kernel environment variables for '{}'".format(dir))

    # TODO dont force x86, parse uname instead! (see kernel makefiles
    set_env_default("ARCH", "x86")
    set_env_default("SRCARCH", "x86")
    set_env_default("CC", "gcc")
    set_env_default("HOSTCC", "gcc")
    set_env_default("HOSTCXX", "g++")

    os.environ["KERNELVERSION"] = subprocess.run(['make', 'kernelversion'], cwd=dir, stdout=subprocess.PIPE).stdout.decode().strip().splitlines()[0]
    os.environ["CC_VERSION_TEXT"] = subprocess.run(['gcc', '--version'], stdout=subprocess.PIPE).stdout.decode().strip().splitlines()[0]

def write_local_module_file(filename, content):
    """
    Writes the given module file content to a module file.
    """
    outdir = "local"

    # Create path if it doesn't exist
    p = Path(outdir)
    p.mkdir(parents=True, exist_ok=True)
    # TODO permissions

    # Write to file
    with (p / filename).open('w') as f:
        f.write(content)

def write_local_module_for_node(ident, node, opts):
    """
    Writes a module for the given node and the detected options.
    """
    log.info("Creating module for {} with {} options".format(ident, len(opts)))
    content = "module {} {{\n".format(ident)
    for o in opts:
        content += "\tset {};\n".format(o)
    content += "}\n"
    write_local_module_file(ident, content)

def write_local_module_selector(identifiers):
    """
    Writes a module named 'local', which depends on all previously written
    local modules. This allows easy inclusion of all local options by depending
    on this selector.
    """
    log.info("Creating local module selector")
    content = "module local {\n"
    for i in identifiers:
        content += "\tuse {};\n".format(i)
    content += "}\n"
    write_local_module_file("local", content)

def detect_options():
    # TODO ensure that the running kernel can inspect all subsystems....
    # TODO what if we run on a minimal kernel?

    # Load the configuration database
    config_db = Lkddb()
    # Inspect the current system
    detector = NodeDetector()

    # Load current kernel config
    kernel_dir = "/usr/src/linux"
    load_environment_variables(dir=kernel_dir)
    kconfig = Kconfig(dir=kernel_dir)
    kconfig.kconfig.load_config(filename='.config')

    # TODO dont create file for each module, instead create only a combined file "local".

    # Try to find detected nodes in the database
    log.info("Matching detected nodes against database")
    detected_options = set()
    local_module_identifiers = []
    for detector_node in detector.nodes:
        for node in detector_node.nodes:
            opts = config_db.find_options(node)
            if len(opts) > 0:
                ident = "{:04d}_{}".format(len(local_module_identifiers), node.get_canonical_name())
                local_module_identifiers.append(ident)

                # Write module file for this node
                write_local_module_for_node(ident, node, opts)
            detected_options.update(opts)

    # Create a combined 'local' module which selects all previously written modules
    write_local_module_selector(sorted(local_module_identifiers))

    # TODO only print summary like 25 options were alreay enabled, 24 are currently modules that can be enabled permanently and 134 are missing
    log.info("The following options were detected:")

    # Resolve symbols
    syms = []
    for i in detected_options:
        syms.append(kconfig.get_symbol(i))

    for sym in sorted(syms, key=lambda s: (-s.tri_value, s.name)):
        color = ""
        if sym.tri_value == autokernel.NO:
            color = "1;31"
        elif sym.tri_value == autokernel.MOD:
            color = "1;33"
        elif sym.tri_value == autokernel.YES:
            color = "1;32"

        print("[[{}m{}[m] {}".format(color, TRI_TO_STR[sym.tri_value], sym.name))

###############################def create_config():
###############################    # Load kconfig file
###############################    kernel_dir = "/usr/src/linux"
###############################    load_environment_variables(dir=kernel_dir)
###############################    kconfig = Kconfig(dir=kernel_dir)
###############################
###############################    # Begin with allnoconfig
###############################    kconfig.all_no_config()
###############################
###############################    # Load configuration changes from config_dir
###############################
###############################    kconfig.write_config(filename="a")
###############################
###############################    sym = kconfig.get_symbol("DVB_USB_RTL28XXU")
###############################    # TODO make autokernel --enable [CONFIG_]SOME_CONF,
###############################    # which tells you which were enabled why, and asks on optionals
###############################    kconfig.set_sym_with_deps(sym, autokernel.MOD)
###############################
###############################    kconfig.write_config(filename="b")

def check_config(args):
    if args.config:
        log.info("Checking generated config against '{}'".format(args.config))
    else:
        log.info("Checking generated config against current kernel")

def generate_config(args):
    log.info("Generating .config for kernel")
    return
    try:
        config = Config(filename='example_config.conf')
    except ConfigParsingException as e:
        log.error(str(e))
        sys.exit(1)

    # Load kconfig file
    kernel_dir = "/usr/src/linux"
    load_environment_variables(dir=kernel_dir)
    kconfig = Kconfig(dir=kernel_dir)

    # Begin with allnoconfig
    kconfig.all_no_config()

    # Track all changed symbols and values.
    changed_symbols = {}

    # Visit all module nodes and apply configuration changes
    visited = set()
    def visit(module):
        # Remember that we visited this module
        visited.add(module.id)
        for d in module.dependencies:
            if d.id not in visited:
                visit(d)

        # Process all symbol value changes
        for symbol, value in module.symbol_values:
            # If the symbol was changed previously
            if symbol in changed_symbols:
                # Assert that it is changed to the same value again
                if changed_symbols[symbol] != value:
                    log.error("Conflicting change for symbol '{}' (previously set to '{}', now '{}')".format(symbol, changed_symbols[symbol], value))
                    sys.exit(1)

                # And skip the reassignment
                continue

            # Get the kconfig symbol, and change the value
            sym = kconfig.get_symbol(symbol)
            if not sym.set_value(value):
                log.error("Invalid value '{}' for symbol '{}'".format(value, symbol))
                sys.exit(1)

            # Track the change
            changed_symbols[symbol] = value
            log.verbose("{} = {}".format(symbol, TRI_TO_STR[value] if value in TRI_TO_STR else "'{}'".format(value)))

    # Visit the root node
    visit(config.kernel.module)

    # TODO umask

def build_kernel(args):
    log.info("Building kernel")

def build_initramfs(args):
    # TODO dont build initramfs if not needed
    log.info("Building initramfs")

def install_kernel(args):
    log.info("Installing kernel")

def install_initramfs(args):
    # TODO dont install initramfs if not needed (section not given)
    log.info("Installing initramfs")

def install(args):
    # TODO print only kernel if initramfs not needed
    install_kernel(args)
    install_initramfs(args)

def build_full(args):
    log.info("Full build")
    generate_config(args)
    build_kernel(args)
    build_initramfs(args)
    install(args)

def detect(args):
    # Add fallbacks for output type and output file.
    if not args.output_type:
        args.output_type = 'module'
        if not args.output:
            args.output = '/etc/autokernel/modules.d/local'

    # Allow - as an alias for stdout
    if args.output == '-':
        args.output = None

    log.info("Detecting kernel configuration for local system")
    log.info("output to {}".format(args.output))
    log.info("type {}".format(args.output_type))
    log.info("modname {}".format(args.output_module_name))

def check_kernel_dir(value):
    """
    Checks if the given value is a valid kernel directory path.
    """

    if not os.path.isdir(value):
        raise argparse.ArgumentTypeError("'{}' is not a directory".format(value))

    if not os.path.exists(os.path.join(value, 'Kconfig')):
        raise argparse.ArgumentTypeError("'{}' is not a valid kernel directory, as it does not contain a Kconfig file".format(value))

    return value

def main():
    parser = argparse.ArgumentParser(description="TODO. If no mode is given, 'autokernel full' will be executed.")
    subparsers = parser.add_subparsers(title="commands",
            description="Use 'autokernel command --help' to view the help for any command.",
            metavar='command')

    # General options
    parser.add_argument('-k', '--kernel-dir', dest='kernel_dir', default='/usr/src/linux', type=check_kernel_dir,
            help="The kernel directory to operate on.")

    # Output options
    output_options = parser.add_mutually_exclusive_group()
    output_options.add_argument('-q', '--quiet', dest='quiet', action='store_true',
            help="Disables any additional output except for errors.")
    output_options.add_argument('-v', '--verbose', dest='verbose', action='store_true',
            help="Enables verbose output.")

    # Check
    parser_check = subparsers.add_parser('check', help="Checks the currently running kernel's TODO")
    parser_check.add_argument('config', nargs='?',
            help="Compare the generated configuration against the given kernel configuration and report the status of each option. If no config file is given, the script will try to use the current kernel's configuration from /proc/config{,.gz}.")
    parser_check.set_defaults(func=check_config)

    # Config generation options
    parser_generate_config = subparsers.add_parser('generate-config', help='TODO')
    parser_generate_config.set_defaults(func=generate_config)

    # Kernel build options
    parser_build_kernel = subparsers.add_parser('build-kernel', help='TODO')
    parser_build_kernel.set_defaults(func=build_kernel)

    # Initramfs build options
    parser_build_initramfs = subparsers.add_parser('build-initramfs', help='TODO')
    parser_build_initramfs.set_defaults(func=build_initramfs)

    # Installation options
    parser_install = subparsers.add_parser('install', help='TODO')
    parser_install.set_defaults(func=install)

    # Full build options
    parser_full = subparsers.add_parser('full', help='TODO')
    parser_full.set_defaults(func=build_full)

    # TODO
    #parser_search = subparsers.add_parser('search', help='TODO')

    # Config detection options
    parser_detect = subparsers.add_parser('detect', help='TODO')
    parser_detect.add_argument('-t', '--type', choices=['module', 'plain'], dest='output_type',
            help="Selects the output type. 'plain' will output an easily parsable list of all required configuration options and their origin. 'module' will output a ready-to-use autokernel module ")
    parser_detect.add_argument('-m', '--module-name', dest='output_module_name', default='local',
            help="The name of the generated module, which will enable all detected options (default: 'local').")
    parser_detect.add_argument('-c', '--check', nargs='?', dest='check_config',
            help="Instead of outputting the required configuration values, compare the detected options against the given kernel configuration and report the status of each option. If no config file is given, the script will try to use the current kernel's configuration from /proc/config{,.gz}.")
    parser_detect.add_argument('-o', '--output', dest='output',
            help="Writes the output to the given file. Use - for stdout. If the type is not explicitly set, this defaults to /etc/autokernel/modules.d/<module_name>.")
    parser_detect.set_defaults(func=detect)

    ## TODO en/disables the given option (and dependencies) interactively.
    ## TODO check for conflicting options in config
# TODO static paths as global variable


    args = parser.parse_args()

    # Enable verbose logging if desired
    log.verbose_output = args.verbose
    log.quiet_output = args.quiet

    # Fallback to build_full() if no mode is given
    if 'func' not in args:
        build_full(args)
    else:
        # Execute the mode's function
        args.func(args)

if __name__ == '__main__':
    main()
