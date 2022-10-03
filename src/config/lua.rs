use super::Config;
use crate::bridge::{Bridge, SymbolValue};

use std::fs;
use std::path::Path;
use std::result::Result::{Err as StdErr, Ok as StdOk};

use anyhow::{Ok, Result};
use rlua::{self, Lua};

pub struct LuaConfig {
    lua: Lua,
    filename: String,
    code: String,
}

impl LuaConfig {
    pub fn new(file: impl AsRef<Path>) -> Result<LuaConfig> {
        println!("Loading lua config...");
        Ok(LuaConfig::from_raw(
            file.as_ref().display().to_string(),
            fs::read_to_string(file)?,
        ))
    }
    pub fn from_raw(filename: String, code: String) -> LuaConfig {
        LuaConfig {
            lua: Lua::new(),
            filename,
            code,
        }
    }
}

impl Config for LuaConfig {
    fn apply_kernel_config(&self, bridge: &Bridge) -> Result<()> {
        self.lua.context(|lua_ctx| {
            let globals = lua_ctx.globals();
            lua_ctx.load(include_bytes!("api.lua")).set_name("api.lua")?.exec()?;
            let symbol_set_auto = lua_ctx.create_function(|_, (name, value): (String, String)| {
                // TODO convert result???? bridge
                // TODO convert result????     .symbol(&name)
                // TODO convert result????     .unwrap()
                // TODO convert result????     .set_symbol_value(SymbolValue::Auto(value))
                // TODO convert result????     .unwrap();
                println!("rust: set auto {name} = {value}");
                StdOk(())
            })?;
            let symbol_set_bool = lua_ctx.create_function(|_, (name, value): (String, bool)| {
                println!("rust: set bool {name} = {value}");
                StdOk(())
            })?;
            let symbol_set_number = lua_ctx.create_function(|_, (name, value): (String, i64)| {
                if value < 0 {
                    // TODO
                    println!("TODO result Please pass values >= 2*63 in string syntax. lua doesn't support this.")
                }
                println!("rust: set number {name} = {:x} -> {:x}", value, value as u64);
                StdOk(())
            })?;
            let symbol_set_tristate = lua_ctx.create_function(|_, (name, value): (String, String)| {
                println!("rust: set tristate {name} = {value}");
                StdOk(())
            })?;
            globals.set("autokernel_symbol_set_auto", symbol_set_auto)?;
            globals.set("autokernel_symbol_set_bool", symbol_set_bool)?;
            globals.set("autokernel_symbol_set_number", symbol_set_number)?;
            globals.set("autokernel_symbol_set_tristate", symbol_set_tristate)?;

            //create the autokernel set function taking in a table (or variadic)
            let mut define_all_syms = String::new();
            for name in bridge.name_to_symbol.keys() {
                let has_uppercase_char = name.chars().any(|c| c.is_ascii_uppercase());
                if name.len() > 0 && has_uppercase_char {
                    define_all_syms.push_str(&format!("CONFIG_{name} = Symbol:new(nil, \"{name}\")\n"));
                    if !name.chars().next().unwrap().is_ascii_digit() {
                        define_all_syms.push_str(&format!("{name} = CONFIG_{name}\n"));
                    }
                }
            }
            lua_ctx
                .load(&define_all_syms)
                .set_name("<internal>::define_all_syms")?
                .exec()?;

            lua_ctx.load(&self.code).set_name(&self.filename)?.exec()?;
            Ok(())
        })?;

        Ok(())
    }
}
