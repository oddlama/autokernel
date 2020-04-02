import autokernel.kconfig
import autokernel.config
import autokernel.lkddb
import autokernel.node_detector
import autokernel.symbol_tracking
from autokernel import log
from autokernel.symbol_tracking import set_value_detect_conflicts

import argparse
import gzip
import os
import shutil
import subprocess
import sys
import tempfile
import kconfiglib
from datetime import datetime, timezone


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
        kconfig.load_config(os.path.realpath(config_file))
    else:
        log.info("Applying kernel config from '/proc/config.gz'")
        with unpack_proc_config_gz() as tmp:
            kconfig.load_config(os.path.realpath(tmp.name))

def generated_by_autokernel_header():
    return "# Generated by autokernel on {}\n".format(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))

def vim_config_modeline_header():
    return "# vim: set ft=ruby ts=4 sw=4 sts=-1 noet:\n"

def apply_autokernel_config(kernel_dir, kconfig, config):
    """
    Applies the given autokernel configuration to a freshly loaded kconfig object,
    and returns gathered extra information such as the resulting kernel cmdline
    """
    log.info("Applying autokernel configuration")

    # Build cmdline on demand
    kernel_cmdline = []
    # Reset symbol_changes
    autokernel.symbol_tracking.symbol_changes.clear()

    # Asserts that the symbol has the given value
    def get_sym(stmt):
        # Get the kconfig symbol, and change the value
        try:
            return kconfig.syms[stmt.sym_name]
        except KeyError:
            autokernel.config.die_print_error_at(stmt.at, "symbol '{}' does not exist".format(stmt.sym_name))

    # Asserts that the symbol has the given value
    def assert_symbol(stmt):
        if not stmt.assert_condition.evaluate(kconfig):
            if stmt.message:
                autokernel.config.die_print_error_at(stmt.at, "assertion failed: {}".format(stmt.message))
            else:
                autokernel.config.die_print_error_at(stmt.at, "assertion failed")

    # Sets a symbols value if and asserts that there are no conflicting double assignments
    def set_symbol(stmt):
        # Get the kconfig symbol, and change the value
        sym = get_sym(stmt)

        if not autokernel.kconfig.symbol_can_be_user_assigned(sym):
            autokernel.config.print_warn_at(stmt.at, "symbol {} can't be user-assigned".format(sym.name))

        # Skip assignment if value is already pinned and the statement is in try mode.
        if stmt.has_try and sym in autokernel.symbol_tracking.symbol_changes:
            log.verbose("skipping {} {}".format(autokernel.kconfig.value_to_str(stmt.value), sym.name))
            return

        if not set_value_detect_conflicts(sym, stmt.value, stmt.at):
            autokernel.config.die_print_error_at(stmt.at, "invalid value {} for symbol {}".format(autokernel.kconfig.value_to_str(stmt.value), sym.name))

        if sym.str_value != stmt.value:
            if not stmt.has_try:
                # Only warn if it wasn't a try
                autokernel.config.print_warn_at(stmt.at, "symbol assignment failed: {} from {} → {}".format(
                    sym.name,
                    autokernel.kconfig.value_to_str(sym.str_value),
                    autokernel.kconfig.value_to_str(stmt.value)))
            else:
                log.verbose("failed try set {} {} (symbol is currently not assignable to the chosen value)".format(autokernel.kconfig.value_to_str(stmt.value), sym.name))

    # Visit all module nodes and apply configuration changes
    visited = set()
    def visit(module):
        # Ensure we visit only once
        if module.name in visited:
            return
        visited.add(module.name)

        def stmt_use(stmt):
            visit(stmt.module)

        def stmt_merge(stmt):
            filename = stmt.filename.replace('$KERNEL_DIR', kernel_dir)
            log.verbose("Merging external kconf '{}'".format(filename))
            kconfig.load_config(os.path.realpath(filename), replace=False)

        def stmt_assert(stmt):
            assert_symbol(stmt)

        def stmt_set(stmt):
            set_symbol(stmt)

        def stmt_add_cmdline(stmt):
            kernel_cmdline.append(stmt.param)

        dispatch_stmt = {
            autokernel.config.ConfigModule.StmtUse: stmt_use,
            autokernel.config.ConfigModule.StmtMerge: stmt_merge,
            autokernel.config.ConfigModule.StmtAssert: stmt_assert,
            autokernel.config.ConfigModule.StmtSet: stmt_set,
            autokernel.config.ConfigModule.StmtAddCmdline: stmt_add_cmdline,
        }

        def conditions_met(stmt):
            for condition in stmt.conditions:
                if not condition.evaluate(kconfig):
                    return False
            return True

        for stmt in module.all_statements_in_order:
            # Ensure all attached conditions are met for the statement.
            if conditions_met(stmt):
                dispatch_stmt[stmt.__class__](stmt)

    # Visit the root node and apply all symbol changes
    visit(config.kernel.module)
    log.info("  Changed {} symbols".format(len(autokernel.symbol_tracking.symbol_changes)))

    # Lastly, invalidate all non-assigned symbols to process new default value conditions
    for sym in kconfig.unique_defined_syms:
        if sym.user_value is None:
            sym._invalidate()

    return kernel_cmdline

