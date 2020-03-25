import os
import sys
from . import log
import lark
import lark.exceptions

class ConfigParsingException(Exception):
    def __init__(self, meta, message):
        super().__init__(message)
        self.meta = meta

currently_parsed_filenames = []
_lark = None
def get_lark_parser():
    """
    Returns the lark parser for config files
    """
    global _lark
    if _lark is None:
        with open(os.path.join(os.path.dirname(__file__), '../config.lark'), 'r') as f:
            _lark = lark.Lark(f.read(), propagate_positions=True, start='blck_root')

    return _lark

def remove_quotes(s):
    """
    Strips leading and trailing quotes from the string, if any.
    """
    return s[1:-1] if s[0] == s[-1] == '"' else s

def parse_bool(tree, s):
    if s in ['true', '1', 'yes', 'y']:
        return True
    elif s in ['false', '0', 'no', 'n']:
        return False
    else:
        raise ConfigParsingException(tree.meta, "Invalid value for boolean")

def redefinition_exception(tree, name):
    return ConfigParsingException(tree.meta, "Duplicate definition of {}".format(name))

def apply_tree_nodes(nodes, callbacks, on_additional=None, ignore_additional=False):
    """
    For each node calls the callback matching its name.
    Raises an exception for unmatched nodes if ignore_additional is not set.
    """
    if type(callbacks) == list:
        callback_dict = {}
        for c in callbacks:
            callback_dict[c.__name__] = c
        callbacks = callback_dict

    for n in nodes:
        if n.__class__ == lark.Tree:
            if n.data in callbacks:
                callbacks[n.data](n)
            elif n.data == "extra_semicolon":
                log.verbose("Extra semicolon at {}:{}:{}".format(currently_parsed_filenames[-1], n.line, n.column))
            elif on_additional:
                on_additional(n)
            elif not ignore_additional:
                raise ConfigParsingException(n.meta, "unprocessed rule '{}'; this is a bug that should be reported.".format(n.data))

def find_token(tree, token_name, ignore_missing=False, strip_quotes=True):
    """
    Finds a token by literal name in the children of the given tree. Raises
    an exception if the token is not found and ignore_missing is not set.
    """
    for c in tree.children:
        if c.__class__ == lark.Token and c.type == token_name:
            return remove_quotes(str(c)) if strip_quotes else str(c)

    if not ignore_missing:
        raise ConfigParsingException(tree.meta, "Missing token '{}'".format(token_name))
    return None

def find_named_token(tree, token_name, ignore_missing=False, strip_quotes=True):
    """
    Finds a token by subrule name in the children of the given tree. Raises
    an exception if the token is not found.
    """
    for c in tree.children:
        if c.__class__ == lark.Tree and c.data == token_name:
            if len(c.children) != 1:
                raise ConfigParsingException(c.meta, "Subrule token '{}' has too many children".format(token_name))
            if c.children[0].__class__ == lark.Token:
                return remove_quotes(str(c.children[0])) if strip_quotes else str(c.children[0])
            else:
                raise ConfigParsingException(c.meta, "Subrule token '{}' has no children literal".format(token_name))

    if not ignore_missing:
        raise ConfigParsingException(tree.meta, "Missing token '{}'".format(token_name))
    return None

def find_all_tokens(tree, token_name, strip_quotes=True):
    """
    Finds all tokens by name in the children of the given tree.
    """
    return [remove_quotes(str(c)) if strip_quotes else str(c) \
            for c in tree.children \
                if c.__class__ == lark.Token and c.type == token_name]

def find_all_named_tokens(tree, token_name, strip_quotes=True):
    """
    Finds all tokens by subrule name in the children of the given tree.
    """
    return [remove_quotes(str(c.children[0])) if strip_quotes else str(c.children[0]) \
            for c in tree.children
                if c.__class__ == lark.Tree
                and c.data == token_name
                and len(c.children) == 1
                and c.children[0].__class__ == lark.Token]

