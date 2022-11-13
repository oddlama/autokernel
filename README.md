<p align="center"><img width="auto" height="90" src="https://user-images.githubusercontent.com/31919558/201540026-7b9281f5-0f1b-4d7a-8b69-4480b1e467d3.png"></p>

<div align="center">

[![Tutorial](https://img.shields.io/badge/Landing_Page-informational.svg)](https://github.com/oddlama/autokernel/blob/main/examples/tutorial.lua)
[![MIT License](https://img.shields.io/badge/license-MIT-informational.svg)](./LICENSE)

</div>

# About autokernel

Autokernel is a tool to manage your kernel configuration that guarantees semantic correctness.
It checks symbol assignments for validity using a native bridge to the kernel's Kconfig interface
and ensures that your configuration doesn't silently break on kernel updates.

- 🧰 Configuration via Lua / kconfig configuration
-  Automatically find satisfying assignments for a symbols and its dependencies
- Integrate an initramfs in a two-stage kernel build
- Write your configuration using classical kconfig files or in lua if you require conditionals or more complex logic.
- Supports all kernels since version `4.2`

## Installation \& Usage

Autokernel can be installed with cargo:

```bash
$ cargo install autokernel
```

Afterwards you will need to create a `/etc/autokernel/config.toml` (for a reference see [config.toml](https://github.com/oddlama/autokernel/blob/main/config.toml)):

```toml
[config]
#script = "/etc/autokernel/legacy.config"
script = "/etc/autokernel/config.lua"
```

Then write your kernel configuration in `/etc/autokernel/config.lua`:

```lua
-- Begin with the defconfig for your architecture
load_kconfig_unchecked(kernel_dir .. "/arch/x86/configs/x86_64_defconfig")

-- Change some symbols
NET "y"
```

And finally run autokernel to generate a `.config` file or directly build the kernel:

```bash
# Just generate the {kernel_dir}/.config file
$ autokernel generate-config
# Or directly build the whole kernel
$ autokernel build
```

If you want to maintain a package for your favourite distribution, feel free to do so and let us know!

## Example

## Showcase

#### Invalid value detection

#### Detects missing dependencies

#### Automatically satisfy a symbol and its dependencies

#### Duplicate assignments

## Why?

Frequently when the kernel evolves, its config options may change.
If you want to keep a structured configuration for your kernel, it is easy to miss those changes,
as the default behavior of the kernel kconfig scripts is to ignore invalid symbols and values.
This makes it difficult to all necessary critical changes in your config.

Autokernel provides an alternative way to configure your kernel. Instead of simply merging
traditional traditional kconfig files, autokernel provides a framework which understands
the semantics behind symbols, their dependencies and allowed values and enforces these rules
when generating a kernel configuration `.config`.

Additionally, autokernel tries to provide as much helpful information as possible in case
an error is encountered. It can not only detect invalid assignments, but also tries to
give you as much information about the cause as possible.

If you have ever searched for an option in `make menuconfig` and couldn't find it or jump to it,
it is probably because it's dependencies were not yet met. In most cases, autokernel can automatically
solve the dependency expression of the symbol and tell you which changes need to be made to
make the symbol visible.


`CONFIG_THUNDERBOLT -> CONFIG_USB4`
