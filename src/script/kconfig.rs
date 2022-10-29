use bridge::Bridge;
use std::path::Path;

use anyhow::anyhow;
use anyhow::Context;
use anyhow::Result;

use crate::bridge;

use super::Config;
use std::fs;

struct Assignment {
    symbol: String,
    value: String,
    line: usize,
}

pub struct KConfig {
    filename: String,
    assignments: Vec<Assignment>,
}

impl KConfig {
    pub fn new(path: impl AsRef<Path>) -> Result<KConfig> {
        KConfig::from_content(path.as_ref().display().to_string(), fs::read_to_string(path)?)
    }

    pub fn from_content(filename: String, content: String) -> Result<KConfig> {
        let mut assignments = Vec::new();
        for (i, line) in content.lines().enumerate() {
            let line = line.trim();
            if line.is_empty() || line.starts_with("#") {
                continue;
            }
            let (k, v) = line.split_once("=").ok_or(anyhow!(format!("invalid line {line}")))?;
            // TODO trimming all " might not be desired
            // TODO trimming CONFIG on right side should only be done for choice symbols
            assignments.push(Assignment {
                symbol: k.trim().trim_start_matches("CONFIG_").to_string(),
                value: v
                    .trim()
                    .trim_start_matches('"')
                    .trim_end_matches('"')
                    .trim_start_matches("CONFIG_")
                    .to_string(),
                line: i + 1,
            });
        }
        Ok(KConfig { filename, assignments })
    }
}

impl Config for KConfig {
    fn apply_kernel_config(&self, bridge: &Bridge) -> Result<()> {
        for assignment in &self.assignments {
            bridge
                .symbol(&assignment.symbol)
                .with_context(|| format!("could not get symbol {:?}", assignment.symbol))?
                .set_value_tracked(
                    bridge::SymbolValue::Auto(assignment.value.clone()),
                    self.filename.clone(),
                    assignment.line.try_into().unwrap(),
                    None,
                )?;
        }
        Ok(())
    }
}