class UniqueProperty:
    """
    A property that tracks if it has been changed, stores a default
    value and raises an error if it is assigned more than once.
    """
    def __init__(self, name, default, convert_bool=False):
        self.name = name
        self.default = default
        self.value = None
        self.convert_bool = convert_bool

    def defined(self):
        return self.value is not None

    def parse(self, tree, token=None, named_token=None, ignore_missing=None):
        default_if_ignored = ignore_missing
        ignore_missing = default_if_ignored is not None

        if self.defined():
            raise redefinition_exception(tree, self.name)
        if token:
            tok = find_token(tree, token, ignore_missing=ignore_missing)
        elif named_token:
            tok = find_named_token(tree, named_token, ignore_missing=ignore_missing)
        else:
            raise ValueError("Missing token identifier argument; this is a bug that should be reported.")

        if ignore_missing:
            tok = tok or default_if_ignored

        if self.convert_bool:
            self.value = parse_bool(tree, tok)
        else:
            self.value = tok

    def __bool__(self):
        return bool(self.__get__())

    def __get__(self):
        return self.default if self.value is None else self.value

    def __str__(self):
        return self.__get__()

class BlockNode:
    """
    A base class for blocks to help with tree parsing.
    """
    def parse_context(self, ctxt):
        """
        Called to parse the related context
        """
        pass

    def parse_block_params(self, blck, *args, **kwargs):
        """
        Called to parse additional block parameters
        """
        pass

    def parse_tree(self, tree, *args, **kwargs):
        """
        Parses the given block tree node, and class parse_block_params and parse_context.
        """
        if not hasattr(self, 'first_definition'):
            self.first_definition = (tree.meta, currently_parsed_filenames[-1])

        if tree.data != ('blck_' + self.node_name):
            raise ConfigParsingException(tree.meta, "{} cannot parse '{}'".format(self.__class__.__name__, tree.data))

        self.parse_block_params(tree, *args, **kwargs)

        ctxt = None
        for c in tree.children:
            if c.__class__ == lark.Tree:
                if c.data == 'ctxt_' + self.node_name:
                    if ctxt:
                        raise ConfigParsingException(c.meta, "'{}' must not have multiple children of type '{}'".format("blck_" + self.node_name, "ctxt_" + self.node_name))
                    ctxt = c

        if not ctxt:
            raise ConfigParsingException(tree.meta, "'{}' must have exactly one child '{}'".format())

        self.parse_context(ctxt, *args, **kwargs)

class ConfigModule(BlockNode):
    node_name = 'module'

    def __init__(self):
        self.name = None
        self.uses = []
        self.dependencies = []
        self.merge_kconf_files = []
        self.assertions = []
        self.assignments = []

    def parse_block_params(self, blck):
        def module_name(tree):
            self.name = find_token(tree, 'IDENTIFIER')

        apply_tree_nodes(blck.children, [module_name], ignore_additional=True)

    def parse_context(self, ctxt):
        def stmt_module_use(tree):
            self.uses.extend(find_all_tokens(tree, 'IDENTIFIER'))
        def stmt_module_merge(tree):
            self.merge_kconf_files.append(find_named_token(tree, 'path'))
        def stmt_module_assert(tree):
            key = find_token(tree, 'KERNEL_OPTION')
            value = find_named_token(tree, 'kernel_option_value', ignore_missing=True) or 'y'
            self.assertions.append((key, value))
        def stmt_module_set(tree):
            key = find_token(tree, 'KERNEL_OPTION')
            value = find_named_token(tree, 'kernel_option_value', ignore_missing=True) or 'y'
            self.assignments.append((key, value))

        apply_tree_nodes(ctxt.children, [
                stmt_module_use,
                stmt_module_merge,
                stmt_module_assert,
                stmt_module_set,
            ])

class ConfigKernel(BlockNode):
    node_name = 'kernel'

    def __init__(self):
        self.module = ConfigModule()
        self.cmdline = []

    def parse_context(self, ctxt):
        def ctxt_module(tree):
            self.module.parse_context(tree)
        def stmt_kernel_add_cmdline(tree):
            self.cmdline.extend(find_all_named_tokens(tree, 'param'))

        apply_tree_nodes(ctxt.children, [
                ctxt_module,
                stmt_kernel_add_cmdline,
            ])

