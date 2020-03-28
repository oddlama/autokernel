import os
import sys
import re
import lark
import lark.exceptions
import kconfiglib

from . import log
from . import kconfig as atk_kconfig

kernel_option_regex = re.compile('^[_A-Z0-9]+$')
currently_parsed_filenames = []

class ConfigParsingException(Exception):
    def __init__(self, meta, message):
        super().__init__(message)
        self.meta = meta

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

def print_line_with_highlight(line, line_nr, highlight):
    tabs_before = line[:highlight[0]-1].count('\t')
    tabs_in_highlight = line[highlight[0]-1:highlight[1]-2].count('\t')
    print("{:5d} | {}".format(line_nr, line[:-1].replace('\t', '    ')))
    print("      | {}".format(" " * ((highlight[0] - 1) + tabs_before * 3) + log.color("[1;34m") + "^" + "~" * ((highlight[1] - highlight[0] - 1) + tabs_in_highlight * 3) + log.color_reset))

def msg_warn(msg):
    return log.color("[1;33m") + "warning:" + log.color_reset + " " + msg

def msg_error(msg):
    return log.color("[1;31m") + "error:" + log.color_reset + " " + msg

def print_message_with_file_location(file, message, line, column_range):
    if not file:
        print(message, file=sys.stderr)
    else:
        print((log.color("[1m") + "{}:{}:{}:" + log.color_reset + " {}").format(
            file, line, column_range[0], message), file=sys.stderr)
        with open(file, 'r') as f:
            line_str = f.readlines()[line - 1]
            print_line_with_highlight(line_str, line, highlight=column_range)

def print_message_at(definition, msg):
    if definition:
        meta, file = definition
        if meta.line == meta.end_line:
            print_message_with_file_location(file, msg, meta.line, (meta.column, meta.end_column))
        else:
            print_message_with_file_location(file, msg, meta.line, (meta.column, meta.column + 1))
    else:
        print_message_with_file_location(None, msg, None, None)

def print_warn_at(definition, msg):
    print_message_at(definition, msg_warn(msg))

def print_error_at(definition, msg):
    print_message_at(definition, msg_error(msg))

def die_print_error_at(definition, msg):
    print_error_at(definition, msg)
    sys.exit(1)

def die_print_parsing_exception(file, e):
    die_print_error_at((e.meta, file), str(e))

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

def find_all_named_tokens_raw(tree, token_name):
    """
    Finds all tokens by subrule name in the children of the given tree.
    """
    return [(remove_quotes(str(c.children[0].children[0])), True) if c.children[0].data == 'string_quoted' else (str(c.children[0]), False) \
            for c in tree.children
                if c.__class__ == lark.Tree
                and c.data == token_name
                and len(c.children) == 1
                and c.children[0].data in ['string', 'string_quoted']
                and c.children[0].__class__ == lark.Tree
                and len(c.children[0].children) == 1
                and c.children[0].children[0].__class__ == lark.Token]

def find_all_named_tokens(tree, token_name):
    """
    Finds all tokens by subrule name in the children of the given tree.
    """
    return [i[0] for i in find_all_named_tokens_raw(tree, token_name)]

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
    '$kernel_version': 'semver',
    '$arch':  'string',
    '$false': 'string',
    '$true':  'string',
}

def get_special_var_cmp_mode(var):
    if var not in special_var_cmp_mode:
        log.die("Unknown special variable '{}'".format(var))
    return special_var_cmp_mode[var]

def resolve_special_variable(kconfig, var):
    if var == '$kernel_version':
        return atk_kconfig.get_kernel_version(kconfig.srctree)
    elif var == '$arch':
        return atk_kconfig.get_arch()
    elif var == '$true':
        return 'y'
    elif var == '$false':
        return 'n'
    else:
        log.die("Unknown special variable '{}'".format(var))

def semver_to_int(ver):
    t = ver.split('-')[0].split('.')
    if len(t) < 3:
        t.extend([0] * (3 - len(t)))
    elif len(t) > 3:
        raise ValueError("Invalid semver '{}'".format(ver))

    return (int(t[0]) << 64) + (int(t[1]) << 32) + int(t[2])


def check_tristate(v, hint_at):
    if v not in ['n', 'm', 'y']:
        die_print_error_at(hint_at, "invalid argument '{}' is not a tristate ('n', 'm', 'y')".format(v))
    return v

_variable_parse_functors = {
    'string': str,
    'int': int,
    'hex': lambda x: int(x, 16),
    'tristate': check_tristate,
    'semver': semver_to_int,
}

def compare_op(op, lhs, rhs):
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