def main_check_config(args):
    """
    Main function for the 'check' command.
    """
    if args.compare_config:
        if not args.compare_kernel_dir:
            args.compare_kernel_dir = args.kernel_dir

        kname_cmp = "'{}'".format(args.compare_config)
    else:
        if not has_proc_config_gz():
            log.die("This kernel does not expose /proc/config.gz. Please provide the path to a valid config file manually.")

        if not args.compare_kernel_dir:
            # Use /usr/src/linux-{kernel_version} as the directory.
            running_kver = subprocess.run(['uname', '-r'], check=True, stdout=subprocess.PIPE).stdout.decode().strip().splitlines()[0]
            args.compare_kernel_dir = os.path.join('/usr/src/linux-{}'.format(running_kver))
            try:
                check_kernel_dir(args.compare_kernel_dir)
            except argparse.ArgumentTypeError:
                log.die("Could not find sources for running kernel (version {}) in '{}', use --check_kernel_dir to specify it manually.".format(running_kver, args.compare_kernel_dir))

        kname_cmp = 'running kernel'

    log.info("Comparing {} against generated config".format(kname_cmp))

    # Load configuration file
    config = autokernel.config.load_config(args.autokernel_config)

    # Load symbols from Kconfig
    kconfig_gen = autokernel.kconfig.load_kconfig(args.kernel_dir)
    # Apply autokernel configuration
    apply_autokernel_config(args.kernel_dir, kconfig_gen, config)

    # Load symbols from Kconfig
    kconfig_cmp = autokernel.kconfig.load_kconfig(args.compare_kernel_dir)
    # Load the given config file or the current kernel's config
    kconfig_load_file_or_current_config(kconfig_cmp, args.compare_config)

    indicator_del = log.color("[31m-[m", "-")
    indicator_add = log.color("[32m+[m", "+")
    indicator_mod = log.color("[33m~[m", "~")

    log.info("Comparing existing config (left) against generated config (right)")
    log.info("  ({}) symbol was removed".format(indicator_del))
    log.info("  ({}) symbol is new".format(indicator_add))
    log.info("  ({}) symbol value changed".format(indicator_mod))

    gen_syms = [s.name for s in kconfig_gen.unique_defined_syms]
    cmp_syms = [s.name for s in kconfig_cmp.unique_defined_syms]

    def intersection(a, b):
        return [i for i in a if i in b]
    def comprehension(a, b):
        return [i for i in a if i not in b]

    common_syms = intersection(gen_syms, set(cmp_syms))
    common_syms_set = set(common_syms)
    only_gen_syms = comprehension(gen_syms, common_syms_set)
    only_cmp_syms = comprehension(cmp_syms, common_syms_set)


    supress_new, supress_del, supress_chg = (args.suppress_columns or (False, False, False))

    if not supress_new:
        for sym in only_gen_syms:
            sym_gen = kconfig_gen.syms[sym]
            print(indicator_add + " {} {}".format(
                autokernel.kconfig.value_to_str(sym_gen.str_value),
                sym))

    if not supress_del:
        for sym in only_cmp_syms:
            sym_cmp = kconfig_cmp.syms[sym]
            print(indicator_del + " {} {}".format(
                autokernel.kconfig.value_to_str(sym_cmp.str_value),
                sym))

    if not supress_chg:
        for sym in common_syms:
            sym_gen = kconfig_gen.syms[sym]
            sym_cmp = kconfig_cmp.syms[sym]
            if sym_gen.str_value != sym_cmp.str_value:
                print(indicator_mod + " {} → {} {}".format(
                    autokernel.kconfig.value_to_str(sym_cmp.str_value),
                    autokernel.kconfig.value_to_str(sym_gen.str_value),
                    sym))

