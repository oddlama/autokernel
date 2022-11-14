-- Begin with the defconfig for your architecture
load_kconfig_unchecked(kernel_dir .. "/arch/x86/configs/x86_64_defconfig")

-- Replace this with your own config:
PCI "y"
NET "y"
USELIB "n"
LEGACY_PTYS "n"
-- ...
