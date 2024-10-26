use super::{KConfig, Script};
use crate::bridge::satisfier::SolverConfig;
use crate::bridge::{Bridge, SymbolValue};

use std::fmt::Write;
use std::fs;
use std::path::Path;
use std::result::Result::{Err as StdErr, Ok as StdOk};

use anyhow::{Context, Ok, Result};
use mlua::{self, Error as LuaError, ExternalResult, Lua};

pub struct LuaScript {
    lua: Lua,
    filename: String,
    code: String,
}

impl LuaScript {
    pub fn new(file: impl AsRef<Path>) -> Result<LuaScript> {
        LuaScript::from_raw(
            file.as_ref().display().to_string(),
            fs::read_to_string(&file).context(format!("Could not read lua script {}", file.as_ref().display()))?,
        )
    }

    pub fn from_raw(filename: String, code: String) -> Result<LuaScript> {
        Ok(LuaScript {
            lua: unsafe { Lua::unsafe_new() },
            filename,
            code,
        })
    }
}

impl Script for LuaScript {
    fn apply(&self, bridge: &Bridge) -> Result<()> {
        self.lua.scope(|scope| {
            let symbol_set_auto = scope.create_function(
                |_, (name, value, file, line, traceback): (String, String, String, u32, String)| {
                    bridge
                        .symbol(&name)
                        .unwrap()
                        .set_value_tracked(SymbolValue::Auto(value), file, line, Some(traceback))
                        .ok();
                    StdOk(())
                },
            )?;
            let symbol_set_bool = scope.create_function(
                |_, (name, value, file, line, traceback): (String, bool, String, u32, String)| {
                    bridge
                        .symbol(&name)
                        .unwrap()
                        .set_value_tracked(SymbolValue::Boolean(value), file, line, Some(traceback))
                        .ok();
                    StdOk(())
                },
            )?;
            let symbol_set_number = scope.create_function(
                |_, (name, value, file, line, traceback): (String, i64, String, u32, String)| {
                    // We use an i64 here to detect whether values in lua got clipped. Apparently
                    // when values wrap
                    if value < 0 {
                        return StdErr(LuaError::RuntimeError(
                            "Please pass values >=2*63 in string syntax. lua doesn't support this.".to_string(),
                        ));
                    }
                    bridge
                        .symbol(&name)
                        .unwrap()
                        .set_value_tracked(SymbolValue::Number(value as u64), file, line, Some(traceback))
                        .ok();
                    StdOk(())
                },
            )?;
            let symbol_set_tristate = scope.create_function(
                |_, (name, value, file, line, traceback): (String, String, String, u32, String)| {
                    bridge
                        .symbol(&name)
                        .unwrap()
                        .set_value_tracked(
                            SymbolValue::Tristate(value.parse().map_err(|_| {
                                LuaError::RuntimeError(format!("Could not convert {value} to tristate"))
                            })?),
                            file,
                            line,
                            Some(traceback),
                        )
                        .ok();
                    StdOk(())
                },
            )?;
            let symbol_satisfy_and_set = scope.create_function(
                |_, (name, value, recursive, file, line, traceback): (String, String, bool, String, u32, String)| {
                    let value = value
                        .parse()
                        .map_err(|_| LuaError::RuntimeError(format!("Could not convert {value} to tristate")))?;
                    let satisfying_configuration = bridge.symbol(&name).unwrap().satisfy_track_error(
                        SymbolValue::Tristate(value),
                        file.clone(),
                        line,
                        Some(traceback.clone()),
                        SolverConfig {
                            recursive,
                            desired_value: value,
                            ..SolverConfig::default()
                        },
                    );

                    // If there was an error, it will have been tracked already.
                    // Ignore and continue.
                    if satisfying_configuration.is_err() {
                        return StdOk(());
                    }

                    for (sym, value) in satisfying_configuration.unwrap() {
                        bridge
                            .symbol(&sym)
                            .unwrap()
                            .set_value_tracked(
                                SymbolValue::Tristate(value),
                                file.clone(),
                                line,
                                Some(traceback.clone()),
                            )
                            .ok();
                    }

                    let mut symbol = bridge.symbol(&name).unwrap();
                    if symbol.prompt_count() > 0 {
                        symbol
                            .set_value_tracked(SymbolValue::Tristate(value), file, line, Some(traceback))
                            .ok();
                    }

                    StdOk(())
                },
            )?;
            let symbol_get_string =
                scope.create_function(|_, name: String| StdOk(bridge.symbol(&name).unwrap().get_string_value()))?;
            let symbol_get_type = scope.create_function(|_, name: String| {
                StdOk(format!("{:?}", bridge.symbol(&name).unwrap().symbol_type()))
            })?;

            let load_kconfig = scope.create_function(|_, (path, checked): (String, bool)| {
                if checked {
                    KConfig::new(path)
                        .map_err(|e| LuaError::RuntimeError(e.to_string()))?
                        .apply(bridge)
                        .ok();
                    // Errors will be tracked automatically
                    StdOk(())
                } else {
                    bridge
                        .read_config_unchecked(path)
                        .map_err(|e| LuaError::RuntimeError(e.to_string()))
                }
            })?;

            let kernel_env = scope.create_function(|_, name: String| StdOk(bridge.get_env(&name)))?;

            let ak = self.lua.create_table()?;
            ak.set("kernel_dir", bridge.kernel_dir.to_str())?;
            ak.set("kernel_version_str", bridge.get_env("KERNELVERSION"))?;
            ak.set("symbol_set_auto", symbol_set_auto)?;
            ak.set("symbol_set_bool", symbol_set_bool)?;
            ak.set("symbol_set_number", symbol_set_number)?;
            ak.set("symbol_set_tristate", symbol_set_tristate)?;
            ak.set("symbol_satisfy_and_set", symbol_satisfy_and_set)?;
            ak.set("symbol_get_string", symbol_get_string)?;
            ak.set("symbol_get_type", symbol_get_type)?;
            ak.set("load_kconfig", load_kconfig)?;
            ak.set("kernel_env", kernel_env)?;
            self.lua.globals().set("ak", ak)?;

            self.lua.load(include_str!("api.lua")).set_name("api.lua").exec()?;

            let mut define_all_syms = String::new();
            for name in bridge.name_to_symbol.keys() {
                let has_uppercase_char = name.chars().any(|c| c.is_ascii_uppercase());
                if !name.is_empty() && has_uppercase_char {
                    writeln!(define_all_syms, "CONFIG_{name} = Symbol:new(nil, \"{name}\")").into_lua_err()?;
                    if !name.chars().next().unwrap().is_ascii_digit() {
                        writeln!(define_all_syms, "{name} = CONFIG_{name}").into_lua_err()?;
                    }
                }
            }
            self.lua
                .load(&define_all_syms)
                .set_name("<internal>::define_all_syms")
                .exec()?;

            self.lua.load(&self.code).set_name(&self.filename).exec()?;
            core::result::Result::Ok(())
        })?;

        Ok(())
    }
}
