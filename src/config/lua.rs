use super::Config;
use crate::bridge::Bridge;

use std::fs;
use std::path::Path;
use std::result::Result::Ok as StdOk;

use anyhow::{Ok, Result};
use rlua::{self, Lua, Table};

pub(super) struct LuaConfig {
    lua: Lua,
    filename: String,
    code: String,
}

impl LuaConfig {
    pub fn new(file: impl AsRef<Path>) -> Result<LuaConfig> {
        println!("Loading lua config...");
        Ok(LuaConfig {
            lua: Lua::new(),
            filename: file.as_ref().display().to_string(),
            code: fs::read_to_string(file)?,
        })
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
                    if name.len() > 0
                        && name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
                        && name.chars().next().unwrap().is_ascii_alphabetic()
                    {
                        define_all_syms.push_str(&format!("{name} = Symbol:new(nil, \"{name}\")\n"));
                    } else {
                        println!("{name} = Symbol:new(nil, \"{name}\")")
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
