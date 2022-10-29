mod kconfig;
mod lua;
use crate::bridge::Bridge;

use std::path::Path;

use anyhow::{bail, Ok, Result};

use colored::Colorize;
pub use kconfig::KConfig;
pub use lua::LuaScript;

pub trait Script {
    fn apply(&self, bridge: &Bridge) -> Result<()>;
}

/// Loads the given script file by instanciating
/// the correct implementation and applys it
pub fn load(path: impl AsRef<Path>) -> Result<Box<dyn Script>> {
    let ext = path
        .as_ref()
        .extension()
        .expect("Missing file extension")
        .to_str()
        .unwrap();

    Ok(match ext {
        "lua" => Box::new(LuaScript::new(path)?),
        "txt" => Box::new(KConfig::new(path)?),
        _ => bail!(format!("Unknown script type {ext}")),
    })
}

/// Loads and applys the given script file
pub fn apply(path: impl AsRef<Path>, bridge: &Bridge) -> Result<()> {
    println!("{:>12} script ({})", "Applying".green(), path.as_ref().display());
    load(path)?.apply(bridge)
}
