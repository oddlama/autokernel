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

    os.environ["KERNELVERSION"] = subprocess.run(['make', 'kernelversion'], cwd=dir, stdout=subprocess.PIPE).stdout.decode('utf-8').strip().split('\n')[0]
    os.environ["CC_VERSION_TEXT"] = subprocess.run(['gcc', '--version'], stdout=subprocess.PIPE).stdout.decode('utf-8').strip().split('\n')[0]

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

def create_config():
    # Load kconfig file
    kernel_dir = "/usr/src/linux"
    load_environment_variables(dir=kernel_dir)
    kconfig = Kconfig(dir=kernel_dir)

    # Begin with allnoconfig
    kconfig.all_no_config()

    # Load configuration changes from config_dir

    kconfig.write_config(filename="a")

    sym = kconfig.get_symbol("DVB_USB_RTL28XXU")
    # TODO make autokernel --enable [CONFIG_]SOME_CONF,
    # which tells you which were enabled why, and asks on optionals
    kconfig.set_sym_with_deps(sym, autokernel.MOD)

    kconfig.write_config(filename="b")

def main():
    parser = argparse.ArgumentParser(description="TODO")

    ## General options
    #parser.add_argument('-c', '--config', dest='config_file',
    #        help="")
    #parser.add_argument('--no-interactive', dest='no_interative', action='store_true',
    #        help="Disables all interactive prompts and automatically selects the default answer.")
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
            help="Enables verbose output.")

    ## Operation modes
    ## TODO en/disables the given option (and dependencies) interactively.
    ## TODO check for conflicting options in config
    ## Writes the new config as /etc/autokernel.d/sets/zzz-local
    #parser.add_argument('-o', '--output', dest='',
    #        help="Output as /etc/autokernel.d/sets/{{output}}")
    #parser.add_argument('-s', '--search', dest='',
    #        help="")
    #parser.add_argument('-e', '--enable', dest='',
    #        help="")
    #parser.add_argument('-d', '--disable', dest='',
    #        help="")
    #parser.add_argument('-d', '--detect-local-options', dest='',
    #        help="Detect kernel options for this host and c")

    ## Kernel related modes
    #parser.add_argument('-m', '--merge-config', dest='',
    #        help="")
    #parser.add_argument('-b', '--build', dest='',
    #        help="")
    #parser.add_argument('-i', '--install', dest='',
    #        help="")
    #parser.add_argument('-f', '--full-build', dest='', action='store_true',
    #        help="Merges the ")

    args = parser.parse_args()
    log.verbose_output = args.verbose

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
    #detect_options()

if __name__ == '__main__':
    main()
