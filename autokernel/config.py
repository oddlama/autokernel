import kconfiglib
import lark
import lark.exceptions
import os
import sys
from pathlib import Path

import autokernel.util as util
import autokernel.kconfig
import autokernel.symbol_tracking
from autokernel import log

currently_parsed_filenames = []

def def_at(tree):
    return (tree.meta, currently_parsed_filenames[-1]) if tree else None

_lark = None
def get_lark_parser():
    """
    Returns the lark parser for config files
    """
    global _lark # pylint: disable=global-statement
    if _lark is None:
        config_lark = util.read_resource('config.lark')
        _lark = lark.Lark(config_lark, propagate_positions=True, start='blck_root')

    return _lark

def die_redefinition(new_at, previous_at, name):
    log.print_error_at(new_at, "redefinition of {}".format(name))
    log.print_hint_at(previous_at, "previously defined here")
    sys.exit(1)

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
                log.die_print_error_at(def_at(n), "unprocessed rule '{}'; this is a bug that should be reported.".format(n.data))

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
            return util.decode_quotes(str(c)) if strip_quotes else str(c)

    if not ignore_missing:
        log.die_print_error_at(def_at(tree), "missing token '{}'".format(token_name))
    return None

class TokenRawInfo:
    def __init__(self, tree, value, is_quoted):
        self.at = def_at(tree)
        self.value = util.decode_quotes(value) if is_quoted else value
        self.was_quoted = is_quoted

class TokenRawLiteral:
    def __init__(self, at, value, is_quoted):
        self.at = at
        self.value = util.decode_quotes(value) if is_quoted else value
        self.was_quoted = is_quoted

def find_named_token_raw(tree, token_name, ignore_missing=False):
    """
    Finds a token by subrule name in the children of the given tree. Raises
    an exception if the token is not found.
    """
    for c in tree.children:
        if c.__class__ == lark.Tree and c.data == token_name:
            if len(c.children) != 1:
                log.die_print_error_at(def_at(c), "subrule token '{}' has too many children".format(token_name))

            if c.children[0].data not in ['string', 'string_quoted']:
                log.die_print_error_at(def_at(c), "subrule token '{}.{}' has an invalid name (must be either 'string' or 'string_quoted')".format(token_name, c.children[0].data))

            if c.children[0].__class__ != lark.Tree:
                log.die_print_error_at(def_at(c), "subrule token '{}.{}' has no children tree".format(token_name, c.children[0].data))

            if len(c.children[0].children) != 1:
                log.die_print_error_at(def_at(c.children[0]), "subrule token '{}.{}' has too many children".format(token_name, c.children[0].data))

            if c.children[0].children[0].__class__ != lark.Token:
                log.die_print_error_at(def_at(c.children[0]), "subrule token '{}.{}' has no children literal".format(token_name, c.children[0].data))

            return TokenRawInfo(c.children[0], str(c.children[0].children[0]), is_quoted=(c.children[0].data == 'string_quoted'))

    if not ignore_missing:
        log.die_print_error_at(def_at(tree), "missing token '{}'".format(token_name))
    return TokenRawInfo(None, None, False)

def find_named_token(tree, token_name, ignore_missing=False):
    """
    Finds a token by subrule name in the children of the given tree. Raises
    an exception if the token is not found. Strips quotes if it was a quoted string.
    """
    return find_named_token_raw(tree, token_name, ignore_missing=ignore_missing).value

def find_all_tokens(tree, token_name, strip_quotes=False):
    """
    Finds all tokens by name in the children of the given tree.
    """
    return [util.decode_quotes(str(c)) if strip_quotes else str(c) \
            for c in tree.children \
                if c.__class__ == lark.Token and c.type == token_name]