class ConfigGenkernel(BlockNode):
    node_name = 'genkernel'

    def __init__(self):
        self.params = []

    def parse_context(self, ctxt):
        def stmt_genkernel_add_params(tree):
            self.params.extend(find_all_named_tokens(tree, 'param'))

        apply_tree_nodes(ctxt.children, [
                stmt_genkernel_add_params,
            ])

class ConfigInitramfs(BlockNode):
    node_name = 'initramfs'

    def __init__(self):
        self.genkernel = ConfigGenkernel()
        self.cmdline = []

    def parse_context(self, ctxt):
        def blck_genkernel(tree):
            self.genkernel.parse_tree(tree)
        def stmt_initramfs_add_cmdline(tree):
            self.cmdline.extend(find_all_named_tokens(tree, 'param'))

        apply_tree_nodes(ctxt.children, [
                blck_genkernel,
                stmt_initramfs_add_cmdline,
            ])

class ConfigEfi(BlockNode):
    node_name = 'efi'

    def __init__(self):
        pass

    def parse_context(self, ctxt):
        pass

class ConfigInstall(BlockNode):
    node_name = 'install'

    def __init__(self):
        self.efi = ConfigEfi()
        self.target_dir = UniqueProperty('target_dir', default='/boot')
        self.target = UniqueProperty('target', default='vmlinuz-{KV}')
        self.mount = []
        self.assert_mounted = []

    def parse_context(self, ctxt):
        def blck_efi(tree):
            self.efi.parse_tree(tree)
        def stmt_install_target_dir(tree):
            self.target_dir.parse(tree, named_token='path')
        def stmt_install_target(tree):
            if self.target:
                raise redefinition_exception(tree, 'target')
            self.target = find_named_token(tree, 'path')
        def stmt_install_mount(tree):
            self.mount.append(find_named_token(tree, 'path'))
        def stmt_install_assert_mounted(tree):
            self.assert_mounted.append(find_named_token(tree, 'path'))

        apply_tree_nodes(ctxt.children, [
                blck_efi,
                stmt_install_target_dir,
                stmt_install_target,
                stmt_install_mount,
                stmt_install_assert_mounted,
            ])

class ConfigBuild(BlockNode):
    node_name = 'build'

    def __init__(self):
        self.enable_initramfs = UniqueProperty('initramfs', default=False, convert_bool=True)
        self.pack = {
                'initramfs': UniqueProperty('pack initramfs', default=False, convert_bool=True),
                'cmdline': UniqueProperty('pack cmdline', default=False, convert_bool=True),
            }

    def parse_context(self, ctxt):
        def stmt_build_initramfs(tree):
            self.enable_initramfs.parse(tree, token='STRING')
        def stmt_build_pack(tree):
            key = find_token(tree, 'STRING')
            if key not in self.pack:
                return ConfigParsingException(tree.meta, "Invalid parameter '{}'".format(key))
            self.pack[key].parse(tree, named_token='param', ignore_missing='true')

        apply_tree_nodes(ctxt.children, [
                stmt_build_initramfs,
                stmt_build_pack,
            ])

