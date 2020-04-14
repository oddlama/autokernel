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

def _print_verbose_color(msg):
    print(_fmt_verbose.format(msg.replace("[m", "[m[2m")))

def _print_verbose(msg):
    print(_fmt_verbose.format(msg))

def _print_info(msg):
    print(_fmt_info.format(msg))

def _print_warn(msg):
    print(_fmt_warn.format(msg), file=sys.stderr)

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


def print_line_with_highlight(line, line_nr, highlight):
    tabs_before = line[:highlight[0]-1].count('\t')
    tabs_in_highlight = line[highlight[0]-1:highlight[1]-2].count('\t')
    print("{:5d} | {}".format(line_nr, line[:-1].replace('\t', '    ')))
    print("      | {}".format(" " * ((highlight[0] - 1) + tabs_before * 3) + color("[1;34m") + "^" + "~" * ((highlight[1] - highlight[0] - 1) + tabs_in_highlight * 3) + color_reset))

def msg_hint(msg):
    return color("[1;34m") + "hint:" + color_reset + " " + msg

def msg_warn(msg):
    return color("[1;33m") + "warning:" + color_reset + " " + msg

def msg_error(msg):
    return color("[1;31m") + "error:" + color_reset + " " + msg

def print_message_with_file_location(file, message, line, column_range):
    print((color("[1m") + "{}:{}:{}:" + color_reset + " {}").format(
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
        print(msg + ' [location untracked]', file=sys.stderr)

def print_hint_at(definition, msg):
    print_message_at(definition, msg_hint(msg))

def print_warn_at(definition, msg):
    print_message_at(definition, msg_warn(msg))

def print_error_at(definition, msg):
    print_message_at(definition, msg_error(msg))

def die_print_error_at(definition, msg):
    print_error_at(definition, msg)
    sys.exit(1)
