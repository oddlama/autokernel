# autokernel

Have you ever though *Which kernel options do I need to enable to use this USB device?*,
or did you ever wonder *Why have I enabled this kernel option?*, or *Which kernel options did I even change..*?

This tool allows to both detect configuration options for the current system, and also
provides a way to properly manage your configuration changes. It can also be used to
automate the build process, but this is entirely optional.

## Detecting configuration options

This tool can automatically detect kernel configuration options for your system.
It does this by inspecting the `/sys/bus` tree exposed by the currently running kernel.

TODO it can be beneficial to detect a configuration on a very modular kernel, to increase
the likelihood of having all necessary features to detect the device in the first place.
(e.g. if usb support is disabled, we cannot detect any devices on that bus, same goes for all other subsystems)

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
./autokernel.py detect -q -t kconf
