use super::Config;
use crate::bridge::{Bridge, Tristate};

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
        let internal_set = |k: &String, v: &String| {
            let mut sym = bridge.symbol(k).expect(&format!("Invalid symbol in config: {k}"));
            println!("k={k}, v={v}");
            match v.as_str() {
                "n" => sym.set_symbol_value_tristate(Tristate::No)?,
                "m" => sym.set_symbol_value_tristate(Tristate::Mod)?,
                "y" => sym.set_symbol_value_tristate(Tristate::Yes)?,
                _ => {
                    if sym.is_choice() {
                        sym.set_symbol_value_choice(v)?
                    } else {
                        sym.set_symbol_value_string(v)?
                    }
                } // TODO assert correct types always! set string can be used on different types too!
            }
            Ok(())
        };

        self.lua.context(|lua_ctx| {
            lua_ctx.load(include_bytes!("api.lua")).set_name("api.lua")?.exec()?;
            lua_ctx.scope(|scope| {
                let globals = lua_ctx.globals();

                // TODO implement ToLua and FromLua for Tristate, or UserData
                globals.set("yes", "y")?;
                globals.set("mod", "m")?;
                globals.set("no", "n")?;

                //create the autokernel set function taking in a table (or variadic)
                let set = scope.create_function(|_, config: Table| {
                    for p in config.pairs::<String, String>() {
                        let (k, v) = p?;
                        internal_set(&k, &v).map_err(|ae| rlua::Error::RuntimeError(ae.to_string()))?;
                    }
                    StdOk(())
                })?;
                globals.set("set", set)?;

                let set_from_file = scope.create_function(|_, _file: String| {
                    // test if file exists
                    //let config = config::load(&file).map_err(|ae| rlua::Error::RuntimeError(ae.to_string()))?;
                    //for (k, v) in &config.build {
                    //    internal_set(k, v).map_err(|ae| rlua::Error::RuntimeError(ae.to_string()))?;
                    //}
                    StdOk(())
                })?;
                globals.set("set_from_file", set_from_file)?;

                lua_ctx.load(&self.code).set_name(&self.filename)?.exec()?;

                Ok(())
            })
        })?;

        Ok(())
    }
}
