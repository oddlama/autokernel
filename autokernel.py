#!/usr/bin/env python3

from autokernel.kconfig import *
from autokernel.node_detector import NodeDetector
from autokernel.lkddb import Lkddb
from autokernel.config import load_config
from autokernel import log

import os
import gzip
import shutil
import sys
import tempfile
import argparse
import kconfiglib
from kconfiglib import STR_TO_TRI, TRI_TO_STR
from datetime import datetime, timezone
from pathlib import Path

def has_proc_config_gz():
    """
    Checks if /proc/config.gz exists
    """
    return os.path.isfile("/proc/config.gz")

def unpack_proc_config_gz():
    """
    Unpacks /proc/config.gz into a temporary file
    """
    tmp = tempfile.NamedTemporaryFile()
    with gzip.open("/proc/config.gz", "rb") as f:
        shutil.copyfileobj(f, tmp)
    return tmp

def kconfig_load_file_or_current_config(kconfig, config_file):
    """
    Applies the given kernel config file to kconfig, or uses /proc/config.gz if config_file is None.
    """

    if config_file:
        log.info("Applying kernel config from '{}'".format(config_file))
        kconfig.load_config(config_file)
    else:
        log.info("Applying kernel config from '/proc/config.gz'")
        with unpack_proc_config_gz() as tmp:
            kconfig.load_config(tmp.name)

def apply_autokernel_config(kconfig, config):
    """
    Applies the given autokernel configuration to a freshly loaded kconfig object,
    and returns the kconfig and a dictionary of changes
    """
    log.info("Applying autokernel configuration")

    def value_to_str(value):
        if value in STR_TO_TRI:
            return '[{}]'.format(value)
        else:
            return "'{}'".format(value)

    # Track all changed symbols and values.
    changes = {}

    # Sets a symbols value if and asserts that there are no conflicting double assignments
    def set_symbol(symbol, value):
        # If the symbol was changed previously
        if symbol in changes:
            # Assert that it is changed to the same value again
            if changes[symbol][1] != value:
                log.error("Conflicting change for symbol '{}' (previously set to {}, now {})".format(symbol, value_to_str(changes[symbol][1]), value_to_str(value)))
                sys.exit(1)

            # And skip the reassignment
            return

        # Get the kconfig symbol, and change the value
        sym = kconfig.syms[symbol]
        original_value = sym.str_value
        if not sym.set_value(value):
            log.error("Invalid value {} for symbol '{}'".format(value_to_str(value), symbol))
            sys.exit(1)

        # Track the change
        if original_value != sym.str_value:
            changes[symbol] = (original_value, sym.str_value)
            log.verbose("{} = {}".format(symbol, value_to_str(sym.str_value)))

    # Visit all module nodes and apply configuration changes
    visited = set()
    def visit(module):
        # Ensure we visit only once
        if module.id in visited:
            return
        visited.add(module.id)

        # Ensure all dependencies are processed first
        for d in module.dependencies:
            visit(d)

        # Merge all given kconf files of the module
        for filename in module.merge_kconf_files:
            # TODO don't count these as changes?
            print("TODO: merge {}".format(filename))

        # Process all symbol value changes
        for symbol, value in module.symbol_values:
            set_symbol(symbol, value)

    # Visit the root node and apply all symbol changes
    visit(config.kernel.module)
    log.info("Changed {} symbols".format(len(changes)))

    return changes

def check_config(args):
    """
    Main function for the 'check' command.
    """
    if args.compare_config:
        log.info("Checking generated config against '{}'".format(args.compare_config))
    else:
        if not has_proc_config_gz():
            log.error("This kernel does not expose /proc/config.gz. Please provide the path to a valid config file manually.")
            sys.exit(1)
        log.info("Checking generated config against currently running kernel")

    # Load configuration file
    config = load_config(args.autokernel_config)

    # Load symbols from Kconfig
    kconfig_gen = load_kconfig(args.kernel_dir)
    # Apply autokernel configuration
    changes = apply_autokernel_config(kconfig_gen, config)

    # Load symbols from Kconfig
    kconfig_cmp = load_kconfig(args.kernel_dir)
    # Load the given config file or the current kernel's config
    kconfig_load_file_or_current_config(kconfig_cmp, args.compare_config)

    for sym in kconfig_gen.syms:
        sym_gen = kconfig_gen.syms[sym]
        sym_cmp = kconfig_cmp.syms[sym]
        if sym_gen.str_value != sym_cmp.str_value:
            print("[{} -> {}] {}".format(sym_cmp.str_value, sym_gen.str_value, sym))

