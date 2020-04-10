<br/><br/>
[![autokernel](./docs/autokernel_banner.svg)](https://autokernel.oddlama.org)
<br/><br/>

[Quick start guide](https://autokernel.oddlama.org) \|
[Documentation](https://autokernel.oddlama.org) \|
[Gitter Chat](https://gitter.im/oddlama-autokernel/community)

[![Docs](https://readthedocs.org/projects/autokernel/badge/?version=latest)](https://autokernel.oddlama.org/en/latest/?badge=latest)
[![Gitter](https://badges.gitter.im/oddlama-autokernel/community.svg)](https://gitter.im/oddlama-autokernel/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

## About autokernel

Autokernel is a kernel configuration management tool. It can:

* detect kernel options for your system
* be used as a kernel configuration manager (it provides a proper way to represent kernel configurations, guarantees reproducible results and has support for conditionals)
* can be used as a kernel build system

You may use it for any combination of the above, as there is no need to
use it as a build system if you only want to detect options for your device.

If you want to try autokernel for yourself, please check out the [Quick start guide](https://autokernel.oddlama.org)

<!--SCREENCASTS HERE TODO-->

## Features

* Can detect kernel options for your system using 
* Manage config
* Compare against current kernel or other config
* Build kernel, initramfs, as seperate files or even atomatically integrated into the kernel
* Sane way to write your config

If you want want to **harden your kernel**, be aware that autokernel provides a
preconfigured module for kernel hardening, which is compatible with any kernel version >= 4.0,
and is derived from the following has explanations for every option.
and 

## Why should I care? What problem does it solve?

> *Which kernel options do I need to enable to use this USB device?*

> *Why have I enabled this kernel option again?*

> *Which kernel options did I even change compared to the default?*

Does any of these question sound familiar? Then this tool might solve a problem for you.

Autokernel can both detect configuration options for the current system, and also
be used to manage your kernel configuration. It can additionally be used
to automate the build process, but this is entirely optional.

## Installation

You can simply install the package with pip.

```
pip install autokernel
```

#### Quick start guide

Be sure autokernel is installed.

> Quickly check which options are detected and what the current values are for the running kernel
./autokernel.py detect -c

Use ... to detect options for your system and compare them against your current kernel (requries /proc/config.gz) this can be abbreviated to ... if you have the sources
for your current kernel in /usr/src/linux

> Write only the suggested configuration changes to stdout in kconf format, so that you could
> theoretically merge them into a kernel .config file
./autokernel.py -q detect -t kconf

Copy .. to etc and edit it to suit your needs. Be sure to have a look at the config documentation

Use ... to compare the generated config against the running one.

Use ... to generate a .config file.

Use .. to make a full kernel build.

Be sure to check out --help and the documentation to fully understand what can be done.






COMMANDS TO EXPLAIN:

> Quickly check which options are detected and what the current values are for the running kernel
./autokernel.py detect -c

> Write only the suggested configuration changes to stdout in kconf format, so that you could
> theoretically merge them into a kernel .config file
./autokernel.py -q detect -t kconf

> Create autokernel modules for the detected options.
> By default the module to select all configuration options will be named 'local',
> so you only need to add `use local;` to your main config file.
./autokernel.py detect -o /etc/autokernel/modules.d/local


TODO say that you should remove modules that conflict with e.g. security, and also in general look tthrough the detected modules and remove
ones that you dont recognize or think might be wrong or undesirable. Its not generate and forget, but more a collection of what could
be interesting to yoz,

## Acknowledgements

I would like to especially thank the following projects and people:

- [LKDDb](https://cateee.net/lkddb/) for providing the awesome Linux Kernel Driver Database (which is used for option detection)
- [KSSP](https://kernsec.org/wiki/index.php/Kernel_Self_Protection_Project/Recommended_Settings) for the great list of kernel hardening options
- [CLIP OS](https://docs.clip-os.org/clipos/kernel.html#configuration) for their well documented and well chosen kernel options
- [kconfig-hardened-check](https://github.com/a13xp0p0v/kconfig-hardened-check) for the collection of options from several kernel hardening resources
