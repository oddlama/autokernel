--load_kconfig("/usr/src/linux/.config", true)
--load_kconfig("arch/$ARCH/defconfig")
--load_kconfig("/usr/src/linux/linux-" .. ak.kernel_version .. "-gentoo-dist/.config")

-- bools are not allowed on purpose, because CMDLINE_BOOL == true cannot be overwritten

CMDLINE_BOOL "y"
--print(ak.kernel_version)
--print(y < y)
--print(y < m)
--print(y < n)
--print(m < y)
--print(m < m)
--print(m < n)
--print(n < y)
--print(n < m)
--print(n < n)
--print(CMDLINE_BOOL() < y)
--print(CMDLINE_BOOL() < m)
--print(CMDLINE_BOOL() < n)
--print(CMDLINE_BOOL:value())
--print(CONFIG_MODULES:value())
--print(CONFIG_CRYPTO:value())
--print(DEFAULT_HOSTNAME:value())
--print(CONSOLE_LOGLEVEL_DEFAULT:value())
--print(PHYSICAL_ALIGN:str_value())

CMDLINE_BOOL "n"
CMDLINE_BOOL(y)
CMDLINE_BOOL(n)
CMDLINE_BOOL(yes)
CMDLINE_BOOL(no)

CONFIG_MODULES "y"
CONFIG_CRYPTO "y"
CONFIG_CRYPTO "m"
CONFIG_CRYPTO "n"
CONFIG_CRYPTO(yes)
CONFIG_CRYPTO(mod)
CONFIG_CRYPTO(no)

DEFAULT_HOSTNAME ""
DEFAULT_HOSTNAME "y"
DEFAULT_HOSTNAME "m"
DEFAULT_HOSTNAME "n"
DEFAULT_HOSTNAME "some_string"

CONSOLE_LOGLEVEL_DEFAULT "2"
CONSOLE_LOGLEVEL_DEFAULT(1)

PHYSICAL_ALIGN "0x200000"

satisfy_deps_m RTLWIFI_USB
RTLWIFI_USB "y"

--PHYSICAL_ALIGN("0xaabbccdd123456")
--PHYSICAL_ALIGN("0xaabbccdd1234567")
--PHYSICAL_ALIGN("0xaabbccdd12345678")
--PHYSICAL_ALIGN("0x7fffffffffffffff")
--PHYSICAL_ALIGN("0x8000000000000000")
--PHYSICAL_ALIGN(0x7fffffffffffffff)
--PHYSICAL_ALIGN(0x8000000000000000)
--PHYSICAL_ALIGN(0x8000000000000001)
--PHYSICAL_ALIGN(0xaabbccdd123456)
--PHYSICAL_ALIGN(0xaabbccdd1234567)
--PHYSICAL_ALIGN(0xaabbccdd12345678)