def main_generate_config(args, config=None):
    """
    Main function for the 'generate_config' command.
    """
    log.info("Generating kernel configuration")
    if not config:
        # Load configuration file
        config = autokernel.config.load_config(args.autokernel_config)

    # Fallback for config output
    if not hasattr(args, 'output') or not args.output:
        args.output = os.path.join(args.kernel_dir, '.config')

    # Load symbols from Kconfig
    kconfig = autokernel.kconfig.load_kconfig(args.kernel_dir)
    # Apply autokernel configuration
    generate_config_info = apply_autokernel_config(args.kernel_dir, kconfig, config)

    # Write configuration to file
    kconfig.write_config(
            filename=args.output,
            header=generated_by_autokernel_header(),
            save_old=False)

    log.info("Configuration written to '{}'".format(args.output))

def build_kernel(args, config, pass_id):
    if pass_id == 'initial':
        log.info("Building kernel")
    elif pass_id == 'pack':
        log.info("Rebuilding kernel to pack external resources")
    else:
        raise ValueError("pass_id has an invalid value '{}'".format(pass_id))

    # TODO cleaning capabilities?
    try:
        subprocess.run(['make'], cwd=args.kernel_dir, check=True)
    except subprocess.CalledProcessError as e:
        log.die("make failed in {} with code {}".format(args.kernel_dir, e.returncode))

def build_initramfs(args, config):
    log.info("Building initramfs")

    print("subprocess.run(['genkernel'], cwd={}), config={}".format(args.kernel_dir, config))

def main_build(args, config=None):
    """
    Main function for the 'build' command.
    """
    if not config:
        # Load configuration file
        config = autokernel.config.load_config(args.autokernel_config)

    # TODO provide own kconfig .... used later bc modified
    main_generate_config(args, config)

    # Build the kernel
    build_kernel(args, config, pass_id='initial')

    # Build the initramfs, if enabled
    if config.build.enable_initramfs:
        build_initramfs(args, config)

        # Pack the initramfs into the kernel if desired
        if config.build.pack['initramfs']:
            build_kernel(args, config, pass_id='pack')

def install_kernel(args, config):
    log.info("Installing kernel")

    # TODO always use a clear environment!!!
    print(args.kernel_dir)
    print(str(config.install.target_dir))
    print(str(config.install.target).replace('$KERNEL_VERSION', autokernel.kconfig.get_kernel_version(args.kernel_dir)))

def install_initramfs(args, config):
    log.info("Installing initramfs")
    print(args.kernel_dir)
    print(config.install.target_dir)

