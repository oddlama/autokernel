/*
 * Helper script to dump the kernel config.
 * - run `make defconfig` in the kernel directory
 * - copy the bridge.c to the kernel directory
 * - build and run it with gcc
 */

use crate::kconfig_types::*;
use serde::Deserialize;
use serde_json::Deserializer;
use std::collections::HashMap;
use std::env;
use std::error::Error;
use std::ffi::OsString;
use std::fmt::Display;
use std::fs;
use std::path::PathBuf;
use std::process::Command;

#[derive(Debug)]
struct StringConversionError {
    cause: OsString,
}
impl Display for StringConversionError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
        // print cause
        write!(
            formatter,
            "failed to convert  OsString to String: {}",
            self.cause.to_string_lossy()
        )
    }
}
impl Error for StringConversionError {}

#[derive(Debug)]
struct CommandCallError {
    msg: String,
    cause: std::io::Error,
}
impl Display for CommandCallError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
        // print cause
        write!(formatter, "{} {}", self.msg, self.cause)
    }
}
impl Error for CommandCallError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        Some(&self.cause)
    }
}

fn create_environment(
    kernel_dir: &PathBuf,
) -> Result<HashMap<String, String>, Box<dyn Error>> {
    let abs_kernel_dir = fs::canonicalize(&kernel_dir)?
        .into_os_string()
        .into_string()
        .map_err(|e| StringConversionError { cause: e })?;
    Ok(HashMap::from([
        ("CC".to_string(), "gcc".to_string()),
        ("SRCARCH".to_string(), "x86".to_string()),
        ("LD".to_string(), "ld".to_string()),

        ("abs_objtree".to_string(), abs_kernel_dir.clone()),
        ("abs_srctree".to_string(), abs_kernel_dir),
        ("obj".to_string(), "scripts/kconfig".to_string()),
        ("objtree".to_string(), ".".to_string()),
        ("srctree".to_string(), ".".to_string()),
        ("CPP".to_string(), "gcc -E".to_string()),
        ("INSTALLKERNEL".to_string(), "installkernel".to_string()),
        ("KBZIP2".to_string(), "bzip2".to_string()),
        ("KCONFIG_CONFIG".to_string(), ".config".to_string()),
        ("KCONFIG_DEFCONFIG_LIST".to_string(), "/lib/modules/5.19.1-arch1-1/.config /etc/kernel-config /boot/config-5.19.1-arch1-1 arch/x86/configs/x86_64_defconfig".to_string()),
        ("KERNELRELEASE".to_string(), "".to_string()),
        ("KERNELVERSION".to_string(), "5.19.1".to_string()),
        ("LDFLAGS_MODULE".to_string(), "".to_string()),

        // TODO: check whether we can extrace those from the makefile
        // by running a command via the makefile.
    ]))
}

pub fn run_bridge(
    kernel_dir: PathBuf,
) -> Result<Symbols, Box<dyn Error>> {
    let build_env = create_environment(&kernel_dir)?;
    let kconfig_dir = kernel_dir.join("scripts").join("kconfig");

    // TODO: warn if .config is present, toml option and cmdline option to force this

    // Create a defconfig .config file
    Command::new("make")
        .arg("defconfig")
        .current_dir(&kernel_dir)
        .envs(&build_env)
        .status()
        .map_err(|e| CommandCallError {
            msg: "failed to make clean".into(),
            cause: e,
        })?;

    // Create bridge.c in kernel scripts directory
    let kconfig_bridge_c = kconfig_dir.join("bridge.c");
    fs::write(&kconfig_bridge_c, include_str!("bridge/bridge.c")).map_err(|e| {
        CommandCallError {
            msg: format!("failed to create {}", kconfig_bridge_c.display()),
            cause: e,
        }
    })?;

    // Create base64.h in kernel scripts directory
    let kconfig_base64_h = kconfig_dir.join("base64.h");
    fs::write(&kconfig_base64_h, include_str!("bridge/base64.h")).map_err(|e| {
        CommandCallError {
            msg: format!("failed to create {}", kconfig_base64_h.display()),
            cause: e,
        }
    })?;

    let kconfig_dir = kconfig_dir.strip_prefix(&kernel_dir).unwrap();

    // Execute this gcc command in the kconfig_dir
    Command::new("gcc")
        .current_dir(&kernel_dir)
        .arg("-g")
        .arg("-fsanitize=address")
        .arg("-Wp,-MMD,scripts/kconfig/.bridge.o.d")
        .arg("-Wall")
        .arg("-Wstrict-prototypes")
        .arg("-O2")
        .arg("-fomit-frame-pointer")
        .arg("-std=gnu89")
        .arg("-D_DEFAULT_SOURCE")
        .arg("-D_XOPEN_SOURCE=600")
        .arg("-c")
        .arg("-o")
        .arg("scripts/kconfig/bridge.o")
        .arg("scripts/kconfig/bridge.c")
        .envs(&build_env)
        .status()
        .map_err(|e| CommandCallError {
            msg: "failed to build bridge.o".into(),
            cause: e,
        })?;

    // Then execute this gcc command in the kconfig_dir
    Command::new("gcc")
        .arg("-g")
        .arg("-fsanitize=address")
        .arg("-o")
        .arg(kconfig_dir.join("bridge"))
        .arg(kconfig_dir.join("bridge.o"))
        .arg(kconfig_dir.join("confdata.o"))
        .arg(kconfig_dir.join("expr.o"))
        .arg(kconfig_dir.join("lexer.lex.o"))
        .arg(kconfig_dir.join("menu.o"))
        .arg(kconfig_dir.join("parser.tab.o"))
        .arg(kconfig_dir.join("preprocess.o"))
        .arg(kconfig_dir.join("symbol.o"))
        .arg(kconfig_dir.join("util.o"))
        .envs(&build_env)
        .current_dir(&kernel_dir)
        .status()
        .map_err(|e| CommandCallError {
            msg: "failed to build bridge".into(),
            cause: e,
        })?;

    // Then execute the bridge in the kconfig_dir
    // Parse command output as json with serde
    let bridge = Command::new(kconfig_dir.join("bridge"))
        .arg("Kconfig")
        .arg(env::current_dir()?.join("/dev/null"))
        .envs(&build_env)
        .current_dir(kernel_dir)
        .output()
        .map_err(|e| CommandCallError {
            msg: "failed to execute bridge".into(),
            cause: e,
        })?;

    let bridge = String::from_utf8_lossy(&bridge.stdout).to_string();

    let mut deserializer = Deserializer::from_str(&bridge);
    deserializer.disable_recursion_limit();
    let symbols: Symbols = Symbols::deserialize(&mut deserializer)?;
    Ok(symbols)
}
