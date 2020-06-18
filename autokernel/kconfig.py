from . import log

import subprocess
import os
import re
import kconfiglib

import sympy
from sympy.logic import simplify_logic
from sympy.logic.inference import satisfiable


def symbol_can_be_user_assigned(sym):
    for node in sym.nodes:
        if node.prompt:
            return True

    return False

value_to_str_color = {
    'n': "[1;31m",
    'm': "[1;33m",
    'y': "[1;32m",
}
def value_to_str(value):
    if value in kconfiglib.STR_TO_TRI:
        return '[{}{}{}]'.format(log.color(value_to_str_color[value]), value, log.color_reset)
    else:
        return "'{}'".format(value)


def tri_to_bool(tri):
    """
    Converts a tristate to a boolean value (['n'] → False, ['m', 'y'] → True)
    """
    return tri != kconfiglib.STR_TO_TRI['n']

def expr_value_bool(expr):
    """
    Evaluates the given expression using kconfiglib.expr_value(expr) and converts
    the result to a boolean value using tri_to_bool().
    """
    return tri_to_bool(kconfiglib.expr_value(expr))

def set_env_default(var, default_value):
    """
    Sets an environment variable to the given default_value if it is currently unset.
    """
    if var not in os.environ:
        os.environ[var] = default_value

def detect_uname_arch():
    return subprocess.run(['uname', '-m'], check=True, stdout=subprocess.PIPE).stdout.decode().strip().splitlines()[0]

def detect_arch():
    arch = get_uname_arch()
    arch = re.sub('i.86',      'x86',     arch)
    arch = re.sub('x86_64',    'x86',     arch)
    arch = re.sub('sun4u',     'sparc64', arch)
    arch = re.sub('arm.*',     'arm',     arch)
    arch = re.sub('sa110',     'arm',     arch)
    arch = re.sub('s390x',     's390',    arch)
    arch = re.sub('parisc64',  'parisc',  arch)
    arch = re.sub('ppc.*',     'powerpc', arch)
    arch = re.sub('mips.*',    'mips',    arch)
    arch = re.sub('sh[234].*', 'sh',      arch)
    arch = re.sub('aarch64.*', 'arm64',   arch)
    arch = re.sub('riscv.*',   'riscv',   arch)
    return arch

def initialize_environment():
    """
    Initializes important environment variables, if not set by the user.
    like
    """
    set_env_default("CC", "gcc")
    set_env_default("LD", "ldd")
    set_env_default("HOSTCC", "gcc")
    set_env_default("HOSTCXX", "g++")

    if "CC_VERSION_TEXT" not in os.environ:
        os.environ["CC_VERSION_TEXT"] = subprocess.run([os.environ['CC'], '--version'], check=True, stdout=subprocess.PIPE).stdout.decode().strip().splitlines()[0]

_arch = None
def get_arch():
    """
    Returns arch of the current host as the kernel would interpret it
    """
    global _arch # pylint: disable=global-statement
    if not _arch:
        _arch = detect_arch()
    return _arch


_uname_arch = None
def get_uname_arch():
    """
    Returns arch of the current host as the kernel would interpret it
    """
    global _uname_arch # pylint: disable=global-statement
    if not _uname_arch:
        _uname_arch = detect_uname_arch()
    return _uname_arch

_kernel_version = {}
def get_kernel_version(kernel_dir):
    """
    Returns the kernel version for the given kernel_dir.
    """
    kernel_dir_canon = os.path.realpath(kernel_dir)
    if kernel_dir_canon in _kernel_version:
        return _kernel_version[kernel_dir_canon]

    _kernel_version[kernel_dir_canon] = subprocess.run(['make', 'kernelversion'], cwd=kernel_dir_canon, check=True, stdout=subprocess.PIPE).stdout.decode().strip().splitlines()[0]
    return _kernel_version[kernel_dir_canon]

def load_kconfig(kernel_dir):
    kconfig_file = os.path.join(kernel_dir, "Kconfig")
    if not os.path.isfile(kconfig_file):
        raise ValueError("'{}' must point to a valid Kconfig file!".format(kconfig_file))

    kver = get_kernel_version(kernel_dir)
    log.info("Loading '{}' (version {})".format(kconfig_file, kver))
    os.environ['srctree'] = kernel_dir
    os.environ["ARCH"] = os.environ["SRCARCH"] = get_arch()
    os.environ["KERNELVERSION"] = kver
    kconfig = kconfiglib.Kconfig(os.path.realpath(kconfig_file), warn_to_stderr=False)

    for w in kconfig.warnings:
        for line in w.split('\n'):
            log.verbose(line)

    return kconfig

def allnoconfig(kconfig):
    """
    Resets the current configuration to the equivalent of calling
    `make allnoconfig` in the kernel source tree.
    """

    log.info("Applying allnoconfig")

    # Allnoconfig from kconfiglib/allnoconfig.py
    warn_save = kconfig.warn
    kconfig.warn = False
    for sym in kconfig.unique_defined_syms:
        sym.set_value('y' if sym.is_allnoconfig_y else 'n')
    kconfig.warn = warn_save
    kconfig.load_allconfig("allno.config")

