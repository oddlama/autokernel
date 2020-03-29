#!/usr/bin/env python3

# For using the tool without installation via setuptools
import os
import sys
import inspect

current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import autokernel.autokernel

if __name__ == "__main__":
    autokernel.autokernel.main()
