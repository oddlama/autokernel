import os
import sys
from . import log
from lark import Lark
from lark.exceptions import UnexpectedInput

class ConfigParsingException(Exception):
    def __init__(self, meta, message):
        super().__init__(message)
        self.meta = meta

_lark = None
def get_lark_parser():
    global _lark
    if _lark is None:
        with open(os.path.join(os.path.dirname(__file__), '../config.lark'), 'r') as f:
            _lark = Lark(f.read(), propagate_positions=True, start='ctxt_root')

    return _lark

class ConfigModule:
    def __init__(self):
        self.name = None
        self.dependencies = []
        self.assignments = []
        self.assertions = []
        self.merge_kconf_files = []

class ConfigKernel:
    def __init__(self):
        self.module = ConfigModule()

class ConfigGenkernel:
    def __init__(self):
        self.params = []

class ConfigInitramfs:
    def __init__(self):
        self.genkernel = ConfigGenkernel()
        self.cmdline = []

class ConfigInstall:
    def __init__(self):
        self.target_dir = None
        self.target = None

class ConfigBuild:
    def __init__(self):
        pass

class Config:
    def __init__(self):
        self.modules = []
        self.kernel = ConfigKernel()
        self.initramfs = ConfigInitramfs()
        self.install = ConfigInstall()
        self.build = ConfigBuild()

    def parse_tree(self, tree):
        if tree.data != "ctxt_root":
            raise ConfigParsingException(tree.meta, "Invalid root context")

        for c in tree.children:
            if not hasattr(c, 'data'):
                continue

            if c.data == "blck_module":
                module = ConfigModule()
                module.parse_tree()
                self.modules.append(module)
            elif c.data == "blck_kernel":
                self.kernel.parse_tree(tree)
            elif c.data == "blck_initramfs":
                self.initramfs.parse_tree(tree)
            elif c.data == "blck_install":
                self.install.parse_tree(tree)
            elif c.data == "blck_build":
                self.build.parse_tree(tree)
            elif c.data == "stmt_include_module_dir":
                pass
            elif c.data == "stmt_include_module":
                pass
            elif c.data == "extra_semicolon":
                pass
                # TODO print_error_in_file("example_config.conf", "Extra semicolon", c.meta)
            else:
                raise ConfigParsingException(c.meta, "Encountered invalid parsed token. This is an error in the application and should be reported.")

def print_line_with_highlight(line, line_nr, highlight):
    tabs_before = line[:highlight[0]-1].count('\t')
    tabs_in_highlight = line[highlight[0]-1:highlight[1]-1].count('\t')
    print("{:5d} | {}".format(line_nr, line[:-1].replace('\t', '    ')))
    print("      | {}".format(" " * ((highlight[0] - 1) + tabs_before * 3) + "[1;31m^" + "~" * ((highlight[1] - highlight[0]) + tabs_in_highlight * 3) + "[m"))

def print_error_in_file(file, message, line, column_range):
    print("[1m{}:{}:{}:[m [1;31merror:[m {}".format(file, line, column_range[0], message), file=sys.stderr)
    with open(file, 'r') as f:
        line_str = f.readlines()[line - 1]
        print_line_with_highlight(line_str, line, highlight=column_range)

def print_parsing_exception(file, e):
    if hasattr(e.meta, 'column_end'):
        print_error_in_file(file, str(e), e.meta.line, (e.meta.column, e.meta.column_end))
    else:
        print_error_in_file(file, str(e), e.meta.line, (e.meta.column, e.meta.column))

def load_config(config_file):
    """
    Loads the autokernel configuration file.
    """
    lark = get_lark_parser()
    with open(config_file, 'r') as f:
        try:
            tree = lark.parse(f.read())
        except UnexpectedInput as e:
            print_error_in_file(config_file, str(e).splitlines()[0], e.line, (e.column, e.column))
            sys.exit(1)

    config = Config()
    try:
        config.parse_tree(tree)
    except ConfigParsingException as e:
        print_parsing_exception(config_file, e)
        sys.exit(1)

    sys.exit(0)
    return config