def compare_variables(resolved_vars, op, cmp_mode, hint_at):
    # Assert that the comparison mode is supported for the given type
    if cmp_mode == 'string':
        if op not in ['EXPR_CMP_NEQ', 'EXPR_CMP_EQ']:
            die_print_error_at(hint_at, "invalid comparison '{}' for type string".format(op))
    elif cmp_mode == 'tristate':
        if op not in ['EXPR_CMP_NEQ', 'EXPR_CMP_EQ']:
            die_print_error_at(hint_at, "invalid comparison operator '{}' for type tristate".format(op))

    # Parse variables to comparable types
    parse_functor = _variable_parse_functors[cmp_mode]
    parsed_variables = []
    for i, var in enumerate(resolved_vars, start=1):
        try:
            parsed_variables.append(parse_functor(var.value))
        except ValueError:
            die_print_error_at(var.at, "could not convert operand #{} ({}) to {}".format(i, var.value, cmp_mode))

    # Compare all variables in order
    for i, rhs in enumerate(parsed_variables[1:]):
        if not compare_op(op, parsed_variables[i - 1], rhs):
            return False
    return True

class NegatedConditionView():
    """
    A negated view on a condition to prevent recalculation
    """
    def __init__(self, condition):
        self.condition = condition

    @property
    def at(self):
        return self.condition.at

    def negate(self):
        return self.condition

    def evaluate(self, *args, **kwargs):
        return not self.condition.evaluate(*args, **kwargs)

class VarInfo:
    def __init__(self, var, value, special, is_sym, cmp_mode):
        self.var = var
        self.value = value
        self.special = special
        self.is_sym = is_sym
        self.cmp_mode =  cmp_mode

class Condition:
    def __init__(self, tree):
        self.at = (tree.meta, currently_parsed_filenames[-1]) if tree else None

    def get_sym(sym_name, kconfig, symbol_changes):
        try:
            sym = kconfig.syms[sym_name]
        except KeyError:
            die_print_error_at(self.at, "symbol {} does not exist".format(sym_name))

        # If the symbol hadn't been encountered before, pin the current value
        if sym not in symbol_changes:
            symbol_changes[sym] = (sym.str_value, self.at)

        return sym

    _sym_cmp_type = {
        kconfiglib.UNKNOWN:  'unknown',
        kconfiglib.BOOL:     'tristate',
        kconfiglib.TRISTATE: 'tristate',
        kconfiglib.STRING:   'string',
        kconfiglib.INT:      'int',
        kconfiglib.HEX:      'hex',
    }
    def resolve_var(var, kconfig, symbol_changes):
        # Remember if var were special variables
        var_special = var.startswith('$')

        # Resolve symbols
        var_is_sym = not var_quoted and not var_special and kernel_option_regex.match(var)
        if var_is_sym:
            value = self.get_sym(var).str_value
            var_cmp_mode = _sym_cmp_type.get(value.orig_type, 'unknown')
            if var_cmp_mode == 'unknown':
                die_print_error_at(self.at, "cannot compare with symbol {} which is of unknown type".format(value.name))
        elif var_special:
            value = resolve_special_variable(kconfig, var)
            var_cmp_mode = get_special_var_cmp_mode(var)
        else:
            value = var
            # Normal strings will always inherit the mode
            var_cmp_mode = None

        return VarInfo(var, value, var_special, var_is_sym, var_cmp_mode)

class CachedCondition(Condition):
    """
    Provides cached versions of negate() and evaluate(),
    a deriving class must only implement _evaluate.
    """
    def __init__(self, tree):
        super.__init__(tree)
        self.value = None

    def negate(self):
        return NegatedConditionView(self)

    def evaluate(self, kconfig, symbol_changes):
        if self.value is None:
            self.value = self._evaluate(kconfig, symbol_changes)
        return self.value

    def _evaluate(self, kconfig, symbol_changes):
        pass # Should be overwritten

class ConditionConstant(Condition):
    """
    A condition that has a constant truth value
    """
    def __init__(self, value):
        super().__init__(None)
        self.value = value

    def negate(self):
        return NegatedConditionView(self)

    def evaluate(self, kconfig, symbol_changes):
        return self.value

class ConditionAnd(CachedCondition):
    """
    A condition that is true if all of its terms are true.
    """
    def __init__(self, tree, *args):
        super().__init__(tree)
        self.terms = args

    def _evaluate(self, kconfig, symbol_changes):
        # all() provides early-out
        return all([t.evaluate(kconfig, symbol_changes) in self.terms])

class ConditionOr(CachedCondition):
    """
    A condition that is true if any of its terms is true.
    """
    def __init__(self, tree, *args):
        super().__init__(tree)
        self.terms = args

    def _evaluate(self, kconfig, symbol_changes):
        # any() provides early-out
        return any([t.evaluate(kconfig, symbol_changes) in self.terms])

