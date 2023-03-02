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

/// Loads the given script file by instanciating the correct implementation
pub fn load(path: impl AsRef<Path>) -> Result<Box<dyn Script>> {
    let ext = path
        .as_ref()
        .extension()
        // If no extension is found, interpret the file name as extension.
        // Happens for files beginning with a . like .config
        .or_else(|| path.as_ref().file_name())
        .expect("Missing file extension")
        .to_str()
        .unwrap();

    Ok(match ext {
        "lua" => Box::new(LuaScript::new(path)?),
        "txt" | "config" | ".config" => Box::new(KConfig::new(path)?),
        _ => bail!(format!("Unknown script type {ext}")),
    })
}

/// Loads and applys the given script file
pub fn apply(path: impl AsRef<Path>, bridge: &Bridge) -> Result<()> {
    println!("{:>12} script ({})", "Applying".green(), path.as_ref().display());
    load(path)?.apply(bridge)
}