class Config(BlockNode):
    node_name = 'root'

    def __init__(self):
        self.modules = {}
        self.kernel = ConfigKernel()
        self.initramfs = ConfigInitramfs()
        self.install = ConfigInstall()
        self.build = ConfigBuild()
        self._include_module_files = set()

    def parse_context(self, ctxt, restrict_to_modules=False):
        def _include_module_file(tree, filename):
            rpath = os.path.realpath(filename)
            if rpath in self._include_module_files:
                log.verbose("Skipping duplicate inclusion of '{}'".format(rpath))
                return
            else:
                self._include_module_files.add(rpath)

            if os.path.isfile(filename):
                try:
                    subtree = load_config_tree(filename)
                except IOError as e:
                    raise ConfigParsingException(tree.meta, str(e))

                try:
                    currently_parsed_filenames.append(filename)
                    self.parse_tree(subtree, restrict_to_modules=True)
                    currently_parsed_filenames.pop()
                except ConfigParsingException as e:
                    print_parsing_exception(filename, e)
                    sys.exit(1)
            else:
                raise ConfigParsingException(tree.meta, "'{}' does not exist or is not a file.".format(filename))

        def blck_module(tree):
            module = ConfigModule()
            module.parse_tree(tree)
            if module.name in self.modules:
                dt, df = self.modules[module.name].first_definition
                raise ConfigParsingException(tree.meta, "redefinition of module '{}' (previously defined in {}:{}:{})".format(module.name, df, dt.line, dt.column))
            self.modules[module.name] = module
        def blck_kernel(tree):
            self.kernel.parse_tree(tree)
        def blck_initramfs(tree):
            self.initramfs.parse_tree(tree)
        def blck_install(tree):
            self.install.parse_tree(tree)
        def blck_build(tree):
            self.build.parse_tree(tree)
        def stmt_root_include_module_dir(tree):
            dir = os.path.join(os.path.dirname(currently_parsed_filenames[-1]), find_named_token(tree, 'path'))
            if os.path.isdir(dir):
                for filename in os.listdir(dir):
                    _include_module_file(tree, os.path.join(dir, filename))
            else:
                raise ConfigParsingException(tree.meta, "'{}' is not a directory".format(dir))
        def stmt_root_include_module(tree):
            filename = os.path.join(os.path.dirname(currently_parsed_filenames[-1]), find_named_token(tree, 'path'))
            _include_module_file(tree, filename)

        if restrict_to_modules:
            def other(tree):
                raise ConfigParsingException(tree.meta, "'{}' must not be used in a module config".format(tree.data))

            apply_tree_nodes(ctxt.children, [
                    blck_module,
                ], on_additional=other)
        else:
            apply_tree_nodes(ctxt.children, [
                    blck_module,
                    blck_kernel,
                    blck_initramfs,
                    blck_install,
                    blck_build,
                    stmt_root_include_module_dir,
                    stmt_root_include_module,
                ])

def print_line_with_highlight(line, line_nr, highlight):
    tabs_before = line[:highlight[0]-1].count('\t')
    tabs_in_highlight = line[highlight[0]-1:highlight[1]-2].count('\t')
    print("{:5d} | {}".format(line_nr, line[:-1].replace('\t', '    ')))
    print("      | {}".format(" " * ((highlight[0] - 1) + tabs_before * 3) + "[1;31m^" + "~" * ((highlight[1] - highlight[0] - 1) + tabs_in_highlight * 3) + "[m"))

def print_error_in_file(file, message, line, column_range):
    print("[1m{}:{}:{}:[m [1;31merror:[m {}".format(file, line, column_range[0], message), file=sys.stderr)
    with open(file, 'r') as f:
        line_str = f.readlines()[line - 1]
        print_line_with_highlight(line_str, line, highlight=column_range)

def print_parsing_exception(file, e):
    if e.meta.line == e.meta.end_line:
        print_error_in_file(file, str(e), e.meta.line, (e.meta.column, e.meta.end_column))
    else:
        print_error_in_file(file, str(e), e.meta.line, (e.meta.column, e.meta.column + 1))

def load_config_tree(config_file):
    """
    Loads the autokernel configuration file and returns the parsed tree.
    """
    larkparser = get_lark_parser()
    with open(config_file, 'r') as f:
        try:
            return larkparser.parse(f.read())
        except lark.exceptions.UnexpectedInput as e:
            print_error_in_file(config_file, str(e).splitlines()[0], e.line, (e.column, e.column))
            sys.exit(1)

def load_config(config_file):
    """
    Loads the autokernel configuration file.
    """
    tree = load_config_tree(config_file)
    config = Config()
    try:
        currently_parsed_filenames.append(config_file)
        config.parse_tree(tree)
        currently_parsed_filenames.pop()
    except ConfigParsingException as e:
        print_parsing_exception(config_file, e)
        sys.exit(1)

    def get_module(u):
        if u not in config.modules:
            log.error("Module '{}' used but never defined".format(u))
            sys.exit(1)
        return config.modules[u]

    # Resolve module dependencies
    for m in config.modules:
        mod = config.modules[m]
        mod.dependencies = [get_module(u) for u in mod.uses]

    # Resolve kernel dependencies
    kmod = config.kernel.module
    kmod.dependencies = [get_module(u) for u in kmod.uses]

    return config
