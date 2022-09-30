use anyhow::{anyhow, ensure, Ok, Result};
use indexmap::map::IndexMap;
use std::fs;
use std::path::Path;

use crate::bridge::Bridge;

pub fn load(path: impl AsRef<Path>) -> Result<Config> {
    let mut c = Config { build: IndexMap::new() };
    for line in fs::read_to_string(path)?.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with("#") {
            continue;
        }
        let (k, v) = line.split_once("=").ok_or(anyhow!(format!("invalid line {line}")))?;
        // TODO trimming all " might not be desired
        // TODO trimming CONFIG on right side should only be done for choice symbols
        c.build.insert(
            k.trim().trim_start_matches("CONFIG_").to_string(),
            v.trim()
                .trim_start_matches('"')
                .trim_end_matches('"')
                .trim_start_matches("CONFIG_")
                .to_string(),
        );
    }
    Ok(c)
}

#[derive(Debug)]
pub struct Config {
    pub build: IndexMap<String, String>,
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
