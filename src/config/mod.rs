mod lua;
use crate::bridge::Bridge;

use std::fs;
use std::path::Path;

use anyhow::{anyhow, bail, Ok, Result};
use indexmap::map::IndexMap;

pub trait Config {
    fn apply_kernel_config(&self, bridge: &Bridge) -> Result<()>;
}

pub fn parse_kconfig(path: impl AsRef<Path>) -> Result<IndexMap<String, String>> {
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

    let ctor = match ext {
        "lua" => lua::LuaConfig::new,
        _ => bail!(format!("Unknown configuration type {ext}")),
    };

    Ok(Box::new(ctor(path)?))
}
