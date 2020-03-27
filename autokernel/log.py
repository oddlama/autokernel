import sys

_verbose = False
_quiet = False
_use_color = True

color_reset = ""

_fmt_verbose = ""
_fmt_info    = ""
_fmt_warn    = ""
_fmt_error   = ""

def use_color():
    return _use_color

def set_use_color(new_use_color):
    global _use_color # pylint: disable=global-statement
    _use_color = new_use_color
    _invalidate_format_strings()

def set_verbose(new_verbose):
    global _verbose # pylint: disable=global-statement
    _verbose = new_verbose
    _invalidate_format_strings()

def set_quiet(quiet):
    global _quiet # pylint: disable=global-statement
    _quiet = quiet
    _invalidate_format_strings()

def color(c, alternative=""):
    if _use_color:
        return c
    return alternative
""

def _print_verbose_color(msg):
    print(_fmt_verbose.format(msg.replace("[m", "[m[2m")))

def _print_verbose(msg):
    print(_fmt_verbose.format(msg))

def _print_info(msg):
    print(_fmt_info.format(msg))

def _print_warn(msg):
    print(_fmt_warn.format(msg))

def _print_error(msg):
    print(_fmt_error.format(msg), file=sys.stderr)

def _noop(msg): # pylint: disable=unused-argument
    pass

verbose = _noop
info    = _noop
warn    = _noop
error   = _noop

def die(message):
    error(message)
    sys.exit(1)

def _invalidate_format_strings():
    # pylint: disable=global-statement
    global color_reset
    global _fmt_verbose
    global _fmt_info
    global _fmt_warn
    global _fmt_error

    # Recalculate format strings
    color_reset = color("[m")
    _fmt_verbose = " *" + color("[2;37m", " V:") + " {}" + color_reset
    _fmt_info = color("[1;32m *[m", " * I:") + " {}"
    _fmt_warn = color("[1;33m *[m", " * W:") + " {}"
    _fmt_error = color("[1;31m * ERROR:[m", " * ERROR:") + " {}"

    # Set function dispatchers
    global verbose
    global info
    global warn
    global error
    verbose = _noop
    info    = _noop
    warn    = _noop

    if not _quiet:
        if _verbose:
            verbose = _print_verbose_color if _use_color else _print_verbose
        info    = _print_info
        warn    = _print_warn
    error = _print_error

_invalidate_format_strings()
