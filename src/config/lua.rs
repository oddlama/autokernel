use super::Config;
use crate::bridge::Bridge;

use std::fs;
use std::path::Path;

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
            fs::read_to_string(file)?
                ))
    }
    pub fn from_raw(filename: String, code: String) -> LuaConfig {
        LuaConfig {
            lua: Lua::new(),
            filename,
            code
        }
    }
}

impl Config for LuaConfig {
    fn apply_kernel_config(&self, bridge: &Bridge) -> Result<()> {
        self.lua.context(|lua_ctx| {
            lua_ctx.load(include_bytes!("api.lua")).set_name("api.lua")?.exec()?;
            lua_ctx.scope(|scope| {
                let globals = lua_ctx.globals();

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
            })
        })?;

        Ok(())
    }
}
