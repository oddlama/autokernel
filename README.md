<p align="center"><img width="auto" height="90" src="https://user-images.githubusercontent.com/31919558/201540026-7b9281f5-0f1b-4d7a-8b69-4480b1e467d3.png"></p>

<div align="center">

[![Tutorial](https://img.shields.io/badge/API-Tutorial-informational.svg)](https://github.com/oddlama/autokernel/blob/main/examples/tutorial.lua)
[![MIT License](https://img.shields.io/badge/license-MIT-informational.svg)](./LICENSE)

</div>

# About autokernel

Autokernel is a tool for managing your kernel configuration that guarantees semantic correctness.
It checks symbol assignments for validity by creating a native bridge to the kernel's
Kconfig interface and ensures that your configuration does not silently break during kernel updates.
The next time a config option is removed or renamed, similar to when `CONFIG_THUNDERBOLT` was merged
with `CONFIG_USB4`, you will notice.

It provides a configuration framework which understands the semantics behind symbols,
their dependencies and allowed values and enforces these rules when generating the final
`.config` kernel configuration file. It is able to automatically resolve symbol dependencies
and show useful diagnostics to help you solve configuration errors.

The configuration itself can be written using traditional kconfig files
or by using the more flexible and powerful lua scripting api. This allows for more complex logic
and compatibility with multiple kernel versions. All kernel versions back to `v4.2.0` are supported.

## Installation \& Quickstart

Autokernel can be installed with cargo:

```bash
$ cargo install autokernel
```

Afterwards you will need to create a `/etc/autokernel/config.toml` (for a reference see [examples/config.toml](https://github.com/oddlama/autokernel/blob/main/examples/config.toml)).
Here you can configure which script is used to generate the kernel configuration and how the artifacts
should be installed to your system when using `autokernel build --install`.

```toml
[config]
#script = "/etc/autokernel/legacy.config"
script = "/etc/autokernel/config.lua"
```

Now you can write your kernel configuration. You can either use a classic kconfig file here
(just change the config above as the comment shows), or use the recommended lua interface.
The provided lua API is a more powerful and versatile way to write your configuration.
With it you will be able to create more structured, complex and reusable configurations.
See [tutorial.lua](examples/tutorial.lua) for an introduction to the api. Here's a very small
example `config.lua`:

```lua
-- Begin with the defconfig for your architecture
load_kconfig_unchecked(kernel_dir .. "/arch/x86/configs/x86_64_defconfig")
-- Change some symbols
NET "y"
USB "y"
```

Finally run autokernel to generate a `.config` file. In case your configuration contains any errors,
autokernel will abort and print the relevant diagnostics.

```bash
# Just generate the {kernel_dir}/.config file
$ autokernel generate-config
# Or directly build the whole kernel
$ autokernel build
```

If you want to maintain a package for your favourite distribution, feel free to do so and let us know!

## Introduction

To set a symbol you can use the syntax below.

```lua
-- This will set `CONFIG_NET` to yes.
NET "y"
```

You can also try to assign a value that isn't allowed:

```lua
-- `CONFIG_NET` is a boolean symbol, so mod isn't allowed.
NET "m"
```

The kernel would usually ignore such statements entirely. Autokernel will instead
abort with an error and display diagnostics telling you that only `n` or `y` are allowed:

![Invalid assignment](https://user-images.githubusercontent.com/31919558/201546052-5c65b680-f722-43f5-b563-80cd6c2ced7f.png)

Kernel options can also only be assigned if they are visible, meaning that their
dependencies must be met. If you try to enable an option that has unmet dependencies,
autokernel will detect that and automatically suggest a solution.

```lua
-- This requires WLAN=y and NETDEVICES=y
WLAN_VENDOR_REALTEK "y"
```

![Automatic dependency resolution](https://user-images.githubusercontent.com/31919558/201546061-9da4cd5f-0fba-46a8-a161-8b583bf3e9e1.png)

Instead of blindly copying these assignments into your config, you can also invoke the solver directly
from lua. This will only work when the solution is unambiguous, otherwise autokernel will
raise an error and tell you what is missing.

```lua
-- Enable WLAN_VENDOR_REALTEK and any required dependencies
WLAN_VENDOR_REALTEK:satisfy { y, recursive = true }
```

You can also view what you would have to change without provoking an error in your config first
by using `autokernel satisfy --recursive WLAN_VENDOR_REALTEK` as a one-shot command.

![One-shot dependency resolution](https://user-images.githubusercontent.com/31919558/201546071-de397f53-d4a7-40d8-b9dc-6ad6f6c5c64a.png)

There are also some symbols that cannot be set manually, like `RTLWIFI_USB`.
Trying to assign them directly will cause an error:

```lua
RTLWIFI_USB "y"
```

![Manual assignment error](https://user-images.githubusercontent.com/31919558/201546077-645e990d-8286-477c-886e-4e1614c88f07.png)

Instead, these need to be enabled by setting another symbol that depends on `RTLWIFI_USB`.
The automatic satisfier is able to solve these aswell, so you can use the same command as
above to find the required assignments or just use `satisfy` directly from lua again:

```lua
RTLWIFI_USB:satisfy { y, recursive = true }
```

Finally you might want to build more complex scripts, which is were lua comes into play.
It will allow you to do conditional assignments like this:

```lua
if kernel_version >= ver("5.6") then
	USB4 "y"
else
	THUNDERBOLT "y"
end
```

Refer to [tutorial.lua](examples/tutorial.lua) for a thorough introduction to the api.

## Hardening example

For an example configuration for kernel hardening, see [hardening.lua](examples/hardening.lua).
