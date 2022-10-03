// -- todo always test all three "y" ("y") and .set("y") using rust
// BOOLEAN_SYMBOL(true)
// BOOLEAN_SYMBOL(false)
// BOOLEAN_SYMBOL "y"
// BOOLEAN_SYMBOL "n"
// BOOLEAN_SYMBOL(yes)
// BOOLEAN_SYMBOL(no)
//
// TRISTATE_SYMBOL(true)
// TRISTATE_SYMBOL(false)
// TRISTATE_SYMBOL "y"
// TRISTATE_SYMBOL "m"
// TRISTATE_SYMBOL "n"
// TRISTATE_SYMBOL(yes)
// TRISTATE_SYMBOL(mod)
// TRISTATE_SYMBOL(no)
//
// STRING_SYMBOL ""
// STRING_SYMBOL "y"
// STRING_SYMBOL "m"
// STRING_SYMBOL "n"
// STRING_SYMBOL "some_string"
//
// CHOICE_SYMBOL "SOME_CHOICE"
// CHOICE_SYMBOL(SOME_CHOICE)
//
// INT_SYMBOL "1"
// INT_SYMBOL(0)
//
// HEX_SYMBOL "0x1234"
// HEX_SYMBOL(0xaabbccdd11223344)
//
// load_kconfig [[
// # Todo always expand to:
// # X "y"
// # X = "y"
// # CONFIG_X "y"
// # CONFIG_X = "y"
// TRISTATE_SYMBOL "y"
// TRISTATE_SYMBOL "m"
// TRISTATE_SYMBOL "n"
//
// STRING_SYMBOL ""
// STRING_SYMBOL "y"
// STRING_SYMBOL "m"
// STRING_SYMBOL "n"
// STRING_SYMBOL "some_string"
//
// INT_SYMBOL "1"
// INT_SYMBOL "0"
// INT_SYMBOL 1
// INT_SYMBOL 0
//
// HEX_SYMBOL "0x1234"
// HEX_SYMBOL "0xaabbccdd11223344"
// HEX_SYMBOL 0x1234
// HEX_SYMBOL 0xaabbccdd11223344
//
// # Comment
// ]]
//
// -- Errors
//
// -- try to support this using rlua
// TRISTATE_SYMBOL = yes
// TRISTATE_SYMBOL = "y"
//
// BOOLEAN_SYMBOL "m"
// BOOLEAN_SYMBOL(mod)
//
// TRISTATE_SYMBOL ""
// TRISTATE_SYMBOL "yes"
// TRISTATE_SYMBOL "mod"
// TRISTATE_SYMBOL "no"
// TRISTATE_SYMBOL "string"
// TRISTATE_SYMBOL(0)
// TRISTATE_SYMBOL(1)
//
// INT_SYMBOL(true)
// INT_SYMBOL(false)
// INT_SYMBOL "0x0"
// INT_SYMBOL "0x1234"
// INT_SYMBOL ""
// INT_SYMBOL " 1"
// INT_SYMBOL "1 "
// INT_SYMBOL "1-1"
// INT_SYMBOL "test"
//
// HEX_SYMBOL(true)
// HEX_SYMBOL(false)
// HEX_SYMBOL "0"
// HEX_SYMBOL "1234"
// HEX_SYMBOL ""
// HEX_SYMBOL " 0x1"
// HEX_SYMBOL "0x1 "
// HEX_SYMBOL "0x1-0x1"
// HEX_SYMBOL "0x"
// HEX_SYMBOL "test"
//
//
//
//
//
//
//
//
//
//
// --if EXPERT == yes then
// --	TEST "n"
// --end
//
//
//
//
//
//
// --EXPERT 1
// --EXPERT yes
// --set_from_file("config.txt")