class ConditionVarComparison(CachedCondition):
    """
    A condition that determines its truth value based on a n-ary comparison (n >= 2)
    """
    def __init__(self, tree, comparion_op, *args):
        super().__init__(tree)
        self.comparion_op = comparion_op
        self.vars = args

        if self.comparion_op not in ['EXPR_CMP_GE', 'EXPR_CMP_GEQ', 'EXPR_CMP_LE', 'EXPR_CMP_LEQ', 'EXPR_CMP_NEQ', 'EXPR_CMP_EQ']:
            raise ConfigParsingException(tree.meta, "Invalid comparison op '{}'. This is a bug that should be reported.".format(self.comparion_op))

    def _evaluate(self, kconfig, symbol_changes):
        resolved_vars = [self.resolve_var(v, kconfig, symbol_changes) for v in self.vars]

        # The comparison mode is determined by the following schema:
        # 1. Filter out None, as variables with mode None will inherit any other comparison type.
        # 2. All other variables force a comparison mode. It is an error to use two variables
        #    of different type in the same expression

        resolved_vars_with_type = [v for v in resolved_vars if v.cmp_mode is not None]
        if len(resolved_vars_with_type) == 0:
            cmp_mode = 'string' # compare with string mode as fallback (e.g. when two literals were given)
        elif len(resolved_vars_with_type) == 1:
            cmp_mode = resolved_vars_with_type[0].cmp_mode
        else:
            die_print_error_at(self.at, "cannot compare variables of different types: [{}]".format(', '.join(["{} ({})".format(v.var, v.cmp_mode) for v in resolved_vars_with_type])))

        return compare_variables(resolved_vars, self.comparion_op, cmp_mode, self.at)

Condition.true = ConditionConstant(True)
Condition.false = ConditionConstant(False)

def parse_expr_condition(tree):
    if tree.data == 'expr':
        return ConditionOr(*[parse_expr_condition(c) for c in tree.children if c.__class__ == lark.Tree and c.data == 'expr_term'])
    if tree.data == 'expr_term':
        return ConditionAnd(*[parse_expr_condition(c) for c in tree.children if c.__class__ == lark.Tree and c.data == 'expr_factor'])
    elif tree.data == 'expr_factor':
        negated = find_first_child(tree, 'expr_op_neg') is not None
        expr_cmp = find_first_child(tree, 'expr_cmp')
        if expr_cmp:
            operands = find_all_named_tokens_raw(expr_cmp, 'expr_param')
            operation = None
            # Find operation type and assert all operation types are equal
            for c in expr_cmp.children:
                if c.data == 'expr_op_cmp':
                    op = c.children[0].type
                    if operation is None:
                        operation = op
                    elif operation != op:
                        raise ConfigParsingException(expr_cmp.meta, "All expression operands must be the same for n-ary comparisons")
            return ConditionVarComparison(operation, operands).negate(negated)

        expr_id = find_first_child(tree, 'expr_id')
        if expr_id:
            # Implicit truth value is the same as writing 'SYM == "y"'
            return ConditionVarComparison('EXPR_CMP_EQ', [(str(expr_id.children[0]), False), ('y', True)]).negate(negated)

        expr = find_first_child(tree, 'expr')
        if expr:
            return parse_expr_condition(expr).negate(negated)

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
    return [parse_expr_condition(expr) for expr in find_subtrees(tree, name)]

def find_condition(tree, ignore_missing=True):
    conditions = find_conditions(tree)

    if len(conditions) == 0:
        if ignore_missing:
            return None
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

class Stmt:
    def __init__(self, tree, conditions):
        self.at = (tree.meta, currently_parsed_filenames[-1])
        self.conditions = conditions

