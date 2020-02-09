from . import log
from .constants import NO, MOD, YES

import kconfiglib
from kconfiglib import expr_value

import os


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


class Kconfig:
    """
    Wraps kconfiglib.Kconfig to expose a simplified interface as well
    as some convenience methods to the user. If any advanced features
    are required, the underlying kconfiglib.Kconfig object can be accessed
    via self.kconfig.

    kconfig:
      The underlying kconfiglib.Kconfig object
    """

    def __init__(self, dir):
        kconfig_file = os.path.join(dir, "Kconfig")
        if not os.path.isfile(kconfig_file):
            raise Exception("'{}' must point to a valid Kconfig file!".format(kconfig_file))

        log.info("Loading '{}'".format(kconfig_file))
        os.environ['srctree'] = dir
        self.kconfig = kconfiglib.Kconfig(kconfig_file, warn_to_stderr=False)

        for w in self.kconfig.warnings:
            for line in w.split('\n'):
                log.warn(line)

    def get_symbol(self, sym_name):
        """
        Resolves a symbol by name and returns the kconfiglib.Symbol object.
        """
        return self.kconfig.syms[sym_name]

    def all_no_config(self):
        """
        Resets the current configuration to the equivalent of calling
        `make allnoconfig` in the kernel source tree.
        """
        # TODO
        print("TODO all_no_config")
        pass

    def set_sym_with_deps(self, sym, target_value):
        """
        Sets the given symbol to target_value, while ensuring that
        all dependencies (and indirect dependencies) are satisfied.
        """
        def sym_is(sym, val):
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
        if sym_is(sym, target_value):
            return

        # If the direct dependencies are not satisfied yet,
        # try to satisfy them now.
        expr = sym.direct_dep
        if not expr_value(expr):
            self.satisfy_expr(expr, target_value)

            # Recheck symbol value after dependency evaluation
            if sym_is(sym, target_value):
                return

        # Finally set the desired value
        val = YES if sym.type == kconfiglib.BOOL and target_value == MOD else target_value
        print("{} = {}".format(sym.name, kconfiglib.TRI_TO_STR[val]))
        if not sym.set_value(val):
            raise Exception("Could set {} to {}".format(sym.name, kconfiglib.TRI_TO_STR[val]))

    def satisfy_expr(self, expr, target_value):
        """
        Parses the given expression and applies necessary changes to
        the current options to satisfy the expression.
        """
        if expr_value_bool(expr) == tri_to_bool(target_value):
            return

        if expr.__class__ is not tuple:
            # If the expression is a symbol, enable or disable it
            # based on the target value.
            self.set_sym_with_deps(expr, target_value)
        else:
            # If the expression is an operator, resolve the operator.
            if expr[0] is kconfiglib.AND:
                # TODO when in not OR and AND behave differently...
                self.satisfy_expr(expr[1], target_value)
                self.satisfy_expr(expr[2], target_value)
            elif expr[0] is kconfiglib.OR:
                # TODO which of these to satisfy?
                self.satisfy_expr(expr[1], target_value)
                self.satisfy_expr(expr[2], target_value)
            elif expr[0] is kconfiglib.NOT:
                self.satisfy_expr(expr[1], not target_value)

    def write_config(self, *args, **kwargs):
        """
        See kconfiglib.write_config.
        """
        self.kconfig.write_config(*args, **kwargs)
