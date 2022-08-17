use serde::Deserialize;
use std::fs;
use std::error::Error;
use std::path::PathBuf;

pub fn load(path: PathBuf) -> Result<Config, Box<dyn Error>> {
    let config_str = fs::read_to_string(path)?;
    let config: Config = toml::from_str(config_str.as_str())?;
    Ok(config)
}

/// TOML config
#[derive(Debug, Deserialize)]
pub struct Config {
    pub build: toml::Value,
    pub install: toml::Value,
}
