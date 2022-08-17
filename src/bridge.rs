/*
 * Helper script to dump the kernel config.
 * - run `make defconfig` in the kernel directory
 * - copy the bridge.c to the kernel directory
 * - build and run it with gcc
 */

use crate::kconfig_types::*;
use serde::Deserialize;
use serde_json::Deserializer;
use std::io::prelude::*;
use std::error::Error;
use std::ffi::OsString;
use std::fmt::Display;
use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::os::unix::fs::OpenOptionsExt;

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

pub fn run_bridge(
    kernel_dir: PathBuf,
) -> Result<Symbols, Box<dyn Error>> {
    let kconfig_dir = kernel_dir.join("scripts").join("kconfig");

    // Create bridge.c in kernel scripts directory
    fs::OpenOptions::new()
        .create(true).write(true).mode(0o644)
        .open(&kconfig_dir.join("autokernel_bridge.c"))?
        .write_all(include_str!("bridge/bridge.c").as_bytes())?;

    // Create base64.h in kernel scripts directory
    fs::OpenOptions::new()
        .create(true).write(true).mode(0o644)
        .open(&kconfig_dir.join("base64.h"))?
        .write_all(include_str!("bridge/base64.h").as_bytes())?;

    // This interceptor script is used to run autokernel's bridge with the
    // correct environment variables, which are set by the Makefile.
    //
    // We do this by replacing the shell used internally by the Makefile
    // with our interceptor script. This script will examine all commands
    // run by the Makefile.
    // If it detects that the kernel's "conf" tool is being run by the Makefile
    // (e.g. by make defconfig), it replaces the executed command with a short
    // function that builds and runs the autokernel bridge.
    //
    // It is necessary that some kind of "conf" tool is being run, as their
    // prerequisite C objects are also required to build our bridge.
    let kconfig_interceptor_sh = kconfig_dir.join("autokernel_interceptor.sh");
    fs::OpenOptions::new()
        .create(true).write(true).mode(0o755)
        .open(&kconfig_interceptor_sh)?
        .write_all(include_str!("bridge/interceptor.sh").as_bytes())?;

    let interceptor_shell = fs::canonicalize(&kconfig_interceptor_sh)?
        .into_os_string().into_string()
        .map_err(|e| StringConversionError { cause: e })?;

    // Build and run our bridge by intercepting the final call of a make defconfig invocation.
    let bridge_output = Command::new("bash")
        .args(["-c", "--"])
        .arg("umask 022 && make SHELL=\"$INTERCEPTOR_SHELL\" defconfig")
        .env("INTERCEPTOR_SHELL", interceptor_shell)
        .current_dir(&kernel_dir)
        .stderr(Stdio::inherit())
        .output()
        .map_err(|e| CommandCallError {
            msg: "Failed to execute bridge with interceptor".into(),
            cause: e,
        })?;

    let bridge_output = String::from_utf8_lossy(&bridge_output.stdout).to_string();
    let bridge_output = bridge_output.split_once("---- AUTOKERNEL BRIDGE BEGIN ----").unwrap().1;

    // Deserialize received symbols
    let mut deserializer = Deserializer::from_str(bridge_output);
    deserializer.disable_recursion_limit();
    let symbols: Symbols = Symbols::deserialize(&mut deserializer)?;
    Ok(symbols)
}
