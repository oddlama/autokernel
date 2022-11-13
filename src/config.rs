use std::{fs, path::Path};

use anyhow::{Context, Ok, Result};
use colored::Colorize;
use serde::Deserialize;

#[derive(Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct SectionConfigInstall {
    pub enable: bool,
    pub path: String,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SectionConfig {
    pub script: String,
    #[serde(default)]
    pub install: SectionConfigInstall,
}

#[derive(Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct SectionKernelInstall {
    pub enable: bool,
}

#[derive(Deserialize, Default)]
#[serde(default, deny_unknown_fields)]
pub struct SectionKernel {
    pub install: SectionKernelInstall,
}

#[derive(Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct SectionInitramfsInstall {
    pub enable: bool,
    pub path: String,
}

#[derive(Deserialize, Default)]
#[serde(default, deny_unknown_fields)]
pub struct SectionInitramfs {
    pub enable: bool,
    pub builtin: bool,
    pub command: Vec<String>,
    pub install: SectionInitramfsInstall,
}

#[derive(Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct SectionModulesInstall {
    pub enable: bool,
    pub path: String,
}

#[derive(Deserialize, Default)]
#[serde(default, deny_unknown_fields)]
pub struct SectionModules {
    pub install: SectionModulesInstall,
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub config: SectionConfig,
    #[serde(default)]
    pub initramfs: SectionInitramfs,
    #[serde(default)]
    pub kernel: SectionKernel,
    #[serde(default)]
    pub modules: SectionModules,
}

impl Default for SectionConfigInstall {
    fn default() -> Self {
        Self {
            enable: true,
            path: "/boot/config-{KERNEL_VERSION}".to_string(),
        }
    }
}

impl Default for SectionInitramfsInstall {
    fn default() -> Self {
        Self {
            enable: true,
            path: "/boot/initramfs-{KERNEL_VERSION}.img".to_string(),
        }
    }
}

impl Default for SectionKernelInstall {
    fn default() -> Self {
        Self { enable: true }
    }
}

impl Default for SectionModulesInstall {
    fn default() -> Self {
        Self {
            enable: true,
            path: "/".to_string(),
        }
    }
}

pub fn load(path: impl AsRef<Path>) -> Result<Config> {
    println!(
        "{:>12} config ({}) [{} {}]",
        "Loading".green(),
        path.as_ref().display(),
        env!("CARGO_PKG_NAME"),
        env!("CARGO_PKG_VERSION")
    );
    Ok(toml::from_str(&fs::read_to_string(&path).context(format!(
        "Could not read config {}",
        path.as_ref().display()
    ))?)?)
}
