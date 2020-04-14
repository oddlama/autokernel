<br/><br/>
[![autokernel](./docs/imgs/autokernel_banner.svg)](https://autokernel.oddlama.org)
<br/><br/>

[Quick start guide](https://autokernel.oddlama.org/en/latest/intro/quick-start-guide.html) \|
[Documentation](https://autokernel.oddlama.org/en/latest) \|
[Gitter Chat](https://gitter.im/oddlama-autokernel/community)

[![PyPI](https://img.shields.io/pypi/v/autokernel.svg)](https://pypi.org/pypi/autokernel/)
[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Docs](https://readthedocs.org/projects/autokernel/badge/?version=latest)](https://autokernel.oddlama.org/en/latest/?badge=latest)
[![Gitter](https://badges.gitter.im/oddlama-autokernel/community.svg)](https://gitter.im/oddlama-autokernel/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

## About autokernel

Autokernel is primarily a kernel configuration management tool.
Its main purpose is to generate a kernel `.config` file from
a more formal description of your configuration.
To help you writing the configuration, it comes with some helpful features:

* Detect kernel options for your system (based on information from `/sys`)
* Manage the kernel configuration in a more structured and sane way.
  Option conflict detection and conditional expressions for configuration statements
  allow writing a sound and modular configuration that can be used with multiple kernel versions.
* Build the kernel (and initramfs) and install them on the system

You may use it for any combination of the above, There is no need to
use it as a build system if you only want to detect options for your device.

Please have a look at the [Introduction](https://autokernel.oddlama.org/en/latest/intro/introduction.html)
section from the documentation, which explains more about what
this tool is designed for, and how it works.

Detecting kernel options                                                           | Automatically satisfying a kernel option
---------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------
[![asciicast](https://asciinema.org/a/320174.svg)](https://asciinema.org/a/320174) | [![asciicast](https://asciinema.org/a/320179.svg)](https://asciinema.org/a/320179)

## Quick start

To get started right away, please check out the [Quick start guide](https://autokernel.oddlama.org/en/latest/intro/quick-start-guide.html).
For in-depth command explanations, visit the [Usage section](https://autokernel.oddlama.org/en/latest/contents/usage.html).

## Installation

You can use pip to install autokernel, or run from source:

#### pip

```bash
pip install autokernel
```

#### From source

```bash
git clone "https://github.com/oddlama/autokernel.git"
cd autokernel
pip install -r requirements.txt
./bin/autokernel.py --help
```

Afterwards you should run `autokernel setup` once to create a default configuration
in `/etc/autokernel`.

## Kernel hardening

A special note if you are interested in hardening your kernel:
Be aware that autokernel provides a preconfigured module for kernel
hardening ([hardening.conf](./autokernel/contrib/etc/modules_d/hardening.conf)), which is
compatible with any kernel version >= 4.0. Every choice is also fully documented
and explanined. Feel free to adjust it to your needs.

## Acknowledgements

I would like to especially thank the following projects and people behind them:

- [kconfiglib](https://github.com/ulfalizer/Kconfiglib) for the awesome python library to load and process Kconfig files, whithout which this project would have been impossible.
- [sympy](https://www.sympy.org/) for the sophisitcated symbolic logic solver
- [lark](https://github.com/lark-parser/lark) for the great parsing library
- [LKDDb](https://cateee.net/lkddb/) for providing the awesome Linux Kernel Driver Database (which is used for option detection)
- [KSSP](https://kernsec.org/wiki/index.php/Kernel_Self_Protection_Project/Recommended_Settings) for the great list of kernel hardening options
- [CLIP OS](https://docs.clip-os.org/clipos/kernel.html#configuration) for their well documented and well chosen kernel options
- [kconfig-hardened-check](https://github.com/a13xp0p0v/kconfig-hardened-check) for the collection of options from several kernel hardening resources
