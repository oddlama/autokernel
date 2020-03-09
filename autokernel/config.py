import os
import sys
from . import log
import lark
import lark.exceptions

class ConfigParsingException(Exception):
    def __init__(self, meta, message):
        super().__init__(message)
        self.meta = meta

_lark = None
def get_lark_parser():
    global _lark
    if _lark is None:
        with open(os.path.join(os.path.dirname(__file__), '../config.lark'), 'r') as f:
            _lark = lark.Lark(f.read(), propagate_positions=True, start='blck_root')

    return _lark

def apply_tree_nodes(nodes, callbacks):
    if type(callbacks) == list:
        callback_dict = {}
        for c in callbacks:
            callback_dict[c.__name__] = c
        callbacks = callback_dict

    for n in nodes:
        if n.__class__ == lark.Tree:
            if n.data in callbacks:
                callbacks[n.data](n)

def find_token(tree, token_name):
    for c in tree.children:
        if c.__class__ == lark.Token:
            if c.type == token_name:
                return c
    raise ConfigParsingException(tree.meta, "Missing token '{}'".format(token_name))

class BlockNode:
    def matches_tree(self, tree):
        return tree.data == ('blck_' + self.node_name)

    def parse_context(self, ctxt):
        pass

    def parse_block_params(self, blck):
        pass

    def parse_tree(self, tree):
        if not self.matches_tree(tree):
            raise ConfigParsingException(tree.meta, "{} cannot parse '{}'".format(self.__class__.__name__, tree.data))

        self.parse_block_params(tree)

        ctxt = None
        for c in tree.children:
            if c.__class__ == lark.Tree:
                if c.data == 'ctxt_' + self.node_name:
                    if ctxt:
                        raise ConfigParsingException(c.meta, "'{}' must not have multiple children of type '{}'".format("blck_" + self.node_name, "ctxt_" + self.node_name))
                    ctxt = c

        if not ctxt:
            raise ConfigParsingException(tree.meta, "'{}' must have exactly one child '{}'".format())

        self.parse_context(ctxt)

class ConfigModule(BlockNode):
    node_name = 'module'

    def __init__(self):
        self.name = None
        self.dependencies = []
        self.assignments = []
        self.assertions = []
        self.merge_kconf_files = []

    def parse_block_params(self, blck):
        def module_name(tree):
            token = find_token(tree, 'IDENTIFIER')
            self.name = str(token)

        apply_tree_nodes(blck.children, [module_name])

    def parse_context(self, ctxt):
        pass

class ConfigKernel(BlockNode):
    node_name = 'kernel'

    def __init__(self):
        self.module = ConfigModule()

    def parse_context(self, ctxt):
        pass

class ConfigGenkernel(BlockNode):
    node_name = 'genkernel'

    def __init__(self):
        self.params = []

    def parse_context(self, ctxt):
        pass

class ConfigInitramfs(BlockNode):
    node_name = 'initramfs'

    def __init__(self):
        self.genkernel = ConfigGenkernel()
        self.cmdline = []

    def parse_context(self, ctxt):
        pass

class ConfigInstall(BlockNode):
    node_name = 'install'

    def __init__(self):
        self.target_dir = None
        self.target = None

    def parse_context(self, ctxt):
        pass

class ConfigBuild(BlockNode):
    node_name = 'build'

    def __init__(self):
        pass

    def parse_context(self, ctxt):
        pass

class Config(BlockNode):
    node_name = 'root'

    def __init__(self):
        self.modules = []
        self.kernel = ConfigKernel()
        self.initramfs = ConfigInitramfs()
        self.install = ConfigInstall()
        self.build = ConfigBuild()

    def parse_context(self, ctxt):
        def blck_module(tree):
            module = ConfigModule()
            module.parse_tree(tree)
            self.modules.append(module)

        def blck_kernel(tree):
            self.kernel.parse_tree(tree)

        def blck_initramfs(tree):
            self.initramfs.parse_tree(tree)

        def blck_install(tree):
            self.install.parse_tree(tree)

        def blck_build(tree):
            self.build.parse_tree(tree)

        def stmt_include_module_dir(tree):
            pass

        def stmt_include_module(tree):
            pass

        apply_tree_nodes(ctxt.children, [
                blck_module,
                blck_kernel,
                blck_initramfs,
                blck_install,
                blck_build,
                stmt_include_module_dir,
                stmt_include_module,
            ])

    #def parse_tree(self, tree):
    #    if tree.data != "ctxt_root":
    #        raise ConfigParsingException(tree.meta, "Invalid root context")

    #    for c in tree.children:
    #        if not hasattr(c, 'data'):
    #            continue

    #        if c.data == "blck_module":
    #            module = ConfigModule()
    #            module.parse_tree(c)
    #            self.modules.append(module)
    #        elif c.data == "blck_kernel":
    #            self.kernel.parse_tree(c)
    #        elif c.data == "blck_initramfs":
    #            self.initramfs.parse_tree(c)
    #        elif c.data == "blck_install":
    #            self.install.parse_tree(c)
    #        elif c.data == "blck_build":
    #            self.build.parse_tree(c)
    #        elif c.data == "stmt_include_module_dir":
    #            pass
    #        elif c.data == "stmt_include_module":
    #            pass
    #        elif c.data == "extra_semicolon":
    #            pass
    #            # TODO print_error_in_file("example_config.conf", "Extra semicolon", c.meta)
    #        else:
    #            raise ConfigParsingException(c.meta, "Encountered invalid parsed token. This is an error in the application and should be reported.")

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
        except lark.exceptions.UnexpectedInput as e:
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
