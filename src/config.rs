use std::fs;
use std::path::Path;
use std::result::Result::Ok as stdOk;

use anyhow::{anyhow, Ok, Result};
use indexmap::map::IndexMap;
use rlua::{self, Lua, Table};

use crate::bridge::{Bridge, Tristate};

pub fn load(path: impl AsRef<Path>) -> Result<IndexMap<String, String>> {
    let mut map = IndexMap::new();
    for line in fs::read_to_string(path)?.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with("#") {
            continue;
        }
        let (k, v) = line.split_once("=").ok_or(anyhow!(format!("invalid line {line}")))?;
        // TODO trimming all " might not be desired
        // TODO trimming CONFIG on right side should only be done for choice symbols
        map.insert(
            k.trim().trim_start_matches("CONFIG_").to_string(),
            v.trim()
                .trim_start_matches('"')
                .trim_end_matches('"')
                .trim_start_matches("CONFIG_")
                .to_string(),
        );
    }
    Ok(map)
}


pub fn run_lua(bridge: &Bridge, filename: &str) -> Result<()> {
    let lua_code = fs::read_to_string(filename)?;
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

    let lua = Lua::new();
    lua.context(|lua_ctx| {
        lua_ctx.scope(|scope| {
            // You can get and set global variables.  Notice that the globals table here is a permanent
            // reference to _G, and it is mutated behind the scenes as Lua code is loaded.  This API is
            // based heavily around sharing and internal mutation (just like Lua itself).

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
                stdOk(())
            })?;
            globals.set("set", set)?;

            let set_from_file = scope.create_function(|_, _file: String| {
                // test if file exists
                //let config = config::load(&file).map_err(|ae| rlua::Error::RuntimeError(ae.to_string()))?;
                //for (k, v) in &config.build {
                //    internal_set(k, v).map_err(|ae| rlua::Error::RuntimeError(ae.to_string()))?;
                //}
                stdOk(())
            })?;
            globals.set("set_from_file", set_from_file)?;

            lua_ctx.load(&lua_code).exec()?;

            Ok(())
        })
    })?;

    Ok(())
}