def main_install(args, config=None):
    """
    Main function for the 'install' command.
    """
    if not config:
        # Load configuration file
        config = autokernel.config.load_config(args.autokernel_config)

    # Mount
    for i in config.install.mount:
        if not os.access(i, os.R_OK):
            log.die("Permission denied on accessing '{}'. Aborting.".format(i))

        if not os.path.ismount(i):
            try:
                subprocess.run(['mount', '--', i], check=True)
            except subprocess.CalledProcessError as e:
                log.die("Could not mount '{}', mount returned code {}. Aborting.".format(i, e.returncode))

    # Check mounts
    for i in config.install.mount + config.install.assert_mounted:
        if not os.access(i, os.R_OK):
            log.die("Permission denied on accessing '{}'. Aborting.".format(i))

        if not os.path.ismount(i):
            log.die("'{}' is not mounted. Aborting.".format(i))

    install_kernel(args, config)

    # Install the initramfs, if enabled and not packed
    if config.build.enable_initramfs and not config.build.pack['initramfs']:
        install_initramfs(args, config)

def main_build_all(args):
    """
    Main function for the 'all' command.
    """
    log.info("Started full build")
    # Load configuration file
    config = autokernel.config.load_config(args.autokernel_config)

    main_build(args, config)
    main_install(args, config)

class Module():
    """
    A module consists of dependencies (other modules) and option assignments.
    """
    def __init__(self, name):
        self.name = name
        self.deps = []
        self.assignments = []
        self.assertions = []
        self.rev_deps = []

def check_config_against_detected_modules(kconfig, modules):
    log.info("Here are the detected options with both current and desired value.")
    log.info("The output format is: [current] OPTION_NAME = desired")
    log.info("HINT: Options are ordered by dependencies, i.e. applying")
    log.info("      them from top to buttom will work")
    log.info("Indicators: (=) same, (~) changed")
    log.info("Detected options:")

    visited = set()
    visited_opts = set()

    indicator_same = log.color('[32m=[m', '=')
    indicator_changed = log.color('[33m~[m', '~')

    def visit_opt(opt, new_value):
        # Ensure we visit only once
        if opt in visited_opts:
            return
        visited_opts.add(opt)

        sym = kconfig.syms[opt]
        changed = sym.str_value != new_value

        if changed:
            print(indicator_changed + " {} → {} {}".format(autokernel.kconfig.value_to_str(sym.str_value), autokernel.kconfig.value_to_str(new_value), sym.name))
        else:
            print(indicator_same + "       {} {}".format(autokernel.kconfig.value_to_str(sym.str_value), sym.name))

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

class KernelConfigWriter:
    """
    Writes modules to the given file in kernel config format.
    """
    def __init__(self, file):
        self.file = file
        self.file.write(generated_by_autokernel_header())
        self.file.write(vim_config_modeline_header())

    def write_module(self, module):
        if len(module.assignments) == len(module.assertions) == 0:
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
        for o, v in module.assertions:
            content += "# REQUIRES {} {}\n".format(o, v)
        self.file.write(content)

class ModuleConfigWriter:
    """
    Writes modules to the given file in the module config format.
    """
    def __init__(self, file):
        self.file = file
        self.file.write(generated_by_autokernel_header())
        self.file.write(vim_config_modeline_header())

    def write_module(self, module):
        content = ""
        for d in module.rev_deps:
            content += "# required by {}\n".format(d.name)
        content += "module {} {{\n".format(module.name)
        for d in module.deps:
            content += "\tuse {};\n".format(d.name)
        for a, v in module.assignments:
            content += "\tset {} {};\n".format(a, v)
        for o, v in module.assertions:
            content += "\tassert {} == {};\n".format(o, v)
        content += "}\n\n"
        self.file.write(content)

