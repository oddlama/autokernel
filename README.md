## About autokernel

Supported kernel versions: 4.2 to latest.

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

v2 is cool

This is a full rewrite of the main autokernel.

It has two major goals:
- **build**: make rebuilding a kernel with custom options as safe and painless as possible
- **configure** make configuring your kernel straightforward as possible

Our approach:
- using the kernel symbols we can check possible flags, available symbols, and can react in a configured way as well as configure the build process while defaulting to best practices
- knowing transitive dependencies, we can support in enabling or disabling features, compare it to other distributions, and in the future even support e.g. lua scripts to make kernel configuration dynamic to the situation

### Example usage

`cargo run -- linux-5.19.1`

### Build Feature Roadmap

User story: "I would like to use the gentoo kernel but switch on a few flags and not have to worry about rebuilding the kernel carefully each update - it should just work"

- [ ] Read config
- [ ] Update with user config
- [ ] Write config
- [ ] Build kernel

### Configuration Feature Roadmap

User story: "I have specific flags I want to change, e.g. due to my hardware. I might know what the main one is, like thunderbolt, but want to make sure everything is configured correctly and have all sideeffects taken care of."
User story 2: "I know what I want in which situation but currently have to track 10 different kernel configs for different devices. I would love a way to configure dynamically"

- [ ] transitive config elements
- [ ] distro comparisons
- [ ] current hardware sanity checks
- [ ] lua / wren / python scripts to manipulate symbols

## Principles

- rather keep the codebase simple than adding convenience features
- unambiguosity is key, rather write more verbose configs, than have an unbootable kernel because of a typo (relevant for e.g. the lua API and == vs is(), where only is() is typesafe
