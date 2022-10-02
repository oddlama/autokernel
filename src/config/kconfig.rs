use bridge::Bridge;
use bridge::SymbolValue;
use std::path::Path;
use std::str::Lines;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;

use crate::bridge;

use super::Config;
use indexmap::map::IndexMap;
use std::fs;

pub struct KConfig {
    config: IndexMap<String, String>,
}

impl KConfig {
    pub fn new(path: impl AsRef<Path>) -> Result<KConfig> {
        KConfig::from_lines(fs::read_to_string(path)?.lines())
    }

    pub fn from_lines<'a>(lines: impl Into<Lines<'a>>) -> Result<KConfig> {
        let mut map = IndexMap::new();
        for line in lines.into() {
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
        Ok(KConfig { config: map })
    }
}

impl Config for KConfig {
    fn apply_kernel_config(&self, bridge: &Bridge) -> Result<()> {
        for (k, v) in &self.config {
            bridge
                .symbol(k)
                .with_context(|| format!("could not get symbol {:?}", k))?
                .set_symbol_value(SymbolValue::Auto(v.clone()))?;
        }
        Ok(())
    }
}
