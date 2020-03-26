import os
import sys
import re
import lark
import lark.exceptions
import sympy

from . import log
from . import kconfig as atk_kconfig

kernel_option_regex = re.compile('^[_A-Z0-9]+$')


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
    global _lark # pylint: disable=global-statement
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

def find_first_child(tree, name):
    for c in tree.children:
        if c.data == name:
            return c
    return None

def find_token(tree, token_name, ignore_missing=False, strip_quotes=False):
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

def find_named_token_raw(tree, token_name, ignore_missing=False):
    """
    Finds a token by subrule name in the children of the given tree. Raises
    an exception if the token is not found.
    """
    for c in tree.children:
        if c.__class__ == lark.Tree and c.data == token_name:
            if len(c.children) != 1:
                raise ConfigParsingException(c.meta, "Subrule token '{}' has too many children".format(token_name))

            if c.children[0].data not in ['string', 'string_quoted']:
                raise ConfigParsingException(c.meta, "Subrule token '{}.{}' has an invalid name (must be either 'string' or 'string_quoted')".format(token_name, c.children[0].data))

            if c.children[0].__class__ != lark.Tree:
                raise ConfigParsingException(c.meta, "Subrule token '{}.{}' has no children tree".format(token_name, c.children[0].data))

            if len(c.children[0].children) != 1:
                raise ConfigParsingException(c.meta, "Subrule token '{}.{}' has too many children".format(token_name, c.children[0].data))

            if c.children[0].children[0].__class__ != lark.Token:
                raise ConfigParsingException(c.meta, "Subrule token '{}.{}' has no children literal".format(token_name, c.children[0].data))

            if c.children[0].data == 'string':
                return (str(c.children[0].children[0]), False)
            elif c.children[0].data == 'string_quoted':
                return (remove_quotes(str(c.children[0].children[0])), True)

    if not ignore_missing:
        raise ConfigParsingException(tree.meta, "Missing token '{}'".format(token_name))
    return (None, None)

def find_named_token(tree, token_name, ignore_missing=False):
    """
    Finds a token by subrule name in the children of the given tree. Raises
    an exception if the token is not found. Strips quotes if it was a quoted string.
    """
    return find_named_token_raw(tree, token_name, ignore_missing=ignore_missing)[0]

def find_all_tokens(tree, token_name, strip_quotes=False):
    """
    Finds all tokens by name in the children of the given tree.
    """
    return [remove_quotes(str(c)) if strip_quotes else str(c) \
            for c in tree.children \
                if c.__class__ == lark.Token and c.type == token_name]

def find_all_named_tokens(tree, token_name):
    """
    Finds all tokens by subrule name in the children of the given tree.
    """
    return [remove_quotes(str(c.children[0].children[0])) if c.children[0].data == 'string_quoted' else str(c.children[0]) \
            for c in tree.children
                if c.__class__ == lark.Tree
                and c.data == token_name
                and len(c.children) == 1
                and c.children[0].data in ['string', 'string_quoted']
                and c.children[0].__class__ == lark.Tree
                and len(c.children[0].children) == 1
                and c.children[0].children[0].__class__ == lark.Token]

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

    def _get(self):
        return self.default if self.value is None else self.value

    def __bool__(self):
        return bool(self._get())

    def __str__(self):
        return self._get()

special_var_cmp_mode = {
    '$KERNEL_VERSION': 'semver'
}

def get_special_var_cmp_mode(var):
    if var not in special_var_cmp_mode:
        log.die("Unknown special variable '{}'".format(var))
    return special_var_cmp_mode[var]

def resolve_special_variable(var):
    if var == '$KERNEL_VERSION':
        return atk_kconfig.kernel_version
    else:
        log.die("Unknown special variable '{}'".format(var))

def semver_to_int(ver):
    t = ver.split('-')[0].split('.')
    if len(t) < 3:
        t.extend([0] * (3 - len(t)))
    elif len(t) > 3:
        raise ValueError("Invalid semver '{}'".format(ver))

    return int(t[0]) << 64 + int(t[1]) << 32 + int(t[2])

