verbose_output = False

def verbose(msg):
    if verbose_output:
        print(" * [2;37m{}[m".format(msg))

def info(msg):
    print("[1;32m *[m {}".format(msg))

def warn(msg):
    print("[1;33m *[m {}".format(msg))

def error(msg):
    print("[1;31m * ERROR:[m {}".format(msg))
