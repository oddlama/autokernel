--load_kconfig("/usr/src/linux/.config", true)

CMDLINE_BOOL(true)
CMDLINE_BOOL(false)
CMDLINE_BOOL "y"
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

CONFIG_CONSOLE_LOGLEVEL_DEFAULT "2"
CONFIG_CONSOLE_LOGLEVEL_DEFAULT(1)

PHYSICAL_ALIGN "0x400000"
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
