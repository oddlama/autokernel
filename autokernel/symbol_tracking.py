import sys
import kconfiglib

import autokernel.kconfig
from autokernel import log


# Monkeypatch Symbol.set_value, and Symbol._invalidate to detect conflicting changes.
# Detection is only done when using the set_value_detect_conflicts instead of Symbol.set_value

class SymbolChange:
    def __init__(self, value, at, reason):
        self.value = value
        self.at = at
        self.reason = reason

symbol_change_hint_at = None
# Map symbol → (value, hint_at)
symbol_changes = {}
symbols_invalidated = {}

saved_set_value = kconfiglib.Symbol.set_value
saved_invalidate = kconfiglib.Symbol._invalidate # pylint: disable=protected-access

def register_symbol_change(symbol, new_value, inducing_change, reason='explicitly set'):
    if symbol == inducing_change[0]:
        log.verbose("{} {}".format(autokernel.kconfig.value_to_str(new_value), symbol.name))
        symbol_changes[symbol] = SymbolChange(new_value, symbol_change_hint_at, reason)
    else:
        log.verbose("{} {} (implicitly triggered by {} = {})".format(
            autokernel.kconfig.value_to_str(new_value),
            symbol.name, inducing_change[0].name, inducing_change[1]))

def track_symbol_changes(symbol, new_value, inducing_change):
    # Both normal and implicit changes can trigger conflicts
    if symbol in symbol_changes and symbol_changes[symbol].value != new_value:
        sc = symbol_changes[symbol]
        autokernel.config.print_error_at(symbol_change_hint_at, "conflicting {}: {} {}".format(
            "change" if symbol == inducing_change[0] else "implicit change",
            autokernel.kconfig.value_to_str(new_value),
            symbol.name))
        autokernel.config.print_hint_at(sc.at, "previously pinned to {} here (reason: {})".format(
            autokernel.kconfig.value_to_str(sc.value), sc.reason))
        sys.exit(1)

    # Implicit changes will not be recorded by register_symbol_change, but
    # they can trigger conflicting changes above.
    # This prevents them from changing an option that was previously set by the user.
    register_symbol_change(symbol, new_value, inducing_change)

def set_value_proxy_detect_conflicts(sym, value):
    # Additional logic only if called through wrapper
    if not symbol_change_hint_at:
        return saved_set_value(sym, value)

    symbols_invalidated.clear()
    ret = saved_set_value(sym, value)

    # Process invalidated symbols and check for conflicting changes.
    track_symbol_changes(sym, value, (sym, value))
    for s in symbols_invalidated:
        # Skip self-invalidation
        if s == sym:
            continue

        # We will only track implicit changes if they changed the value.
        if symbols_invalidated[s] == s.str_value:
            continue

        track_symbol_changes(s, s.str_value, (sym, value))

    return ret

def monkey_invalidate(sym):
    # Remember old value
    symbols_invalidated[sym] = sym.str_value
    return saved_invalidate(sym)

kconfiglib.Symbol.set_value = set_value_proxy_detect_conflicts
kconfiglib.Symbol._invalidate = monkey_invalidate # pylint: disable=protected-access

def set_value_detect_conflicts(sym, value, hint_at):
    # Remember which symbol caused a chain of changes
    global symbol_change_hint_at # pylint: disable=global-statement
    symbol_change_hint_at = hint_at
    ret = sym.set_value(value)
    symbol_change_hint_at = None
    return ret