class ModuleCreator:
    def __init__(self, module_prefix=''):
        self.modules = {}
        self.module_for_sym = {}
        self.module_select_all = Module('module_select_all')
        self.module_prefix = module_prefix

    def _create_reverse_deps(self):
        # Clear rev_deps
        for m in self.modules:
            self.modules[m].rev_deps = []
        self.module_select_all.rev_deps = []

        # Fill in reverse dependencies for all modules
        for m in self.modules:
            for d in self.modules[m].deps:
                d.rev_deps.append(self.modules[m])

        # Fill in reverse dependencies for select_all module
        for d in self.module_select_all.deps:
            d.rev_deps.append(self.module_select_all)

    def _add_module_for_option(self, sym):
        """
        Recursively adds a module for the given option,
        until all dependencies are satisfied.
        """
        mod = Module(self.module_prefix + "config_{}".format(sym.name.lower()))

        # Find dependencies if needed
        needs_deps = not kconfiglib.expr_value(sym.direct_dep)
        if needs_deps:
            req_deps = autokernel.kconfig.required_deps(sym)
            if req_deps is False:
                # Dependencies can never be satisfied. The module should be skipped.
                log.warn("Cannot satisfy dependencies for {}".format(sym.name))
                return False

        if not autokernel.kconfig.symbol_can_be_user_assigned(sym):
            # If we cannot assign the symbol, we add an assertion instead.
            mod.assertions.append((sym.name, 'y'))
        else:
            mod.assignments.append((sym.name, 'y'))

            if needs_deps:
                for d, v in req_deps:
                    if v:
                        depm = self.add_module_for_sym(d)
                        if depm is False:
                            return False
                        mod.deps.append(depm)
                    else:
                        if autokernel.kconfig.symbol_can_be_user_assigned(sym):
                            mod.assignments.append((d.name, 'n'))
                        else:
                            mod.assertions.append((d.name, 'n'))

        self.modules[mod.name] = mod
        return mod

    def add_module_for_sym(self, sym):
        """
        Adds a module for the given symbol (and its dependencies).
        """
        if sym in self.module_for_sym:
            return self.module_for_sym[sym]

        # Create a module for the symbol, if it doesn't exist already
        mod = self._add_module_for_option(sym)
        if mod is False:
            return False
        self.module_for_sym[sym] = mod
        return mod

    def select_module(self, mod):
        self.module_select_all.deps.append(mod)

    def add_external_module(self, mod):
        self.modules[mod.name] = mod

    def _write_detected_modules(self, f, output_type, output_module_name):
        """
        Writes the collected modules to a file / stdout, in the requested output format.
        """
        if output_type == 'kconf':
            writer = KernelConfigWriter(f)
        elif output_type == 'module':
            writer = ModuleConfigWriter(f)
        else:
            log.die("Invalid output_type '{}'".format(output_type))

        # Set select_all name
        self.module_select_all.name = output_module_name

        # Fill in reverse dependencies for all modules
        self._create_reverse_deps()

        visited = set()
        def visit(m):
            # Ensure we visit only once
            if m in visited:
                return
            visited.add(m)
            writer.write_module(m)

        # Write all modules in topological order
        for m in self.modules:
            visit(self.modules[m])

        # Lastly, write "select_all" module, if it has been used
        if len(self.module_select_all.deps) > 0:
            writer.write_module(self.module_select_all)

    def write_detected_modules(self, args):
        # Write all modules in the given format to the given output file / stdout
        if args.output:
            try:
                with open(args.output, 'w') as f:
                    self._write_detected_modules(f, args.output_type, args.output_module_name)
                    log.info("Module configuration written to '{}'".format(args.output))
            except IOError as e:
                log.die(str(e))
        else:
            self._write_detected_modules(sys.stdout, args.output_type, args.output_module_name)

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

    local_module_count = 0
    def next_local_module_id():
        """
        Returns the next id for a local module
        """
        nonlocal local_module_count
        i = local_module_count
        local_module_count += 1
        return i

    module_creator = ModuleCreator(module_prefix='detected_')
    def add_module_for_detected_node(node, opts):
        """
        Adds a module for the given detected node
        """
        mod = Module("{:04d}_{}".format(next_local_module_id(), node.get_canonical_name()))
        for o in opts:
            try:
                sym = kconfig.syms[o]
            except KeyError:
                log.warn("Skipping unknown symbol {}".format(o))
                continue

            m = module_creator.add_module_for_sym(sym)
            if m is False:
                log.warn("Skipping module {} (unsatisfiable dependencies)".format(mod.name))
                return None
            mod.deps.append(m)
        module_creator.add_external_module(mod)
        return mod

    # Load the configuration database
    config_db = autokernel.lkddb.Lkddb()
    # Inspect the current system
    detector = autokernel.node_detector.NodeDetector()

    # Try to find detected nodes in the database
    log.info("Matching detected nodes against database")

    # First sort all nodes for more consistent output between runs
    all_nodes = []
    # Find options in database for each detected node
    for detector_node in detector.nodes:
        all_nodes.extend(detector_node.nodes)
    all_nodes.sort(key=lambda x: x.get_canonical_name())

    for node in all_nodes:
        opts = config_db.find_options(node)
        if len(opts) > 0:
            # If there are options for the node in the database,
            # add a module for the detected node and its options
            mod = add_module_for_detected_node(node, opts)
            if mod:
                # Select the module in the global selector module
                module_creator.select_module(mod)

    return module_creator

