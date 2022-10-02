mod kconfig;
mod lua;
use crate::bridge::Bridge;

use std::path::Path;

use anyhow::{bail, Ok, Result};

pub use kconfig::KConfig;
pub use lua::LuaConfig;

pub trait Config {
    fn apply_kernel_config(&self, bridge: &Bridge) -> Result<()>;
}

/// Loads the given configuration file by instanciating
/// the correct Config implementation
pub fn load(path: impl AsRef<Path>) -> Result<Box<dyn Config>> {
    println!("Loading config: {}", path.as_ref().display());
    let ext = path
        .as_ref()
        .extension()
        .expect("Missing file extension")
        .to_str()
        .unwrap();

    Ok(match ext {
        "lua" => Box::new(LuaConfig::new(path)?),
        "txt" => Box::new(KConfig::new(path)?),
        _ => bail!(format!("Unknown configuration type {ext}")),
    })
}