class ConfigModule(BlockNode):
    node_name = 'module'

    class StmtUse(Stmt):
        def __init__(self, tree, conditions, module_name):
            super().__init__(tree, conditions)
            self.module_name = module_name
            self.module = None
    class StmtMerge(Stmt):
        def __init__(self, tree, conditions, filename):
            super().__init__(tree, conditions)
            self.filename = filename
    class StmtAssert(Stmt):
        def __init__(self, tree, conditions, assert_condition, message):
            super().__init__(tree, conditions)
            self.assert_condition = assert_condition
            self.message = message
    class StmtSet(Stmt):
        def __init__(self, tree, conditions, sym_name, value):
            super().__init__(tree, conditions)
            self.sym_name = sym_name
            self.value = value
    class StmtAddCmdline(Stmt):
        def __init__(self, tree, conditions, param):
            super().__init__(tree, conditions)
            self.param = param

    def __init__(self):
        self.name = None
        self.uses = []
        self.merge_kconf_files = []
        self.assertions = []
        self.assignments = []
        self.cmdline = []
        self.all_statements_in_order = []

    def parse_block_params(self, blck): # pylint: disable=arguments-differ
        def module_name(tree):
            self.name = find_token(tree, 'IDENTIFIER')

        apply_tree_nodes(blck.children, [module_name], ignore_additional=True)

    def parse_context(self, ctxt, preconditions=[Condition.true]): # pylint: disable=arguments-differ
        def stmt_module_if(tree):
            conditions = find_conditions(tree)
            subcontexts = find_subtrees(tree, 'ctxt_module')
            if len(subcontexts) - len(conditions) not in [0, 1]:
                raise ConfigParsingException(tree.meta, "invalid amount of subcontexts(={}) and conditions(={}) for if block; this is a bug that should be reported.".format(len(subcontexts), len(conditions)))

            not_previous_conditions = []
            for c, s in zip(conditions, subcontexts):
                # The condition for an else if block is the combined negation of all previous conditions,
                # and its own condition
                conds = preconditions + not_previous_conditions + [c]
                self.parse_context(s, preconditions=conds)
                not_previous_conditions.append(c.negate())

            if len(subcontexts) > len(conditions):
                # The condition for the else block is the combined negation of all previous conditions
                conds = preconditions + not_previous_conditions
                self.parse_context(subcontexts[-1], preconditions=conds)

        def _conds(tree):
            c = find_condition(tree)
            if c:
                return preconditions + [c]
            else:
                return preconditions
        def stmt_module_use(tree):
            conds = _conds(tree)
            new_uses = [ConfigModule.StmtUse(tree, conds, i) for i in find_all_tokens(tree, 'IDENTIFIER')]
            self.uses.extend(new_uses)
            self.all_statements_in_order.extend(new_uses)
        def stmt_module_merge(tree):
            stmt = ConfigModule.StmtMerge(tree, _conds(tree), find_named_token(tree, 'path'))
            self.merge_kconf_files.append(stmt)
            self.all_statements_in_order.append(stmt)
        def stmt_module_assert(tree):
            conditions = find_conditions(tree)
            assert_condition = conditions[0]
            stmt_conditions = preconditions + ([conditions[1]] if len(conditions) > 1 else [])
            message = find_named_token(tree, 'quoted_param', ignore_missing=True)
            stmt = ConfigModule.StmtAssert(tree, stmt_conditions, assert_condition, message)
            self.assertions.append(stmt)
            self.all_statements_in_order.append(stmt)
        def stmt_module_set(tree):
            key = find_token(tree, 'KERNEL_OPTION')
            value = find_named_token(tree, 'kernel_option_value', ignore_missing=True) or 'y'
            stmt = ConfigModule.StmtSet(tree, _conds(tree), key, value)
            self.assignments.append(stmt)
            self.all_statements_in_order.append(stmt)
        def stmt_module_add_cmdline(tree):
            conds = _conds(tree)
            new_params = [ConfigModule.StmtAddCmdline(tree, conds, i) for i in find_all_named_tokens(tree, 'quoted_param')]
            self.cmdline.extend(new_params)
            self.all_statements_in_order.extend(new_params)

        apply_tree_nodes(ctxt.children, [
                stmt_module_if,
                stmt_module_use,
                stmt_module_merge,
                stmt_module_assert,
                stmt_module_set,
                stmt_module_add_cmdline,
            ])

class ConfigKernel(BlockNode):
    node_name = 'kernel'

    def __init__(self):
        self.module = ConfigModule()

    def parse_context(self, ctxt):
        def ctxt_module(tree):
            self.module.parse_context(tree)

        apply_tree_nodes(ctxt.children, [
                ctxt_module,
            ])

class ConfigGenkernel(BlockNode):
    node_name = 'genkernel'

    def __init__(self):
        self.params = []

    def parse_context(self, ctxt):
        def stmt_genkernel_add_params(tree):
            self.params.extend(find_all_named_tokens(tree, 'quoted_param'))

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
            self.cmdline.extend(find_all_named_tokens(tree, 'quoted_param'))

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
                    die_print_parsing_exception(filename, e)
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

def load_config_tree(config_file):
    """
    Loads the autokernel configuration file and returns the parsed tree.
    """
    larkparser = get_lark_parser()
    with open(config_file, 'r') as f:
        try:
            return larkparser.parse(f.read())
        except (lark.exceptions.UnexpectedCharacters, lark.exceptions.UnexpectedToken) as e:
            print_message_with_file_location(config_file, msg_error(str(e).splitlines()[0]), e.line, (e.column, e.column))
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
        die_print_parsing_exception(config_file, e)

    def get_module(stmt):
        if stmt.module_name not in config.modules:
            die_print_error_at(stmt.at, "module '{}' is never defined".format(stmt.module_name))
        return config.modules[stmt.module_name]

    # Resolve module dependencies
    for m in config.modules:
        mod = config.modules[m]
        for u in mod.uses:
            u.module = get_module(u)

    # Resolve kernel dependencies
    kmod = config.kernel.module
    for u in kmod.uses:
        u.module = get_module(u)

    return config