def main_detect(args):
    """
    Main function for the 'main_detect' command.
    """
    # Check if we should write a config or report differences
    check_only = args.check_config is not 0

    # Assert that --check is not used together with --type
    if check_only and args.output_type:
        log.die("--check and --type are mutually exclusive")

    # Assert that --check is not used together with --output
    if check_only and args.output:
        log.die("--check and --output are mutually exclusive")

    # Determine the config file to check against, if applicable.
    if check_only:
        if args.check_config:
            log.info("Checking generated config against '{}'".format(args.check_config))
        else:
            if not has_proc_config_gz():
                log.die("This kernel does not expose /proc/config.gz. Please provide the path to a valid config file manually.")
            log.info("Checking generated config against currently running kernel")

    # Load symbols from Kconfig
    kconfig = autokernel.kconfig.load_kconfig(args.kernel_dir)
    # Detect system nodes and create modules
    module_creator = detect_modules(kconfig)

    if check_only:
        # Load the given config file or the current kernel's config
        kconfig_load_file_or_current_config(kconfig, args.check_config)
        # Check all detected symbols' values and report them
        check_config_against_detected_modules(kconfig, module_creator.modules)
    else:
        # Add fallback for output type.
        if not args.output_type:
            args.output_type = 'module'

        # Allow - as an alias for stdout
        if args.output == '-':
            args.output = None

        # Write all modules in the given format to the given output file / stdout
        module_creator.write_detected_modules(args)

def main_info(args):
    """
    Main function for the 'info' command.
    """
    # Load symbols from Kconfig
    kconfig = autokernel.kconfig.load_kconfig(args.kernel_dir)

    for config_symbol in args.config_symbols:
        # Get symbol
        if config_symbol.startswith('CONFIG_'):
            sym_name = config_symbol[len('CONFIG_'):]
        else:
            sym_name = config_symbol

        # Print symbol
        try:
            sym = kconfig.syms[sym_name]
        except KeyError:
            log.die("Symbol '{}' does not exist".format(sym_name))

        print(sym)
        print(sym.env_var)

