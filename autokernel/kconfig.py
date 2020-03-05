from . import log
from .constants import NO, MOD, YES

import subprocess
import os
import kconfiglib
from kconfiglib import expr_value

from sympy import pretty, Symbol, true, false, Or, And, Not
from sympy.logic.boolalg import to_cnf, simplify_logic


def tri_to_bool(tri):
    """
    Converts a tristate to a boolean value (['n'] -> False, ['m', 'y'] -> True)
    """
    return tri != NO

def expr_value_bool(expr):
    """
    Evaluates the given expression using expr_value(expr) and converts
    the result to a boolean value using tri_to_bool().
    """
    return tri_to_bool(expr_value(expr))

def print_expr_tree(expr, recursive=True, indent=0, chaining_op=None):
    """
    Prints a color coded tree of the given expression.
    Intended for debugging purposes only.
    """
    def print_node(name, indent, satisfied):
        if satisfied:
            print("[32m" + "  " * indent + name + "[m")
        else:
            print("[31m" + "  " * indent + name + "[m")

    if expr.__class__ is not tuple:
        if not recursive or (expr.__class__ is kconfiglib.Symbol and expr.is_constant):
            print_node(expr.name, indent, tri_to_bool(expr.tri_value))
        else:
            # Recurse into dependencies of the symbol, if dependencies are not a constant
            print_node(expr.name, indent, tri_to_bool(expr.tri_value))
            if not (expr.direct_dep.__class__ is  kconfiglib.Symbol and expr.direct_dep.is_constant):
                print_expr_tree(expr.direct_dep, recursive, indent + 1)
    else:
        if expr[0] is kconfiglib.AND:
            if chaining_op is not kconfiglib.AND:
                print_node("AND", indent, expr_value_bool(expr))
                indent += 1
            print_expr_tree(expr[1], recursive, indent, chaining_op=kconfiglib.AND)
            print_expr_tree(expr[2], recursive, indent, chaining_op=kconfiglib.AND)
        elif expr[0] is kconfiglib.OR:
            if chaining_op is not kconfiglib.OR:
                print_node("OR", indent, expr_value_bool(expr))
                indent += 1
            print_expr_tree(expr[1], recursive, indent, chaining_op=kconfiglib.OR)
            print_expr_tree(expr[2], recursive, indent, chaining_op=kconfiglib.OR)
        elif expr[0] is kconfiglib.NOT:
            print_node("NOT", indent, expr_value_bool(expr))
            print_expr_tree(expr[1], recursive, indent + 1, chaining_op=kconfiglib.NOT)

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

    os.environ["KERNELVERSION"] = subprocess.run(['make', 'kernelversion'], cwd=dir, stdout=subprocess.PIPE).stdout.decode().strip().splitlines()[0]
    os.environ["CC_VERSION_TEXT"] = subprocess.run(['gcc', '--version'], stdout=subprocess.PIPE).stdout.decode().strip().splitlines()[0]

def load_kconfig(kernel_dir):
    kconfig_file = os.path.join(kernel_dir, "Kconfig")
    if not os.path.isfile(kconfig_file):
        raise Exception("'{}' must point to a valid Kconfig file!".format(kconfig_file))

    load_environment_variables(dir=kernel_dir)

    log.info("Loading '{}'".format(kconfig_file))
    os.environ['srctree'] = kernel_dir
    kconfig = kconfiglib.Kconfig(kconfig_file, warn_to_stderr=False)

    for w in kconfig.warnings:
        for line in w.split('\n'):
            log.verbose(line)

    allnoconfig(kconfig)
    return kconfig

def allnoconfig(kconfig):
    """
    Resets the current configuration to the equivalent of calling
    `make allnoconfig` in the kernel source tree.
    """

    log.info("Loading allnoconfig")

    # Allnoconfig from kconfiglib/allnoconfig.py
    warn_save = kconfig.warn
    kconfig.warn = False
    for sym in kconfig.unique_defined_syms:
        sym.set_value(YES if sym.is_allnoconfig_y else NO)
    kconfig.warn = warn_save
    kconfig.load_allconfig("allno.config")