def compare_variables(lhs, rhs, op, cmp_mode):
    if cmp_mode == 'string':
        if op not in ['EXPR_CMP_NEQ', 'EXPR_CMP_EQ']:
            log.die("Invalid comparison '{}' between '{}' and '{}' (type 'string')".format(op, lhs, rhs))
    elif cmp_mode == 'int':
        lhs = int(lhs)
        rhs = int(rhs)
    elif cmp_mode == 'semver':
        lhs = semver_to_int(lhs)
        rhs = semver_to_int(rhs)

    if op == 'EXPR_CMP_GE':
        return lhs > rhs
    elif op == 'EXPR_CMP_GEQ':
        return lhs >= rhs
    elif op == 'EXPR_CMP_LE':
        return lhs < rhs
    elif op == 'EXPR_CMP_LEQ':
        return lhs <= rhs
    elif op == 'EXPR_CMP_NEQ':
        return lhs != rhs
    elif op == 'EXPR_CMP_EQ':
        return lhs == rhs

class Condition:
    def __init__(self, sympy_expr):
        self.expr = sympy_expr
        self.value = None

    def evaluate(self, kconfig, symbol_changes):
        if self.value is None:
            self.value = self._evaluate(kconfig, symbol_changes)
        return self.value

    def _evaluate(self, kconfig, symbol_changes):
        def get_sym(sym_name):
            try:
                sym = kconfig.syms[sym_name]
            except KeyError:
                log.die("Referenced symbol '{}' does not exist".format(sym_name))

            # If the symbol hadn't been encountered before, pin the current value
            if sym not in symbol_changes:
                symbol_changes[sym] = sym.str_value

            return sym

        subs = {}
        for s in self.expr.free_symbols:
            if s.name.count('\001') == 2:
                lhs, op, rhs = s.name.split('\001')
                if op not in ['EXPR_CMP_GE', 'EXPR_CMP_GEQ', 'EXPR_CMP_LE', 'EXPR_CMP_LEQ', 'EXPR_CMP_NEQ', 'EXPR_CMP_EQ']:
                    log.die("Invalid comparison op '{}'. This is a bug.".format(op))

                def resolve_var(var):
                    var_quoted = var[0] == "1"
                    var = var[1:]

                    # Remember if var were special variables
                    var_special = var.startswith('$')

                    # Resolve symbols
                    var_is_sym = not var_quoted and not var_special and kernel_option_regex.match(var)
                    if var_is_sym:
                        var = get_sym(var).str_value

                    # Find cmp mode and replace variable if it is special
                    var_cmp_mode = None
                    if var_special:
                        var_cmp_mode = get_special_var_cmp_mode(var)
                        var = resolve_special_variable(var)

                    return (var, var_quoted, var_special, var_is_sym, var_cmp_mode)

                lhs, lhs_quoted, lhs_special, lhs_is_sym, lhs_cmp_mode = resolve_var(lhs)
                rhs, rhs_quoted, rhs_special, rhs_is_sym, rhs_cmp_mode = resolve_var(rhs)

                # Find out final comparison mode
                if lhs_special or rhs_special:
                    # If both were special, we have to assert they resolved to the same cmp mode
                    if lhs_cmp_mode and rhs_cmp_mode:
                        if lhs_cmp_mode != rhs_cmp_mode:
                            log.die("Cannot compare special symbols of different type {} (type {}) to {} (type {})".format(lhs, lhs_cmp_mode, rhs, rhs_cmp_mode))
                        cmp_mode = lhs_cmp_mode
                    else:
                        # One of the variables wasn't special, so we can use the one deduced comparison mode
                        cmp_mode = lhs_cmp_mode or rhs_cmp_mode
                else:
                    # If both variables are not special, we have to find the comparison mode
                    # based on if the arguments are quoted. If both are symbols, we use
                    # string comparison. If either is not a symbol, we do string comparison if
                    # the argument is quoted and integer comparison otherwise.
                    if lhs_is_sym and rhs_is_sym:
                        cmp_mode = 'string'
                    else:
                        if lhs_quoted or rhs_quoted:
                            cmp_mode = 'string'
                        else:
                            cmp_mode = 'int'

                subs[s.name] = compare_variables(lhs, rhs, op, cmp_mode)
            else:
                subs[s.name] = atk_kconfig.tri_to_bool(get_sym(s.name).tri_value)
        return self.expr.subs(subs)

