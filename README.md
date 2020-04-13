<br/><br/>
[![autokernel](./docs/imgs/autokernel_banner.svg)](https://autokernel.oddlama.org)
<br/><br/>

[Quick start guide](https://autokernel.oddlama.org/en/latest/quick-start-guide.html) \|
[Documentation](https://autokernel.oddlama.org/en/latest) \|
[Gitter Chat](https://gitter.im/oddlama-autokernel/community)

[![Docs](https://readthedocs.org/projects/autokernel/badge/?version=latest)](https://autokernel.oddlama.org/en/latest/?badge=latest)
[![Gitter](https://badges.gitter.im/oddlama-autokernel/community.svg)](https://gitter.im/oddlama-autokernel/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

## About autokernel

Autokernel is primarily a kernel configuration management tool. This means
its main purpose is to be used as a tool to generate a `.config` file from
your particular set of kernel options. To help you accomplish this, it
comes with a set of helpful features:

* Kernel option detection for your system (based on information from `/sys`)
* Manage your kernel configuration in a sane way and detect option conflicts immediately
* Can be used as a kernel build system

You may use it for any combination of the above, There is no need to
use it as a build system if you only want to detect options for your device.

Please have a look at the [Introduction](https://autokernel.oddlama.org/en/latest/introduction.html)
section from the documentation, which explains more about what
this tool is designed for, and how it works.

<!--SCREENCASTS HERE TODO -->

## Quick start

To get started right away, please check out the [Quick start guide](https://autokernel.oddlama.org/en/latest/quick-start-guide.html).

## Installation

You can simply install the package with pip.

```
pip install autokernel
# Run setup to create a default configuration
autokernel setup
```

Otherwise, you can also clone this repository, and run
autokernel locally.

```
# Clone the repo
git clone "https://github.com/oddlama/autokernel.git"
cd autokernel
# Install requirements
pip install --user -r requirements.txt
# Execute autokernel with the wrapper in bin/
./bin/autokernel.py --help
```

## Kernel hardening

A special note if you are interested in hardening your kernel:
Be aware that autokernel provides a preconfigured module for kernel
hardening ([hardening.conf](./example/modules.d/hardening.conf)), which is
compatible with any kernel version >= 4.0. Every choice is also fully documented
and explanined. Feel free to adjust it to your needs.

## Acknowledgements

I would like to especially thank the following projects and people:

- [kconfiglib](https://github.com/ulfalizer/Kconfiglib) for the awesome python library to load and process Kconfig files, whithout which this project would have been impossible.
- [sympy](https://www.sympy.org/) for the sophisitcated symbolic logic solver
- [lark](https://github.com/lark-parser/lark) for the great parsing library
- [LKDDb](https://cateee.net/lkddb/) for providing the awesome Linux Kernel Driver Database (which is used for option detection)
- [KSSP](https://kernsec.org/wiki/index.php/Kernel_Self_Protection_Project/Recommended_Settings) for the great list of kernel hardening options
- [CLIP OS](https://docs.clip-os.org/clipos/kernel.html#configuration) for their well documented and well chosen kernel options
- [kconfig-hardened-check](https://github.com/a13xp0p0v/kconfig-hardened-check) for the collection of options from several kernel hardening resources
