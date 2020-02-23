#!/usr/bin/env python3

import autokernel
import argparse
from autokernel import log, Lkddb, NodeDetector, Kconfig, print_expr_tree

import subprocess
import os

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

def detect_options():
    # TODO ensure that the running kernel can inspect all subsystems....
    # TODO what if we run on a minimal kernel?

    # Load the configuration database
    config_db = Lkddb()
    # Inspect the current system
    detector = NodeDetector()

    log.info("Matching detected nodes against database")
    # Try to find nodes in the database
    detected_options = set()
    for detector_node in detector.nodes:
        for node in detector_node.nodes:
            log.verbose("Options for {}:".format(node))
            opts = config_db.find_options(node)
            if log.verbose_output:
                for i in opts:
                    log.verbose(" - {}".format(i))
            detected_options.update(opts)

    # Load current kernel config and check against detected options
    kernel_dir = "/usr/src/linux"
    load_environment_variables(dir=kernel_dir)
    kconfig = Kconfig(dir=kernel_dir)
    kconfig.kconfig.load_config(filename='.config')

    # TODO only print summary like 25 options were alreay enabled, 24 are currently modules that can be enabled permanently and 134 are missing
    log.info("The following options were detected:")
    import kconfiglib

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

        print("[[{}m{}[m] {}".format(color, kconfiglib.TRI_TO_STR[sym.tri_value], sym.name))

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
    #parser = argparse.ArgumentParser(description="TODO")

    ## General options
    #parser.add_argument('-c', '--config', dest='config_file',
    #        help="")
    #parser.add_argument('--no-interactive', dest='no_interative', action='store_true',
    #        help="Disables all interactive prompts and automatically selects the default answer.")

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

    #args = parser.parse_args()

    # TODO umask
    detect_options()

if __name__ == '__main__':
    main()
