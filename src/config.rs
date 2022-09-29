use anyhow::{ensure, Ok, Result};
use serde::Deserialize;
use std::fs;
use std::path::PathBuf;
use toml::value::Map;

use crate::bridge::Bridge;

pub fn load(path: PathBuf) -> Result<Config> {
    let config_str = fs::read_to_string(path)?;
    let config: Config = toml::from_str(config_str.as_str())?;
    Ok(config)
}

/// TOML config
#[derive(Debug, Deserialize)]
pub struct Config {
    pub build: Map<String, toml::Value>,
    pub install: toml::Value,
}

impl Config {
    pub fn validate(&self, bridge: &Bridge) -> Result<usize> {
        for (k, _) in &self.build {
            ensure!(
                bridge.symbol(k).is_some(),
                format!("Key {} does not exist in loaded symbols", &k)
            );
            //TODO validate value in range
        }
        Ok(self.build.len())
    }
}