def main_deps(args):
    """
    Main function for the 'deps' command.
    """
    # Load symbols from Kconfig
    kconfig = autokernel.kconfig.load_kconfig(args.kernel_dir)

    # Apply autokernel configuration only if we want our dependencies based on the current configuration
    if not args.dep_global:
        # Load configuration file
        config = autokernel.config.load_config(args.autokernel_config)
        # Apply kernel config
        apply_autokernel_config(args.kernel_dir, kconfig, config)

    # Create a module for the detected option
    module_creator = ModuleCreator()

    for config_symbol in args.config_symbols:
        # Get symbol
        if config_symbol.startswith('CONFIG_'):
            sym_name = config_symbol[len('CONFIG_'):]
        else:
            sym_name = config_symbol

        try:
            sym = kconfig.syms[sym_name]
        except KeyError:
            log.die("Symbol '{}' does not exist".format(sym_name))

        mod = module_creator.add_module_for_sym(sym)
        if mod is False:
            log.warn("Skipping {} (unsatisfiable dependencies)".format(sym.name))
            continue
        module_creator.select_module(mod)

    # Add fallback for output type.
    if not args.output_type:
        args.output_type = 'module'

    # Allow - as an alias for stdout
    if args.output == '-':
        args.output = None

    # Write the module
    module_creator.write_detected_modules(args)

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

def suppress_columns_list(value):
    """
    Checks if the given value is a csv of columns to suppress.
    """
    valid_values_new = ['new', 'n']
    valid_values_del = ['del', 'd']
    valid_values_chg = ['changed', 'chg', 'c']
    valid_values = valid_values_new + valid_values_del + valid_values_chg

    supress_new = False
    supress_del = False
    supress_chg = False
    for i in value.split(','):
        if i in valid_values_new:
            supress_new = True
        elif i in valid_values_del:
            supress_del = True
        elif i in valid_values_chg:
            supress_chg = True
        else:
            raise argparse.ArgumentTypeError("'{}' is not a valid suppression type. Must be one of [{}]".format(i, ', '.join(["'{}'".format(v) for v in valid_values])))

    return (supress_new, supress_del, supress_chg)

class ArgumentParserError(Exception):
    pass

class ThrowingArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentParserError(message)

