use anyhow::{anyhow, ensure, Ok, Result};
use indexmap::map::IndexMap;
use std::fs;
use std::path::Path;

use crate::bridge::Bridge;

pub fn load<P>(path: P) -> Result<Config>
where
    P: AsRef<Path>,
{
    let mut c = Config { build: IndexMap::new() };
    for line in fs::read_to_string(path)?.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with("#") {
            continue;
        }
        let (k, v) = line.split_once("=").ok_or(anyhow!(format!("invalid line {line}")))?;
        // TODO trimming all " might not be desired
        c.build
            .insert(k.trim().to_string(), v.trim_matches('"').trim().to_string());
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