def generate_config(args):
    """
    Main function for the 'generate_config' command.
    """

    # Load configuration file
    config = load_config(args.autokernel_config)
    # Load symbols from Kconfig
    kconfig = load_kconfig(args.kernel_dir)
    # Apply autokernel configuration
    apply_autokernel_config(kconfig, config)

    # Write configuration to file
    header = "# Generated by autokernel on {}\n".format(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")),
    kconfig.write_config(
            filename=args.output,
            header=header,
            save_old=False)

    log.info("Configuration written to '{}'".format(args.output))

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
    # TODO only kernel if initramfs not needed
    install_kernel(args)
    install_initramfs(args)

def build_full(args):
    log.info("Full build")
    generate_config(args)
    build_kernel(args)
    build_initramfs(args)
    install(args)

class Module():
    """
    A module consists of dependencies (other modules) and option assignments.
    """
    def __init__(self, name):
        self.name = name
        self.deps = []
        self.assignments = []
        self.rev_deps = []

def check_config_against_detected_modules(kconfig, modules):
    log.info("Here are the detected options with both current and desired value.")
    log.info("The output format is: [current] OPTION_NAME = desired")
    log.info("HINT: Options are ordered by dependencies, i.e. applying")
    log.info("      them from top to buttom will work")
    log.info("Detected options:")

    visited = set()
    visited_opts = set()
    color = {
        NO: "[1;31m",
        MOD: "[1;33m",
        YES: "[1;32m",
    }

    def visit_opt(opt, v):
        from autokernel.constants import NO, MOD, YES

        # Ensure we visit only once
        if opt in visited_opts:
            return
        visited_opts.add(opt)

        sym = kconfig.syms[opt]
        if v in STR_TO_TRI:
            sym_v = sym.tri_value
            tri_v = STR_TO_TRI[v]

            if tri_v == sym_v:
                # Match
                v_color = color[YES]
            elif tri_to_bool(tri_v) == tri_to_bool(sym_v):
                # Match, but mixed y and m
                v_color = color[MOD]
            else:
                # Mismatch
                v_color = color[NO]

            # Print option value
            print("[{}{}[m] {} = {}".format(v_color, TRI_TO_STR[sym_v], sym.name, v))
        else:
            # Print option assignment
            print("{} = {}{}[m".format(sym.name, color[YES] if sym.str_value == v else color[NO], sym.str_value))

    def visit(m):
        # Ensure we visit only once
        if m in visited:
            return
        visited.add(m)

        # First visit all dependencies
        for d in m.deps:
            visit(d)
        # Then print all assignments
        for a, v in m.assignments:
            visit_opt(a, v)

    # Visit all modules
    for m in modules:
        visit(modules[m])

def detect_modules(kconfig):
    """
    Detects required options for the current system organized into modules.
    Any option with dependencies will also be represented as a module. It returns
    a dict which maps module names to the module objects. The special module returned
    additionaly is the module which selects all detected modules as dependencies.
    """
    log.info("Detecting kernel configuration for local system")
    log.info("HINT: It might be beneficial to run this while using a very generic")
    log.info("      and modular kernel, such as the default kernel on Arch Linux.")

    modules = {}
    module_for_sym = {}
    local_module_count = 0

    def next_local_module_id():
        """
        Returns the next id for a local module
        """
        nonlocal local_module_count
        i = local_module_count
        local_module_count += 1
        return i

    def add_module_for_option(sym):
        """
        Recursively adds a module for the given option,
        until all dependencies are satisfied.
        """
        mod = Module("dep_{}".format(sym.name.lower()))
        mod.assignments.append((sym.name, 'y'))
        for d, v in required_deps(sym):
            if v:
                dm = add_module_for_sym(d)
                if dm:
                    mod.deps.append(dm)
            else:
                mod.assignments.append((d.name, 'n'))
        modules[mod.name] = mod
        return mod

    def add_module_for_sym(sym):
        """
        Adds a module for the given symbol (and its dependencies).
        """
        if sym in module_for_sym:
            return module_for_sym[sym]

        # If dependencies are already satisfied, return none
        if expr_value(sym.direct_dep):
            return None

        # Otherwise, create a module for the dep
        mod = add_module_for_option(sym)
        module_for_sym[sym] = mod
        return mod

    def add_module_for_detected_node(node, opts):
        """
        Adds a module for the given detected node
        """
        mod = Module("{:04d}_{}".format(next_local_module_id(), node.get_canonical_name()))
        for o in opts:
            m = add_module_for_option(kconfig.syms[o])
            mod.deps.append(m)
        modules[mod.name] = mod
        return mod

    # Load the configuration database
    config_db = Lkddb()
    # Inspect the current system
    detector = NodeDetector()

    # Try to find detected nodes in the database
    log.info("Matching detected nodes against database")

    # A list of all modules that directly correspond to a detected node
    detected_node_modules = []
    # Find options in database for each detected node
    for detector_node in detector.nodes:
        for node in detector_node.nodes:
            opts = config_db.find_options(node)
            if len(opts) > 0:
                # If there are options for the node in the database,
                # add a module for the detected node and its options
                mod = add_module_for_detected_node(node, opts)
                # Remember the module name for the combined local module
                detected_node_modules.append(mod)

    # Fill in reverse dependencies for all modules
    for m in modules:
        for d in modules[m].deps:
            d.rev_deps.append(modules[m])

    # Create a local module that selects all detected modules
    module_select_all = Module('module_select_all')
    module_select_all.deps = detected_node_modules

    # Fill in reverse dependencies for select_all module
    for d in module_select_all.deps:
        d.rev_deps.append(module_select_all)

    return modules, module_select_all

class KernelConfigWriter:
    """
    Writes modules to the given file in kernel config format.
    """
    def __init__(self, file):
        self.file = file

    def write_module(self, module):
        if len(module.assignments) == 0:
            return

        content = ""
        for d in module.rev_deps:
            content += "# required by {}\n".format(d.name)
        content += "# module {}\n".format(module.name)
        for a, v in module.assignments:
            if v in "nmy":
                content += "CONFIG_{}={}\n".format(a, v)
            else:
                content += "CONFIG_{}=\"{}\"\n".format(a, v)
        self.file.write(content)

class ModuleConfigWriter:
    """
    Writes modules to the given file in the module config format.
    """
    def __init__(self, file):
        self.file = file

    def write_module(self, module):
        content = ""
        for d in module.rev_deps:
            content += "# required by {}\n".format(d.name)
        content += "module {} {{\n".format(module.name)
        for d in module.deps:
            content += "\tuse {};\n".format(d.name)
        for a, v in module.assignments:
            content += "\tset {} {};\n".format(a, v)
        content += "}\n\n"
        self.file.write(content)

def write_detected_modules(modules, module_select_all, f, output_type, output_module_name):
    """
    Writes the detected modules to a file / stdout, in the requested output format.
    """
    if output_type == 'kconf':
        writer = KernelConfigWriter(f)
    elif output_type == 'module':
        writer = ModuleConfigWriter(f)

    visited = set()
    def visit(m):
        # Ensure we visit only once
        if m in visited:
            return
        visited.add(m)
        writer.write_module(m)

    # Write all modules in topological order
    for m in modules:
        visit(modules[m])

    # Lastly, write "select_all" module
    module_select_all.name = output_module_name
    writer.write_module(module_select_all)

def detect(args):
    """
    Main function for the 'detect' command.
    """
    # Check if we should write a config or report differences
    check_only = args.check_config is not 0

    # Assert that --check is not used together with --type
    if check_only and args.output_type:
        log.error("--check and --type are mutually exclusive")
        sys.exit(1)

    # Assert that --check is not used together with --output
    if check_only and args.output:
        log.error("--check and --output are mutually exclusive")
        sys.exit(1)

    # Add fallback for output type.
    if not args.output_type:
        args.output_type = 'module'

    # Allow - as an alias for stdout
    if args.output == '-':
        args.output = None

    # Determine the config file to check against, if applicable.
    if check_only:
        if args.check_config:
            log.info("Checking generated config against '{}'".format(args.check_config))
        else:
            if not has_proc_config_gz():
                log.error("This kernel does not expose /proc/config.gz. Please provide the path to a valid config file manually.")
                sys.exit(1)
            log.info("Checking generated config against currently running kernel")

    # Load symbols from Kconfig
    kconfig = load_kconfig(args.kernel_dir)
    # Detect system nodes and create modules
    modules, module_select_all = detect_modules(kconfig)

    if check_only:
        # Load the given config file or the current kernel's config
        kconfig_load_file_or_current_config(kconfig, args.check_config)
        # Check all detected symbols' values and report them
        check_config_against_detected_modules(kconfig, modules)
    else:
        # Write all modules in the given format to the given output file / stdout
        if args.output:
            try:
                with open(args.output, 'w') as f:
                    write_detected_modules(modules, module_select_all, f, args.output_type, args.output_module_name)
                    log.info("Configuration written to '{}'".format(args.output))
            except IOError as e:
                log.error(str(e))
                sys.exit(1)
        else:
            write_detected_modules(modules, module_select_all, sys.stdout, args.output_type, args.output_module_name)

def check_file_exists(value):
    """
    Checks if the given exists
    """
    if not os.path.isfile(value):
        raise argparse.ArgumentTypeError("'{}' is not a file".format(value))
    return value

def check_kernel_dir(value):
    """
    Checks if the given value is a valid kernel directory path.
    """
    if not os.path.isdir(value):
        raise argparse.ArgumentTypeError("'{}' is not a directory".format(value))

    if not os.path.exists(os.path.join(value, 'Kconfig')):
        raise argparse.ArgumentTypeError("'{}' is not a valid kernel directory, as it does not contain a Kconfig file".format(value))

    return value

class ArgumentParserError(Exception):
    pass

class ThrowingArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)