def main():
    """
    Parses options and dispatches control to the correct subcommand function
    """
    # TODO descr
    parser = ThrowingArgumentParser(description="TODO. If no mode is given, 'autokernel all' will be executed.")
    subparsers = parser.add_subparsers(title="commands",
            description="Use 'autokernel command --help' to view the help for any command.",
            metavar='command')

    # General options
    parser.add_argument('-K', '--kernel-dir', dest='kernel_dir', default='/usr/src/linux', type=check_kernel_dir,
            help="The kernel directory to operate on. The default is /usr/src/linux.")
    parser.add_argument('-C', '--config', dest='autokernel_config', default='/etc/autokernel/autokernel.conf', type=check_file_exists,
            help="The autokernel configuration file to use. The default is '/etc/autokernel/autokernel.conf'.")
    parser.add_argument('--no-color', dest='use_color', action='store_false',
            help="Disables coloring in normal output.")

    # Output options
    output_options = parser.add_mutually_exclusive_group()
    output_options.add_argument('-q', '--quiet', dest='quiet', action='store_true',
            help="Disables any additional output except for errors.")
    output_options.add_argument('-v', '--verbose', dest='verbose', action='store_true',
            help="Enables verbose output.")

    # Check
    parser_check = subparsers.add_parser('check', help="Reports differences between the config that will be generated by autokernel, and the given config file. If no config file is given, the script will try to load the current kernel's configuration from '/proc/config.gz'.")
    parser_check.add_argument('-c', '--compare-config', dest='compare_config', type=check_file_exists,
            help="The .config file to compare the generated configuration against.")
    parser_check.add_argument('-k', '--compare-kernel-dir', dest='compare_kernel_dir', type=check_kernel_dir,
            help="The kernel directory for the given comparison config.")
    parser_check.add_argument('--suppress', dest='suppress_columns', type=suppress_columns_list,
            help="Comma separated list of columns to suppress. 'new' or 'n' supresses new symbols, 'del' or 'd' suppresses removed symbols, 'changed', 'chg' or 'c' supresses changed symbols.")
    parser_check.set_defaults(func=main_check_config)

    # Config generation options
    parser_generate_config = subparsers.add_parser('generate-config', help='Generates the kernel configuration file from the autokernel configuration.')
    parser_generate_config.add_argument('-o', '--output', dest='output',
            help="The output filename. An existing configuration file will be overwritten. The default is '{KERNEL_DIR}/.config'.")
    parser_generate_config.set_defaults(func=main_generate_config)

    # Build options
    parser_build = subparsers.add_parser('build', help='Generates the configuration, and then builds the kernel (and initramfs if required) in the kernel tree.')
    parser_build.set_defaults(func=main_build)

    # Installation options
    parser_install = subparsers.add_parser('install', help='Installs the finished kernel and requisites into the system.')
    parser_install.set_defaults(func=main_install)

    # Full build options
    parser_all = subparsers.add_parser('all', help='First builds and then installs the kernel.')
    parser_all.set_defaults(func=main_build_all)

    # Show symbol infos
    parser_info = subparsers.add_parser('info', help='Displays information for the given symbols')
    parser_info.add_argument('config_symbols', nargs='+',
            help="A list of configuration symbols to show infos for")
    parser_info.set_defaults(func=main_info)

    # Single config module generation options
    parser_deps = subparsers.add_parser('deps', help='Generates required modules to enable the given symbol')
    parser_deps.add_argument('-g', '--global', action='store_true', dest='dep_global',
            help="Report changes based on an allnoconfig instead of basing the output on changes from the current autokernel configuration")
    parser_deps.add_argument('-t', '--type', choices=['module', 'kconf'], dest='output_type',
            help="Selects the output type. 'kconf' will output options in the kernel configuration format. 'module' will output a list of autokernel modules to reflect the necessary configuration.")
    parser_deps.add_argument('-m', '--module-name', dest='output_module_name', default='rename_me',
            help="The name of the generated module, which will enable all given options (default: 'rename_me').")
    parser_deps.add_argument('-o', '--output', dest='output',
            help="Writes the output to the given file. Use - for stdout (default).")
    parser_deps.add_argument('config_symbols', nargs='+',
            help="The configuration symbols to generate modules for (including dependencies)")
    parser_deps.set_defaults(func=main_deps)

    # Config detection options
    parser_detect = subparsers.add_parser('detect', help='Detects configuration options based on information gathered from the running system')
    parser_detect.add_argument('-c', '--check', nargs='?', default=0, dest='check_config', type=check_file_exists,
            help="Instead of outputting the required configuration values, compare the detected options against the given kernel configuration and report the status of each option. If no config file is given, the script will try to load the current kernel's configuration from '/proc/config.gz'.")
    parser_detect.add_argument('-t', '--type', choices=['module', 'kconf'], dest='output_type',
            help="Selects the output type. 'kconf' will output options in the kernel configuration format. 'module' will output a list of autokernel modules to reflect the necessary configuration.")
    parser_detect.add_argument('-m', '--module-name', dest='output_module_name', default='local',
            help="The name of the generated module, which will enable all detected options (default: 'local').")
    parser_detect.add_argument('-o', '--output', dest='output',
            help="Writes the output to the given file. Use - for stdout (default).")
    parser_detect.set_defaults(func=main_detect)

    try:
        args = parser.parse_args()
    except ArgumentParserError as e:
        log.die(str(e))

    # Set logging options
    log.set_verbose(args.verbose)
    log.set_quiet(args.quiet)
    log.set_use_color(args.use_color)

    # Initialize important environment variables
    autokernel.kconfig.initialize_environment()

    # Fallback to main_build_all() if no mode is given
    if 'func' not in args:
        main_build_all(args)
    else:
        # Execute the mode's function
        args.func(args)

    # TODO umask (probably better as external advice, ala "use umask then execute this".)

def main_checked():
    try:
        main()
    except PermissionError as e:
        log.die(str(e))
    except Exception as e: # pylint: disable=broad-except
        import traceback
        traceback.print_exc()
        log.die("Aborted because of previous errors")

if __name__ == '__main__':
    main_checked()
