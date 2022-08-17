## About autokernel

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
