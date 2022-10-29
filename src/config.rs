use std::{fs, path::Path};

use anyhow::{Ok, Result};
use colored::Colorize;
use serde::Deserialize;

#[derive(Deserialize, Default)]
#[serde(default)]
pub struct SectionKernel {
    pub script: String,
}

#[derive(Deserialize, Default)]
#[serde(default)]
pub struct SectionInitramfs {
    pub enable: bool,
    pub command: Vec<String>,
}

#[derive(Deserialize, Default)]
#[serde(default)]
pub struct SectionInstall {
    pub enable: bool,
}

#[derive(Deserialize)]
pub struct Config {
    pub kernel: SectionKernel,
    pub initramfs: SectionInitramfs,
    pub install: SectionInstall,
}

pub fn load(path: impl AsRef<Path>) -> Result<Config> {
    println!(
        "{:>12} config ({}) [{} {}]",
        "Loading".green(),
        path.as_ref().display(),
        env!("CARGO_PKG_NAME"),
        env!("CARGO_PKG_VERSION")
    );
    Ok(toml::from_str(&fs::read_to_string(path)?)?)
}
