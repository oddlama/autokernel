<br/><br/>
[![autokernel](./docs/autokernel_banner.svg)](https://github.com/oddlama/autokernel)

[Quick start guide](https://github.com/oddlama/autokernel) \|
[Documentation](https://github.com/oddlama/autokernel) \|
[Gitter Chat](https://gitter.im/oddlama-autokernel/community)

[![Gitter](https://badges.gitter.im/oddlama-autokernel/community.svg)](https://gitter.im/oddlama-autokernel/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge)

## About autokernel

**TL;DR:**

autokernel is a pure python tool for kernel configuration management that can:

* detect kernel options for your system
* be used as a kernel configuration generator with a proper way
  to store changes, allows for basic logic and reproducible results
* can be used as a kernel build system

You can use it for any combination of the above, there is no need to
use it as a build system if you only want to detect options for your device.
It also provides an autokernel module to harden any kernel with version >= 4.0.0.

SCREENCASTS HERE TODO

## Why should I care?

> *Which kernel options do I need to enable to use this USB device?*

> *Why have I enabled this kernel option again?*

> *Which kernel options did I even change compared to the default?*

Does any of these question sound familiar? Then this tool might solve a problem for you.

autokernel can both detect configuration options for the current system, and also
provides a way to properly manage your kernel configuration. It can additionally be used
to automate the build process, but this is entirely optional.

## Installation

You can simply install the package with pip.

```
pip install autokernel
```

## Feature overview

#### Detecting configuration options

This tool can automatically detect kernel configuration options for your system.
It does this by collecting bus and device information from the `/sys/bus` tree exposed
by the currently running kernel. It then relates this information to a configuration option database (lkddb),
and also selects required dependencies by finding a solution to the dependency graph for each option.

It might be beneficial to run detection while using a very generic and modular kernel,
such as the default kernel on Arch Linux. This increases the likelihood of having all necessary buses and features
enabled to actually detect connected devices. Basically we cannot detect usb devices, if the current kernel does
not support the bus in the first place.

#### Managing the kernel config

Have you ever wondered something like: *Why have I enabled this kernel option?*,
or have you ever wondered what kernel options you have changed from the default options?
While you can try to use scripts like `diffconfig`, these will output overwhelming amounts of information.
You will not only see the options you have changed, but also all of the dependencies they carried with them.

How can you avoid this mess? Instead of managing `.config` directly, you should manage the differences to a well
known set of default options. I recommend using `make defconfig` or even better `make allnoconfig`.
This way you can document all of your choices and will be able to understand why you have enabled a particular option
in the future (the same goes for disabling options).

This tool allows you to store all your configuration options in any folder (by default `/etc/autokernel.d/`) and
when you update your kernel, you can generate a new `.config` from the known default with your changes applied.

#### Building the kernel

Lastly, this tool can be used to build the kernel.








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