def find_all_named_tokens_raw(tree, token_name):
    """
    Finds all tokens by subrule name in the children of the given tree.
    returns tuple (str, tree_token, was_quoted)
    """
    return [TokenRawInfo(c.children[0], str(c.children[0].children[0]), is_quoted=(c.children[0].data == 'string_quoted')) \
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
    return [i.value for i in find_all_named_tokens_raw(tree, token_name)]

class UniqueProperty:
    """
    A property that tracks if it has been changed, stores a default
    value and raises an error if it is assigned more than once.
    """
    def __init__(self, name, default, convert_bool=False):
        self.at = None
        self.was_quoted = False
        self.name = name
        self.default = default
        self._value = None
        self.convert_bool = convert_bool

    @property
    def defined(self):
        return self._value is not None

    def parse(self, tree, token=None, named_token=None, ignore_missing=None):
        default_if_ignored = ignore_missing
        ignore_missing = default_if_ignored is not None

        if self.defined:
            die_redefinition(def_at(tree), self.at, self.name)

        if token:
            tok = find_token(tree, token, ignore_missing=ignore_missing)
            self.was_quoted = False
            self.at = def_at(tree)
        elif named_token:
            rawtok = find_named_token_raw(tree, named_token, ignore_missing=ignore_missing)
            tok = rawtok.value
            self.was_quoted = rawtok.was_quoted
            self.at = rawtok.at
        else:
            raise ValueError("Missing token identifier argument; this is a bug that should be reported.")

        if ignore_missing:
            tok = tok or default_if_ignored

        if self.convert_bool:
            self._value = util.parse_bool(self.at, tok)
        else:
            self._value = tok

    @property
    def value(self):
        return self.default if self._value is None else self._value

    @value.setter
    def value(self, v):
        self._value = v

    def __bool__(self):
        return bool(self.value)

    def __str__(self):
        return str(self.value)

class UniqueListProperty:
    """
    A list property that tracks if it has been changed, stores a default
    value and raises an error if it is assigned more than once.
    """
    def __init__(self, name, default):
        self.at = None
        self.name = name
        self.default = default
        self._value = None

    @property
    def defined(self):
        return self._value is not None

    def parse(self, tree, tokens_name):
        if self.defined:
            die_redefinition(def_at(tree), self.at, self.name)
        self.at = def_at(tree)
        self._value = find_all_named_tokens(tree, tokens_name)

    @property
    def value(self):
        return self.default if self._value is None else self._value

    @value.setter
    def value(self, v):
        self._value = v

    def __bool__(self):
        return bool(self.value)

def _parse_umask_property(prop):
    try:
        prop.value = int(prop.value, 8)
    except ValueError as e:
        log.die_print_error_at(prop.at, "Invalid value for umask: {}".format(str(e)))

def _parse_int_property(prop):
    try:
        prop.value = int(prop.value)
    except ValueError as e:
        log.die_print_error_at(prop.at, "Invalid value for integer: {}".format(str(e)))

special_var_cmp_mode = {
    '$kernel_version': 'semver',
    '$uname_arch': 'string',
    '$arch':  'string',
    '$false': 'tristate',
    '$true':  'tristate',
}

def get_special_var_cmp_mode(hint_at, var):
    if util.is_env_var(var):
        return 'string'
    if var in special_var_cmp_mode:
        return special_var_cmp_mode[var]
    log.die_print_error_at(hint_at, "unknown special variable '{}'".format(var))

def resolve_special_variable(hint_at, kconfig, var):
    if var == '$kernel_version':
        return autokernel.kconfig.get_kernel_version(kconfig.srctree)
    elif var == '$uname_arch':
        return autokernel.kconfig.get_uname_arch()
    elif var == '$arch':
        return autokernel.kconfig.get_arch()
    elif var == '$true':
        return 'y'
    elif var == '$false':
        return 'n'
    elif util.is_env_var(var):
        return util.resolve_env_variable(hint_at, var)
    else:
        log.die_print_error_at(hint_at, "unknown special variable '{}'".format(var))

def check_str(v):
    return v.value

def semver_to_int(v):
    t = v.split('-')[0].split('.')
    if len(t) < 3:
        t.extend(['0'] * (3 - len(t)))
    elif len(t) > 3:
        raise ValueError("invalid semver: too many tokens")

    return (int(t[0]) << 64) + (int(t[1]) << 32) + int(t[2])

def check_tristate(v):
    if v.value not in ['n', 'm', 'y']:
        raise ValueError("invalid argument: '{}' is not a tristate ('n', 'm', 'y')".format(v))
    return v.value

def check_int(v):
    return int(v.value)

def check_hex(v):
    if not v.is_sym and not v.value.startswith("0x"):
        raise ValueError("invalid argument: missing 0x prefix for hex variable")
    if v.value == '':
        return 0
    return int(v.value, 16)

_variable_parse_functors = {
    'string': check_str,
    'int': check_int,
    'hex': check_hex,
    'tristate': check_tristate,
    'semver': lambda v: semver_to_int(v.value),
}

_compare_op_to_str = {
    'EXPR_CMP_GE':  '>',
    'EXPR_CMP_GEQ': '>=',
    'EXPR_CMP_LE':  '<',
    'EXPR_CMP_LEQ': '<=',
    'EXPR_CMP_NEQ': '!=',
    'EXPR_CMP_EQ':  '==',
}

_compare_op_to_functor = {
    'EXPR_CMP_GE':  lambda a, b: a >  b,
    'EXPR_CMP_GEQ': lambda a, b: a >= b,
    'EXPR_CMP_LE':  lambda a, b: a <  b,
    'EXPR_CMP_LEQ': lambda a, b: a <= b,
    'EXPR_CMP_NEQ': lambda a, b: a != b,
    'EXPR_CMP_EQ':  lambda a, b: a == b,
}

def compare_variables(resolved_vars, op, cmp_mode, hint_at):
    # Assert that the comparison mode is supported for the given type
    if cmp_mode == 'string':
        if op not in ['EXPR_CMP_NEQ', 'EXPR_CMP_EQ']:
            log.die_print_error_at(hint_at, "invalid comparison '{}' for type string".format(_compare_op_to_str[op]))
    elif cmp_mode == 'tristate':
        if op not in ['EXPR_CMP_NEQ', 'EXPR_CMP_EQ']:
            log.die_print_error_at(hint_at, "invalid comparison operator '{}' for type tristate".format(_compare_op_to_str[op]))

    # Parse variables to comparable types
    parse_functor = _variable_parse_functors[cmp_mode]
    parsed_variables = []
    for i, var in enumerate(resolved_vars, start=1):
        try:
            parsed_variables.append(parse_functor(var))
        except ValueError as e:
            log.die_print_error_at(var.var.at, "could not convert operand #{} '{}' to {}: {}".format(i, var.var.value, cmp_mode, str(e)))

    # Compare all variables in order
    for i, rhs in enumerate(parsed_variables[1:], start=1):
        if not _compare_op_to_functor[op](parsed_variables[i - 1], rhs):
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

    def negate(self, do_negate=True):
        return self.condition if do_negate else self

    def evaluate(self, *args, **kwargs):
        return not self.condition.evaluate(*args, **kwargs)

    def __str__(self):
        return "not {}".format(self.condition)

class VarInfo:
    def __init__(self, var, value, special, is_sym, sym, cmp_mode):
        self.var = var
        self.value = value
        self.special = special
        self.is_sym = is_sym
        self.sym = sym
        self.cmp_mode =  cmp_mode

class Condition:
    def __init__(self, tree):
        self.at = def_at(tree)

    def get_sym(self, sym_name, kconfig):
        try:
            sym = kconfig.syms[sym_name]
        except KeyError:
            log.die_print_error_at(self.at, "symbol {} does not exist".format(sym_name))

        # If the symbol hadn't been encountered before, pin the current value
        if sym not in autokernel.symbol_tracking.symbol_changes:
            autokernel.symbol_tracking.symbol_changes[sym] = autokernel.symbol_tracking.SymbolChange(sym.str_value, self.at, 'used in condition')

        return sym

    _sym_cmp_type = {
        kconfiglib.UNKNOWN:  'unknown',
        kconfiglib.BOOL:     'tristate',
        kconfiglib.TRISTATE: 'tristate',
        kconfiglib.STRING:   'string',
        kconfiglib.INT:      'int',
        kconfiglib.HEX:      'hex',
    }

    def resolve_var(self, var, kconfig):
        # Remember if var was a special variable
        var_special = var.value.startswith('$')

        # Resolve symbols
        var_is_sym = (not var.was_quoted) and (not var_special) and (util.kernel_option_regex.match(var.value) is not None)
        sym = None
        if var_is_sym:
            if var.value.startswith('CONFIG_'):
                sym_name = var.value[len('CONFIG_'):]
            else:
                sym_name = var.value
            sym = self.get_sym(sym_name, kconfig)
            value = sym.str_value
            var_cmp_mode = Condition._sym_cmp_type.get(sym.orig_type, 'unknown')
            if var_cmp_mode == 'unknown':
                log.die_print_error_at(var.at, "cannot compare with symbol {} which is of unknown type".format(sym.name))
        elif var_special:
            value = resolve_special_variable(var.at, kconfig, var.value)
            var_cmp_mode = get_special_var_cmp_mode(var.at, var.value)
        else:
            value = var.value
            # Literal strings will always inherit the mode
            var_cmp_mode = None

        return VarInfo(var, value, var_special, var_is_sym, sym, var_cmp_mode)

class CachedCondition(Condition):
    """
    Provides cached versions of negate() and evaluate(),
    a deriving class must only implement _evaluate.
    """
    def __init__(self, tree):
        super().__init__(tree)
        self.value = None

    def negate(self, do_negate=True):
        return NegatedConditionView(self) if do_negate else self

    def evaluate(self, kconfig):
        if self.value is None:
            self.value = self._evaluate(kconfig) # pylint: disable=assignment-from-no-return
        return self.value

    def _evaluate(self, kconfig):
        # pylint: disable=unused-argument
        pass # Should be overwritten

class ConditionConstant(Condition):
    """
    A condition that has a constant truth value
    """
    def __init__(self, value):
        super().__init__(None)
        self.value = value

    def negate(self, do_negate=True):
        return NegatedConditionView(self) if do_negate else self

    def evaluate(self, kconfig):
        # pylint: disable=unused-argument
        return self.value

    def __str__(self):
        return "true" if self.value else "false"

class ConditionAnd(CachedCondition):
    """
    A condition that is true if all of its terms are true.
    """
    def __init__(self, tree, *args):
        super().__init__(tree)
        self.terms = args

    def _evaluate(self, kconfig):
        for t in self.terms:
            if not t.evaluate(kconfig):
                return False
        return True

    def __str__(self):
        return '(' + ' and '.join([str(t) for t in self.terms]) + ')'

class ConditionOr(CachedCondition):
    """
    A condition that is true if any of its terms is true.
    """
    def __init__(self, tree, *args):
        super().__init__(tree)
        self.terms = args

    def _evaluate(self, kconfig):
        for t in self.terms:
            if t.evaluate(kconfig):
                return True
        return False

    def __str__(self):
        return '(' + ' or '.join([str(t) for t in self.terms]) + ')'

class ConditionVarComparison(CachedCondition):
    """
    A condition that determines its truth value based on a n-ary comparison (n >= 2)
    """
    def __init__(self, tree, compare_op, operands):
        super().__init__(tree)
        self.compare_op = compare_op
        self.vars = operands

        if self.compare_op not in _compare_op_to_str:
            log.die_print_error_at(self.at, "Invalid comparison op '{}'. This is a bug that should be reported.".format(_compare_op_to_str[self.compare_op]))

    def _evaluate(self, kconfig):
        resolved_vars = [self.resolve_var(v, kconfig) for v in self.vars]

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
            log.die_print_error_at(self.at, "cannot compare variables of different types: [{}]".format(', '.join(["{} ({})".format(v.var.value, v.cmp_mode) for v in resolved_vars_with_type])))

        return compare_variables(resolved_vars, self.compare_op, cmp_mode, self.at)

    def __str__(self):
        op_str = ' {} '.format(_compare_op_to_str[self.compare_op])
        return '(' + op_str.join([v.value for v in self.vars]) + ')'

class ConditionVarTruth(CachedCondition):
    """
    A condition that determines its truth value based on implicit truth
    """
    def __init__(self, tree, operand):
        super().__init__(tree)
        self.var = operand

    def _evaluate(self, kconfig):
        resolved_var = self.resolve_var(self.var, kconfig)
        cmp_mode = resolved_var.cmp_mode

        if cmp_mode == 'tristate':
            implicit_var = self.resolve_var(TokenRawLiteral(self.var.at, '"n"', is_quoted=True), kconfig)
        elif cmp_mode == 'string' and (resolved_var.is_sym or (resolved_var.special and util.is_env_var(self.var.value))):
            implicit_var = self.resolve_var(TokenRawLiteral(self.var.at, '""', is_quoted=True), kconfig)
        else:
            log.die_print_error_at(self.at, "cannot implicitly convert '{}' to a truth value".format(self.var.value))

        return compare_variables([resolved_var, implicit_var], 'EXPR_CMP_NEQ', cmp_mode, self.at)

    def __str__(self):
        return self.var.value

Condition.true = ConditionConstant(True)
Condition.false = ConditionConstant(False)

def parse_expr_condition(tree):
    if tree.data == 'expr':
        return ConditionOr(tree, *[parse_expr_condition(c) for c in tree.children if c.__class__ == lark.Tree and c.data == 'expr_term'])
    if tree.data == 'expr_term':
        return ConditionAnd(tree, *[parse_expr_condition(c) for c in tree.children if c.__class__ == lark.Tree and c.data == 'expr_factor'])
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
                        log.die_print_error_at(def_at(expr_cmp), "all expression operands must be the same for n-ary comparisons")
            return ConditionVarComparison(expr_cmp, operation, operands).negate(negated)

        expr_id = find_named_token(tree, 'expr_id')
        if expr_id:
            # Implicit truth value is the same as writing 'var != "n"' for tristate symbols
            # and 'var != ""' for others.
            operand = TokenRawInfo(tree, str(expr_id), is_quoted=False)
            return ConditionVarTruth(tree, operand).negate(negated)

        expr = find_first_child(tree, 'expr')
        if expr:
            return parse_expr_condition(expr).negate(negated)

        log.die_print_error_at(def_at(tree), "invalid expression subtree '{}' in 'expr_factor'".format(tree.data))
    else:
        log.die_print_error_at(def_at(tree), "invalid expression subtree '{}'".format(tree.data))

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
            log.die_print_error_at(def_at(tree), "missing expression")

    if len(conditions) == 1:
        return conditions[0]

    log.die_print_error_at(def_at(tree), "expected exactly one expression, but got {}".format(len(conditions)))

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
        if self.first_definition is None:
            self.first_definition = def_at(tree)

        if tree.data != ('blck_' + self.node_name):
            log.die_print_error_at(def_at(tree), "{} cannot parse '{}'".format(self.__class__.__name__, tree.data))

        self.parse_block_params(tree, *args, **kwargs)

        ctxt = None
        for c in tree.children:
            if c.__class__ == lark.Tree:
                if c.data == 'ctxt_' + self.node_name:
                    if ctxt:
                        log.die_print_error_at(def_at(c), "'{}' must not have multiple children of type '{}'".format("blck_" + self.node_name, "ctxt_" + self.node_name))
                    ctxt = c

        if not ctxt:
            log.die_print_error_at(def_at(tree), "'{}' must have exactly one child '{}'".format("blck_" + self.node_name, "ctxt_" + self.node_name))

        self.parse_context(ctxt, *args, **kwargs)

class Stmt:
    def __init__(self, tree, conditions):
        self.at = def_at(tree)
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
        def __init__(self, tree, conditions, sym_name, value, has_try):
            super().__init__(tree, conditions)
            self.sym_name = sym_name
            self.value = value
            self.has_try = has_try
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

    def parse_context(self, ctxt, preconditions=None): # pylint: disable=arguments-differ
        if preconditions is None:
            preconditions = [Condition.true]
        def stmt_module_if(tree):
            conditions = find_conditions(tree)
            subcontexts = find_subtrees(tree, 'ctxt_module')
            if len(subcontexts) - len(conditions) not in [0, 1]:
                log.die_print_error_at(def_at(tree), "invalid amount of subcontexts(={}) and conditions(={}) for if block; this is a bug that should be reported.".format(len(subcontexts), len(conditions)))

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
            return preconditions + [c] if c else preconditions
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
            has_try = find_token(tree, 'TRY', ignore_missing=True) is not None
            key = find_token(tree, 'KERNEL_OPTION')
            value = find_named_token(tree, 'kernel_option_value', ignore_missing=True) or 'y'
            stmt = ConfigModule.StmtSet(tree, _conds(tree), key, value, has_try)
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

class ConfigInitramfs(BlockNode):
    node_name = 'initramfs'

    def __init__(self):
        self.build_command = UniqueListProperty('build_command', default=[])
        self.build_output = UniqueProperty('build_output', default=None)
        self.enabled = UniqueProperty('enabled', default=False, convert_bool=True)
        self.builtin = UniqueProperty('builtin', default=False, convert_bool=True)

    def parse_context(self, ctxt):
        def stmt_initramfs_enabled(tree):
            self.enabled.parse(tree, named_token='param')
        def stmt_initramfs_builtin(tree):
            self.builtin.parse(tree, named_token='param')
        def stmt_initramfs_build_command(tree):
            self.build_command.parse(tree, 'quoted_param')
        def stmt_initramfs_build_output(tree):
            self.build_output.parse(tree, named_token='path')

        apply_tree_nodes(ctxt.children, [
                stmt_initramfs_enabled,
                stmt_initramfs_builtin,
                stmt_initramfs_build_command,
                stmt_initramfs_build_output,
            ])

class ConfigHooks(BlockNode):
    node_name = 'hooks'

    def __init__(self):
        self.pre  = UniqueListProperty('pre',  default=[])
        self.post = UniqueListProperty('post', default=[])

    def parse_context(self, ctxt):
        def stmt_hooks_pre(tree):
            self.pre.parse(tree, 'quoted_param')
        def stmt_hooks_post(tree):
            self.post.parse(tree, 'quoted_param')

        apply_tree_nodes(ctxt.children, [
                stmt_hooks_pre,
                stmt_hooks_post,
            ])

class ConfigInstall(BlockNode):
    node_name = 'install'

    def __init__(self):
        self.hooks            = ConfigHooks()
        self.umask            = UniqueProperty('umask',            default=0o077)
        self.target_dir       = UniqueProperty('target_dir',       default='/boot')
        self.target_kernel    = UniqueProperty('target_kernel',    default="bzImage-{KERNEL_VERSION}")
        self.target_config    = UniqueProperty('target_config',    default="config-{KERNEL_VERSION}")
        self.target_initramfs = UniqueProperty('target_initramfs', default="initramfs-{KERNEL_VERSION}.cpio")
        self.modules_prefix   = UniqueProperty('modules_prefix',   default='/')
        self.mount            = []
        self.assert_mounted   = []
        self.keep_old         = UniqueProperty('keep_old', default=(-1))

    def parse_context(self, ctxt):
        def _parse_target(tree, target):
            target.parse(tree, named_token='path')
            # Parse disable
            if not target.was_quoted:
                target.value = util.parse_bool(target.at, target.value)
                if target.value is not False:
                    log.die_print_error_at(target.at, "You can only disable targets!")

        def blck_hooks(tree):
            self.hooks.parse_tree(tree)
        def stmt_install_umask(tree):
            self.umask.parse(tree, named_token='param')
            _parse_umask_property(self.umask)
        def stmt_install_target_dir(tree):
            self.target_dir.parse(tree, named_token='path')
        def stmt_install_target_kernel(tree):
            _parse_target(tree, self.target_kernel)
        def stmt_install_target_config(tree):
            _parse_target(tree, self.target_config)
        def stmt_install_target_initramfs(tree):
            _parse_target(tree, self.target_initramfs)
        def stmt_install_modules_prefix(tree):
            _parse_target(tree, self.modules_prefix)
        def stmt_install_mount(tree):
            self.mount.append(find_named_token(tree, 'path'))
        def stmt_install_assert_mounted(tree):
            self.assert_mounted.append(find_named_token(tree, 'path'))
        def stmt_install_keep_old(tree):
            self.keep_old.parse(tree, named_token='param')
            _parse_int_property(self.keep_old)

        apply_tree_nodes(ctxt.children, [
                blck_hooks,
                stmt_install_umask,
                stmt_install_target_dir,
                stmt_install_target_kernel,
                stmt_install_target_config,
                stmt_install_target_initramfs,
                stmt_install_modules_prefix,
                stmt_install_mount,
                stmt_install_assert_mounted,
                stmt_install_keep_old,
            ])

class ConfigBuild(BlockNode):
    node_name = 'build'

    def __init__(self):
        self.hooks = ConfigHooks()
        self.umask = UniqueProperty('umask', default=0o077)

    def parse_context(self, ctxt):
        def blck_hooks(tree):
            self.hooks.parse_tree(tree)
        def stmt_build_umask(tree):
            self.umask.parse(tree, named_token='param')
            _parse_umask_property(self.umask)

        apply_tree_nodes(ctxt.children, [
                blck_hooks,
                stmt_build_umask,
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
                    log.die_print_error_at(def_at(tree), str(e))

                currently_parsed_filenames.append(filename)
                self.parse_tree(subtree, restrict_to_modules=True)
                currently_parsed_filenames.pop()
            else:
                log.die_print_error_at(def_at(tree), "'{}' does not exist or is not a file".format(filename))

        def blck_module(tree):
            module = ConfigModule()
            module.parse_tree(tree)
            if module.name in self.modules:
                die_redefinition(def_at(tree), self.modules[module.name].first_definition, "module '{}'".format(module.name))
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
                    if filename.endswith('.conf'):
                        _include_module_file(tree, os.path.join(include_dir, filename))
            else:
                log.die_print_error_at(def_at(tree), "'{}' is not a directory".format(include_dir))
        def stmt_root_include_module(tree):
            filename = os.path.join(os.path.dirname(currently_parsed_filenames[-1]), find_named_token(tree, 'path'))
            if not filename.endswith('.conf'):
                log.print_warn_at(def_at(tree), "module files should always end in .conf")
            _include_module_file(tree, filename)

        if restrict_to_modules:
            def other(tree):
                log.die_print_error_at(def_at(tree), "'{}' must not be used in a module config".format(tree.data))

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
            log.print_message_with_file_location(config_file, log.msg_error(str(e).splitlines()[0]), e.line, (e.column, e.column))
            sys.exit(1)

def config_file_path(config_file, warn=False):
    if config_file:
        return Path(config_file)

    config_file = Path('/etc/autokernel/autokernel.conf')
    if not config_file.exists():
        if warn:
            log.warn("Configuration file '/etc/autokernel/autokernel.conf' not found")
            log.warn("You may want to run `autokernel setup` to install a default config.")
            log.warn("Falling back to a minimal internal configuration!")
        config_file = util.resource_path('internal.conf')

    return config_file

def load_config(config_file):
    """
    Loads the autokernel configuration file.
    """
    with config_file_path(config_file) as config_file:
        config_file = str(config_file)
        tree = load_config_tree(config_file)
        config = Config()

        currently_parsed_filenames.append(config_file)
        config.parse_tree(tree)
        currently_parsed_filenames.pop()

        def get_module(stmt):
            if stmt.module_name not in config.modules:
                log.die_print_error_at(stmt.at, "module '{}' is never defined".format(stmt.module_name))
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

        # Assert that build_command and build_output are set if initramfs is enabled.
        if config.initramfs.enabled:
            if len(config.initramfs.build_command.value) == 0:
                log.die("config: initramfs is enabled, but initramfs.build_command has not been defined!")
            if not config.initramfs.build_output and not any(['{INITRAMFS_OUTPUT}' in a for a in config.initramfs.build_command.value]):
                log.die("config: initramfs is enabled, and neither {INITRAMFS_OUTPUT} was used in the build_command, nor initramfs.build_output has been defined!")

        if config.install.target_dir.value[0] != '/':
            log.die("config: install.target_dir must be an absolute path!")
        if config.install.modules_prefix.value and config.install.modules_prefix.value[0] != '/':
            log.die("config: install.modules_prefix must be an absolute path!")

        return config
