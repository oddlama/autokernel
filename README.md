# autokernel

> *Which kernel options do I need to enable to use this USB device?*

> *Why have I enabled this kernel option again?*

> *Which kernel options did I even change when compared to the default?*

Does any of these question sound familiar? Then this tool might solve a problem for you.

Autokernel can both detect configuration options for the current system, and also
provide a way to properly manage your kernel configuration. It may also be used to
automate the build process, but this is entirely optional.

## Detecting configuration options

This tool can automatically detect kernel configuration options for your system.
It does this by collecting bus and device information from the `/sys/bus` tree exposed
by the currently running kernel. It then relates this information to a configuration option database (lkddb),
and also selects required dependencies by finding a solution to the dependency graph for each option.

It might be beneficial to run detection while using a very generic and modular kernel,
such as the default kernel on Arch Linux. This increases the likelihood of having all necessary buses and features
enabled to actually detect connected devices. Basically we cannot detect usb devices, if the current kernel does
not support the bus in the first place.

## Managing the kernel config

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

## Building the kernel

Lastly, this tool can be used to build the kernel.
TODO not currently.









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