def main():
    """
    Parses options and dispatches control to the correct subcommand function
    """
    parser = ThrowingArgumentParser(description="TODO. If no mode is given, 'autokernel full' will be executed.")
    subparsers = parser.add_subparsers(title="commands",
            description="Use 'autokernel command --help' to view the help for any command.",
            metavar='command')

    # General options
    parser.add_argument('-k', '--kernel-dir', dest='kernel_dir', default='/usr/src/linux', type=check_kernel_dir,
            help="The kernel directory to operate on. The default is /usr/src/linux.")
    parser.add_argument('-C', '--config', dest='autokernel_config', default='/etc/autokernel/autokernel.conf', type=check_file_exists,
            help="The autokernel configuration file to use. The default is '/etc/autokernel/autokernel.conf'.")

    # Output options
    output_options = parser.add_mutually_exclusive_group()
    output_options.add_argument('-q', '--quiet', dest='quiet', action='store_true',
            help="Disables any additional output except for errors.")
    output_options.add_argument('-v', '--verbose', dest='verbose', action='store_true',
            help="Enables verbose output.")

    # Check
    parser_check = subparsers.add_parser('check', help="Reports differences between the config that will be generated by autokernel, and the given config file. If no config file is given, the script will try to load the current kernel's configuration from '/proc/config.gz'.")
    parser_check.add_argument('-c', '--compare-config', nargs='?', dest='compare_config', type=check_file_exists,
            help="The .config file to compare the generated configuration against.")
    parser_check.set_defaults(func=check_config)

    # Config generation options
    parser_generate_config = subparsers.add_parser('generate-config', help='Generates the kernel configuration file from the autokernel configuration.')
    parser_generate_config.add_argument('-o', '--output', dest='output', default='/usr/src/linux/.config',
            help="The output filename. An existing configuration file will be overwritten. The default is '/usr/src/linux/.config'.")
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
    parser_detect.add_argument('-t', '--type', choices=['module', 'kconf'], dest='output_type',
            help="Selects the output type. 'kconf' will output options in the kernel configuration format. 'module' will output a list of autokernel modules to reflect the necessary configuration.")
    parser_detect.add_argument('-m', '--module-name', dest='output_module_name', default='local',
            help="The name of the generated module, which will enable all detected options (default: 'local').")
    parser_detect.add_argument('-c', '--check', nargs='?', default=0, dest='check_config', type=check_file_exists,
            help="Instead of outputting the required configuration values, compare the detected options against the given kernel configuration and report the status of each option. If no config file is given, the script will try to load the current kernel's configuration from '/proc/config.gz'.")
    parser_detect.add_argument('-o', '--output', dest='output',
            help="Writes the output to the given file. Use - for stdout (default).")
    parser_detect.set_defaults(func=detect)

    # TODO static paths as global variable

    try:
        args = parser.parse_args()
    except ArgumentParserError as e:
        log.error(str(e))
        sys.exit(1)

    # Enable verbose logging if desired
    log.verbose_output = args.verbose
    log.quiet_output = args.quiet

    # Fallback to build_full() if no mode is given
    if 'func' not in args:
        build_full(args)
    else:
        # Execute the mode's function
        args.func(args)

    # TODO umask (probably better as external advice, use umask then execute this.)

if __name__ == '__main__':
    main()