def set_sym_with_deps(sym, target_value):
    """
    Sets the given symbol to target_value, while ensuring that
    all dependencies (and indirect dependencies) are satisfied.
    """
    def sym_has_value(sym, val):
        if sym.type == kconfiglib.BOOL:
            if tri_to_bool(sym.tri_value) == tri_to_bool(val):
                return True
        else:
            if sym.tri_value == val:
                return True
        return False

    if sym.type not in [kconfiglib.BOOL, kconfiglib.TRISTATE]:
        raise Exception("cannot enable symbol of type '{}'".format(sym.type))

    # Check if symbol already has target value
    if sym_has_value(sym, target_value):
        return

    # If the direct dependencies are not satisfied yet,
    # try to satisfy them now.
    expr = sym.direct_dep
    if not expr_value(expr):
        satisfy_expr(expr, target_value)

        # Recheck symbol value after dependency evaluation
        if sym_has_value(sym, target_value):
            return

    # Finally set the desired value
    val = YES if sym.type == kconfiglib.BOOL and target_value == MOD else target_value
    print("{} = {}".format(sym.name, kconfiglib.TRI_TO_STR[val]))
    if not sym.set_value(val):
        raise Exception("Could set {} to {}".format(sym.name, kconfiglib.TRI_TO_STR[val]))

def satisfy_expr(expr, target_value):
    """
    Parses the given expression and applies necessary changes to
    the current options to satisfy the expression.
    """
    if expr_value_bool(expr) == tri_to_bool(target_value):
        return

    if expr.__class__ is not tuple:
        # If the expression is a symbol, enable or disable it
        # based on the target value.
        set_sym_with_deps(expr, target_value)
    else:
        # If the expression is an operator, resolve the operator.
        if expr[0] is kconfiglib.AND:
            # TODO when in not OR and AND behave differently...
            satisfy_expr(expr[1], target_value)
            satisfy_expr(expr[2], target_value)
        elif expr[0] is kconfiglib.OR:
            # TODO which of these to satisfy?
            satisfy_expr(expr[1], target_value)
            satisfy_expr(expr[2], target_value)
        elif expr[0] is kconfiglib.NOT:
            satisfy_expr(expr[1], not target_value)

class ExprCompare:
    def __init__(self, cmp_type, lhs, rhs):
        self.cmp_type = cmp_type
        self.lhs = lhs
        self.rhs = rhs

def parse_expr(expr):
    """
    Parses the given expression and converts it into a sympy expression.
    """
    symbols = []
    # TODO return these ..... also make recursive....

    def add_symbol(sym):
        i = len(symbols)
        symbols.append(sym)
        return "x" + str(i)

    if expr.__class__ is not tuple:
        if expr.__class__ is kconfiglib.Symbol and expr.is_constant:
            return true if tri_to_bool(expr) else false
        else:
            return And(add_symbol(expr), parse_expr(expr.direct_dep))
    else:
        # If the expression is an operator, resolve the operator.
        if expr[0] is kconfiglib.AND:
            return And(parse_expr(expr[1]), parse_expr(expr[2]))
        elif expr[0] is kconfiglib.OR:
            return Or(parse_expr(expr[1]), parse_expr(expr[2]))
        elif expr[0] is kconfiglib.NOT:
            return Not(parse_expr(expr[1]))
        elif expr[0] in [kconfiglib.EQUAL, kconfiglib.UNEQUAL, kconfiglib.LESS, kconfiglib.LESS_EQUAL, kconfiglib.GREATER, kconfiglib.GREATER_EQUAL]:
            if expr[1].__class__ is tuple or expr[2].__class__ is tuple:
                raise Exception("Cannot compare expressions")
            return ExprCompare(expr[0], expr[1], expr[2])
        else:
            raise Exception("Unknown expression type: '{}'".format(expr[0]))

def required_deps(sym):
    expr = parse_expr(sym.direct_dep)
    expr = to_cnf(expr)
    expr = simplify_logic(expr, form='cnf')
    #expr = simplify_expr(parse_expr(kconfig.syms[o].direct_dep))
    print(pretty(expr))
