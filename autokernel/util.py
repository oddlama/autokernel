import codecs
import os
import re
import autokernel.contrib
from autokernel import log

try:
    import importlib.resources as pkg_resources
except ImportError:
    # Try backported to py<37 `importlib_resources`.
    import importlib_resources as pkg_resources

kernel_option_regex = re.compile('^[_A-Z0-9]*[_A-Z][_A-Z0-9]*$')

ESCAPE_SEQUENCE_RE = re.compile(r'''
    ( \\U........   # 8-digit hex escapes
    | \\u....       # 4-digit hex escapes
    | \\x..         # 2-digit hex escapes
    | \\[0-7]{1,3}  # Octal escapes
    | \\N\{[^}]+\}  # Unicode characters by name
    | \\[\\'"nrv]   # Single-character escapes
    )''', re.UNICODE | re.VERBOSE)

def decode_escapes(s):
    def decode_match(match):
        return codecs.decode(match.group(0), 'unicode-escape')

    return ESCAPE_SEQUENCE_RE.sub(decode_match, s)

def decode_quotes(s):
    """
    Strips leading and trailing quotes from the string, if any.
    Also decodes escapes inside the string.
    """
    return decode_escapes(s[1:-1]) if s[0] == s[-1] and s[0] in ['"', "'"] else s

def parse_bool(at, s):
    if s in ['true', '1', 'yes', 'y', 'on']:
        return True
    elif s in ['false', '0', 'no', 'n', 'off']:
        return False
    else:
        log.die_print_error_at(at, "invalid value for boolean")

def is_env_var(var):
    return var.startswith('$env[') and var.endswith(']')

def resolve_env_variable(hint_at, var):
    tokens = var[len('$env['):-1].split(':', 1)
    envvar = tokens[0]
    default = None if len(tokens) == 1 else decode_quotes(tokens[1])
    value = os.environ.get(envvar, default)
    if value is None:
        log.die_print_error_at(hint_at, "unknown environment variable '{}'.".format(envvar))
    return value

def read_resource(name, pkg=autokernel.contrib):
    return pkg_resources.read_text(pkg, name)

def resource_path(name, pkg=autokernel.contrib):
    return pkg_resources.path(pkg, name)

def resource_contents(pkg):
    return pkg_resources.contents(pkg)
