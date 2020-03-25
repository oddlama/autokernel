import sys

verbose_output = False
quiet_output = False

def verbose(msg):
    if not quiet_output and verbose_output:
        print(" * [2;37m{}[m".format(msg))

def info(msg):
    if not quiet_output:
        print("[1;32m *[m {}".format(msg))

def warn(msg):
    if not quiet_output:
        print("[1;33m *[m {}".format(msg))

def error(msg):
    print("[1;31m * ERROR:[m {}".format(msg), file=sys.stderr)

def die(message):
    error(message)
    sys.exit(1)