class ExprSymbol:
    def __init__(self, sym):
        self.sym = sym

    def is_satisfied(self):
        return tri_to_bool(self.sym.tri_value)

class ExprCompare:
    def __init__(self, cmp_type, lhs, rhs):
        self.cmp_type = cmp_type
        self.lhs = lhs
        self.rhs = rhs

    def is_satisfied(self):
        if self.cmp_type == kconfiglib.EQUAL:
            return self.lhs == self.rhs
        elif self.cmp_type == kconfiglib.UNEQUAL:
            return self.lhs != self.rhs
        elif self.cmp_type == kconfiglib.LESS:
            return self.lhs < self.rhs
        elif self.cmp_type == kconfiglib.LESS_EQUAL:
            return self.lhs <= self.rhs
        elif self.cmp_type == kconfiglib.GREATER:
            return self.lhs > self.rhs
        elif self.cmp_type == kconfiglib.GREATER_EQUAL:
            return self.lhs >= self.rhs

    def __str__(self):
        return "{} {} {}".format(self.lhs.name, kconfiglib.REL_TO_STR[self.cmp_type], self.rhs.name)

class ExprIgnore:
    def is_satisfied(self):
        return False

class Expr:
    def __init__(self, sym):
        self.sym = sym
        self.symbols = []
        self.expr_ignore_sym = None
        self.expr = self._parse(sym.direct_dep)

    def _add_symbol_if_nontrivial(self, sym, trivialize=True):
        if sym.__class__ is ExprSymbol and not symbol_can_be_user_assigned(sym.sym):
            return sympy.true if kconfiglib.expr_value(sym.sym) else sympy.false

        # If the symbol is aleady satisfied in the current config,
        # skip it.
        if trivialize and sym.is_satisfied():
            return sympy.true

        # Return existing symbol if possible
        for s, sympy_s in self.symbols:
            if s.__class__ is sym.__class__ is ExprSymbol:
                if s.sym == sym.sym:
                    return sympy_s

        # Create new symbol
        i = len(self.symbols)
        s = sympy.Symbol(str(i))
        self.symbols.append((sym, s))
        return s

    def _parse(self, expr, trivialize=True):
        def add_sym(expr, trivialize=trivialize):
            return self._add_symbol_if_nontrivial(ExprSymbol(expr), trivialize)

        if expr.__class__ is not tuple:
            if expr.__class__ is kconfiglib.Symbol:
                if expr.is_constant:
                    return sympy.true if tri_to_bool(expr) else sympy.false
                elif expr.type in [kconfiglib.BOOL, kconfiglib.TRISTATE]:
                    return add_sym(expr)
                else:
                    # Ignore unknown symbol types
                    return self.expr_ignore()
            elif expr.__class__ is kconfiglib.Choice:
                return self.expr_ignore()
            else:
                raise ValueError("Unexpected expression type '{}'".format(expr.__class__.__name__))
        else:
            # If the expression is an operator, resolve the operator.
            if expr[0] is kconfiglib.AND:
                return sympy.And(self._parse(expr[1]), self._parse(expr[2]))
            elif expr[0] is kconfiglib.OR:
                return sympy.Or(self._parse(expr[1]), self._parse(expr[2]))
            elif expr[0] is kconfiglib.NOT:
                return sympy.Not(self._parse(expr[1], trivialize=False))
            elif expr[0] is kconfiglib.EQUAL and expr[2].is_constant:
                if tri_to_bool(expr[2]):
                    return add_sym(expr[1], trivialize=False)
                else:
                    return sympy.Not(ExprSymbol(expr[1]))
            elif expr[0] in [kconfiglib.UNEQUAL, kconfiglib.LESS, kconfiglib.LESS_EQUAL, kconfiglib.GREATER, kconfiglib.GREATER_EQUAL]:
                if expr[1].__class__ is tuple or expr[2].__class__ is tuple:
                    raise ValueError("Cannot compare expressions")
                return self._add_symbol_if_nontrivial(ExprCompare(expr[0], expr[1], expr[2]), trivialize)
            else:
                raise ValueError("Unknown expression type: '{}'".format(expr[0]))

    def expr_ignore(self):
        if not self.expr_ignore_sym:
            self.expr_ignore_sym = self._add_symbol_if_nontrivial(ExprIgnore())
        return self.expr_ignore_sym

    def simplify(self):
        self.expr = simplify_logic(self.expr)

    def unsatisfied_deps(self):
        configuration = satisfiable(self.expr)
        if not configuration:
            return False

        # If configuration is 'True', return none.
        if configuration.get(True, False):
            return []

        deps = []
        for k in configuration:
            idx = int(k.name)
            deps.append((idx, self.symbols[idx][0], configuration[k]))

        deps.sort(key=lambda x: x[0], reverse=True)
        return deps

def required_deps(sym):
    expr = Expr(sym)
    expr.simplify()

    deps = []
    unsat_deps = expr.unsatisfied_deps()
    if unsat_deps is False:
        return False

    for _, s, v in unsat_deps:
        if s.__class__ is ExprIgnore:
            pass
        elif s.__class__ is ExprSymbol:
            deps.append((s.sym, v))
        else:
            raise ValueError("Cannot automatically satisfy inequality: '{}'".format(s))
    return deps
