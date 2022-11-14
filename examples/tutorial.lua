-- This is a short introduction to the autokernel lua API.
-- The static parts of this api (classes, globals) are defined in [api.lua](https://github.com/oddlama/autokernel/blob/main/src/script/api.lua),
-- which you may use as a reference.
--
-- This file intentionally contains errors to explain autokernel and should therefore _NOT_
-- be used as an actual script.


--###############################################################
-- Loading kconfig files
--###############################################################

-- First, it is a good idea to begin with loading the defconfig for your architecture.
-- This will be sane base configuration to build upon.
--
-- This is done unchecked (by calling the kernel's internal conf_read() function), as these
-- files tend to contain statements that break the strict assignment rules. It is unclear
-- at this point whether these are actual errors in the defconfig files, or if they are
-- technically acceptable due to assignment mechanics that autokernel is unaware of.
--
-- The global variable `kernel_dir` contains the kernel directory against which autokernel
-- is currently running.
load_kconfig_unchecked(kernel_dir .. "/arch/x86/configs/x86_64_defconfig")

-- A lot of distributions currently organize their kernel configuration into smaller config
-- files that are then merged together using `scripts/kconfig/merge_config.sh` which is provided
-- with the kernel sources.
--
-- If you have existing kconfig files that you want to apply with autokernel (including
-- all validity checks), you can do so without re-writing these files in lua by using
-- the global function `load_kconfig(path)`. Paths are relative to the current working
load_kconfig("/path/to/config/usb.config")


--###############################################################
-- Assigning symbol values
--###############################################################

-- All existing symbols in the kernel are automatically exposed as global variables.
-- These are instances of a special Symbol class, which you can use to get and set values.
--
-- We can now enable the CONFIG_ACPI symbol by calling the `Symbol:set(value)` function.
-- The global variables `y`, `m` and `n` are instances of the `Tristate` class.
CONFIG_ACPI:set(y)

-- For readability, it is supported and recommended to omit the `CONFIG_` prefix for all options.
-- Reassignments like this one will also cause warnings to be emitted, as typically symbols should
-- only be assigned once.
ACPI:set(y)

-- Instead of using the global tristate values you may also simply use a string representation.
-- This allows you to omit the parenthesis in lua.
ACPI:set "y"

-- Finally, as you will set a lot of values, symbols implement the call-operator to provide a
-- nice short-hand syntax to set values. When using string values to omit the parenthesis,
-- this syntax is very similar to the classic kconfig files.
ACPI(y)   -- Using the global typed tristate symbol
ACPI "y"  -- Using a string value

-- Depending on the symbol, it might be of a different type:
DEFAULT_HOSTNAME "my_hostname" -- <- A string symbol
PHYSICAL_ALIGN(0x11223344)     -- <- A hex symbol

-- Invalid assignments will always cause errors, but errors are reported "late",
-- so evaluation continues even if an assignment failed. Most symbol assignments don't depend
-- on each other, so this allows autokernel to show you all errors at once.
ACPI "some string"      -- <- invalid value
DEFAULT_HOSTNAME(y)     -- <- invalid value
DOES_NOT_EXIST "y"      -- <- invalid symbol name
WLAN_VENDOR_REALTEK "y" -- <- unmet dependencies
RTLWIFI_USB "n"         -- <- cannot be set manually


--###############################################################
-- Conditionals
--###############################################################

-- Some symbols only exist in specific kernel versions, but you might want
-- to maintain compatiblity across several kernel versions.
--
-- The global variable `kernel_version` contains the current kernel version
-- wrapped in an instance of the `Version` class. Similarly, the `ver()` function
-- can be used to convert a version string to such a `Version` instance, which
-- can be compared to one another.
if kernel_version >= ver("5.6") then
	USB4 "y"
else
	THUNDERBOLT "y"
end


--###############################################################
-- Getting and comparing symbol values
--###############################################################

-- Symbol values can be read by using Symbol:value() or Symbol:v().
print("ACPI is currently set to " .. tostring(ACPI:value()))
print("USB4 is currently set to " .. tostring(USB4:v()))

-- To correctly compare symbol values, we need to be aware of the value type.
-- Instead of using type(...) to inspect the returned value type, the API provides
-- the Symbol:is(value) function to provide convenient value checking.
if USB4:is("y") then       -- automatic conversion
	print("USB4 is y")
elseif USB4:is("abc") then -- raises an error due to invalid symbol type comparison
	print("Not reachable")
end

-- Comparisons between symbols are also possible
if USB:is(USB4) then
	print("USB == USB4")
end

-- Roughly equivalent to USB4:is(ACPI:value()), but has even stricter requirements:
-- The two symbols must be of the same type.
if USB4:is(ACPI) then -- <- error: trying to compare Tristate to Boolean
	print("Not reachable, invalid comparison")
end


--###############################################################
-- Automatically set symbols and dependencies
--###############################################################

-- Often you need to enable a symbol which depends on other symbols being set.
-- For example `RTLWIFI_USB` is needed to enable support for many WiFi USB modules.
--
--RTLWIFI_USB "y"
--
-- Trying to execute the above statement will most likely fail, because it's dependencies
-- (`USB=y`, `WLAN=y`, `RTL_CARDS=y`, ...) are still unmet. The error message would try
-- to guide you and explain that these symbols are missing:
--   USB "y"
--   NETDEVICES "y"
--   WLAN "y"
--   WLAN_VENDOR_REALTEK "y"
--   RTL_CARDS "y"
--
-- Now you can either copy all these assignments into your config,
-- or you can directly invoke the solver from lua:
RTLWIFI_USB:satisfy { y, recursive = true }

-- This will automatically calculate and assign the required values for the symbol
-- `RTLWIFI_USB` and its dependencies to be set to `y`.
-- Specifying `recursive = true` also includes transitive dependencies.
--
-- The returned solution will always be unambiguous with respect to the symbols that will be enabled.
-- If there is a choice involved somewhere in the dependency tree (e.g. SYMBOL_A==y || SYMBOL_B==y),
-- an error will be shown that explains which options you have. One of these must then
-- be set explicitly before calling satisfy.

-- If you prefer to use modules where possible, you can solve for `m` instead:
RTLWIFI_USB:satisfy { m, recursive = true }

-- Finally, you are of course able to use lua to it's full extent. Feel free to call
-- other programs, read/write files, make web requests or anything else that you
-- require to build the perfect kernel config.