def parse_expr(tree):
    if tree.data == 'expr':
        return sympy.Or(*[parse_expr(c) for c in tree.children if c.__class__ == lark.Tree and c.data == 'expr_term'])
    if tree.data == 'expr_term':
        return sympy.And(*[parse_expr(c) for c in tree.children if c.__class__ == lark.Tree and c.data == 'expr_factor'])
    elif tree.data == 'expr_factor':
        negated = find_first_child(tree, 'expr_op_neg') is not None
        def negate_if_needed(s):
            return sympy.Not(s) if negated else s

        expr_cmp = find_first_child(tree, 'expr_cmp')
        if expr_cmp:
            lhs, lhs_quoted = find_named_token_raw(expr_cmp, 'expr_lhs')
            rhs, rhs_quoted = find_named_token_raw(expr_cmp, 'expr_rhs')
            operation = find_first_child(expr_cmp, 'expr_op_cmp').children[0].type
            return negate_if_needed(sympy.Symbol("{}{}\001{}\001{}{}".format('1' if lhs_quoted else '0', lhs, operation, '1' if rhs_quoted else '0', rhs)))

        expr_id = find_first_child(tree, 'expr_id')
        if expr_id:
            return negate_if_needed(sympy.Symbol(str(expr_id.children[0])))

        expr = find_first_child(tree, 'expr')
        if expr:
            return negate_if_needed(parse_expr(expr))

        raise ConfigParsingException(tree.meta, "Invalid expression subtree '{}' in 'expr_factor'".format(tree.data))
    else:
        raise ConfigParsingException(tree.meta, "Invalid expression subtree '{}'".format(tree.data))

def find_subtrees(tree, name):
    """
    Returns all subtrees with given name
    """
    return [c for c in tree.children if c.__class__ == lark.Tree and c.data == name]

def find_conditions(tree, name='expr'):
    """
    Returns all conditions in the direct subtree.
    """
    return [parse_expr(expr) for expr in find_subtrees(tree, name)]

def find_condition(tree, ignore_missing=True):
    conditions = find_conditions(tree)

    if len(conditions) == 0:
        if ignore_missing:
            return sympy.true
        else:
            raise ConfigParsingException(tree.meta, "Missing expression")

    if len(conditions) == 1:
        return conditions[0]

    raise ConfigParsingException(tree.meta, "Expected exactly one expression, but got {}".format(len(conditions)))

class BlockNode:
    """
    A base class for blocks to help with tree parsing.
    """

    node_name = None
    first_definition = None # Will be overwritten

    def parse_context(self, ctxt):
        """
        Called to parse the related context
        """
        pass # pylint: disable=unnecessary-pass

    def parse_block_params(self, blck, *args, **kwargs):
        """
        Called to parse additional block parameters
        """
        pass # pylint: disable=unnecessary-pass

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
            raise ConfigParsingException(tree.meta, "'{}' must have exactly one child '{}'".format("blck_" + self.node_name, "ctxt_" + self.node_name))

        self.parse_context(ctxt, *args, **kwargs)

class ConfigModule(BlockNode):
    node_name = 'module'

    class StmtUse:
        def __init__(self, cond, module_name):
            self.condition = cond
            self.module_name = module_name
            self.module = None
    class StmtMerge:
        def __init__(self, cond, filename):
            self.condition = cond
            self.filename = filename
    class StmtAssert:
        def __init__(self, cond, sym_name, value):
            self.condition = cond
            self.sym_name = sym_name
            self.value = value
    class StmtSet:
        def __init__(self, cond, sym_name, value):
            self.condition = cond
            self.sym_name = sym_name
            self.value = value

    def __init__(self):
        self.name = None
        self.uses = []
        self.merge_kconf_files = []
        self.assertions = []
        self.assignments = []
        self.all_statements_in_order = []

    def parse_block_params(self, blck): # pylint: disable=arguments-differ
        def module_name(tree):
            self.name = find_token(tree, 'IDENTIFIER')

        apply_tree_nodes(blck.children, [module_name], ignore_additional=True)

    def parse_context(self, ctxt, precondition=sympy.true): # pylint: disable=arguments-differ
        def stmt_module_if(tree):
            conditions = find_conditions(tree)
            subcontexts = find_subtrees(tree, 'ctxt_module')
            if len(subcontexts) - len(conditions) not in [0, 1]:
                raise ConfigParsingException(tree.meta, "invalid amount of subcontexts(={}) and conditions(={}) for if block; this is a bug that should be reported.".format(len(subcontexts), len(conditions)))

            previous_conditions = []
            def negate_previous():
                return sympy.Not(sympy.Or(*previous_conditions))

            for c, s in zip(conditions, subcontexts):
                # The condition for an else if block is the combined negation of all previous conditions,
                # and its own condition
                cond = precondition & negate_previous() & c
                self.parse_context(s, precondition=cond)
                previous_conditions.append(c)

            if len(subcontexts) > len(conditions):
                # The condition for the else block is the combined negation of all previous conditions
                cond = precondition & negate_previous()
                self.parse_context(subcontexts[-1], precondition=cond)

        def stmt_module_use(tree):
            cond = Condition(precondition & find_condition(tree))
            new_uses = [ConfigModule.StmtUse(cond, i) for i in find_all_tokens(tree, 'IDENTIFIER')]
            self.uses.extend(new_uses)
            self.all_statements_in_order.extend(new_uses)
        def stmt_module_merge(tree):
            cond = Condition(precondition & find_condition(tree))
            stmt = ConfigModule.StmtMerge(cond, find_named_token(tree, 'path'))
            self.merge_kconf_files.append(stmt)
            self.all_statements_in_order.append(stmt)
        def stmt_module_assert(tree):
            cond = Condition(precondition & find_condition(tree))
            key = find_token(tree, 'KERNEL_OPTION')
            value = find_named_token(tree, 'kernel_option_value', ignore_missing=True) or 'y'
            stmt = ConfigModule.StmtAssert(cond, key, value)
            self.assertions.append(stmt)
            self.all_statements_in_order.append(stmt)
        def stmt_module_set(tree):
            cond = Condition(precondition & find_condition(tree))
            key = find_token(tree, 'KERNEL_OPTION')
            value = find_named_token(tree, 'kernel_option_value', ignore_missing=True) or 'y'
            stmt = ConfigModule.StmtSet(cond, key, value)
            self.assignments.append(stmt)
            self.all_statements_in_order.append(stmt)

        apply_tree_nodes(ctxt.children, [
                stmt_module_if,
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
            self.enable_initramfs.parse(tree, named_token='param')
        def stmt_build_pack(tree):
            key = find_named_token(tree, 'key')
            if key not in self.pack:
                raise ConfigParsingException(tree.meta, "Invalid parameter '{}'".format(key))
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

    def parse_context(self, ctxt, restrict_to_modules=False): # pylint: disable=arguments-differ
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
            include_dir = os.path.join(os.path.dirname(currently_parsed_filenames[-1]), find_named_token(tree, 'path'))
            if os.path.isdir(include_dir):
                for filename in os.listdir(include_dir):
                    _include_module_file(tree, os.path.join(include_dir, filename))
            else:
                raise ConfigParsingException(tree.meta, "'{}' is not a directory".format(include_dir))
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
        except (lark.exceptions.UnexpectedCharacters, lark.exceptions.UnexpectedToken) as e:
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
        for u in mod.uses:
            u.module = get_module(u.module_name)

    # Resolve kernel dependencies
    kmod = config.kernel.module
    for u in kmod.uses:
        u.module = get_module(u.module_name)

    return config
