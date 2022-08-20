/*
 * Helper script to dump the kernel config.
 * - run `make defconfig` in the kernel directory
 * - copy the bridge.c to the kernel directory
 * - build and run it with gcc
 */

use std::collections::HashMap;
use std::error::Error;
use std::ffi::OsString;
use std::fmt::Display;
use std::fs;
use std::io::prelude::*;
use std::os::unix::fs::OpenOptionsExt;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use libloading::os::unix::Symbol as RawSymbol;
use libloading::{Library, Symbol};
use libc::c_int;

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
    cause: Option<std::io::Error>,
}
impl Display for CommandCallError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
        // print cause
        write!(formatter, "{} {:?}", self.msg, self.cause)
    }
}
impl Error for CommandCallError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match &self.cause {
            Some(e) => Some(e),
            None => None,
        }
    }
}

type AddFunc = extern "C" fn(c_int, c_int) -> c_int;
type Env = HashMap<String, String>;

struct BridgeVTable {
    add: RawSymbol<AddFunc>,
}

impl BridgeVTable {
    unsafe fn new(library: &Library) -> BridgeVTable {
        let fn_add: Symbol<AddFunc> = library.get(b"add").unwrap();

        BridgeVTable {
            add: fn_add.into_raw(),
        }
    }
}

pub struct Bridge {
    #[allow(dead_code)]
    library: Library,
    vtable: BridgeVTable,
    pub kernel_dir: PathBuf,
    pub environment: Env,
}

impl Bridge {
    pub fn add(&self, a: c_int, b: c_int) -> c_int {
        let a = (self.vtable.add)(a, b);
        use std::env;
        println!("EEEEEEEEEEEEENV {}", env::var("HOME").unwrap());
        a
    }
}

/// Compile (or find existing) bridge shared library.
pub fn prepare_bridge(kernel_dir: &PathBuf) -> Result<(PathBuf, Env), Box<dyn Error>> {
    let kconfig_dir = kernel_dir.join("scripts").join("kconfig");

    // Copy bridge.c to kernel scripts directory
    fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .mode(0o644)
        .open(&kconfig_dir.join("autokernel_bridge.c"))?
        .write_all(include_bytes!("bridge/bridge.c"))?;

    // This interceptor script is used to run autokernel's bridge with the
    // correct environment variables, which are set by the Makefile.
    //
    // We do this by replacing the shell used internally by the Makefile
    // with our interceptor script. This script will examine all commands
    // run by the Makefile.
    // If it detects that the kernel's "conf" tool is being run by the Makefile
    // (e.g. by make defconfig), it replaces the executed command with a short
    // function that builds the autokernel bridge and returns the required environment.
    //
    // It is necessary that some kind of "conf" tool is being run, as their
    // prerequisite C objects are also required to build our bridge.
    let kconfig_interceptor_sh = kconfig_dir.join("autokernel_interceptor.sh");
    fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .mode(0o755)
        .open(&kconfig_interceptor_sh)?
        .write_all(include_bytes!("bridge/interceptor.sh"))?;

    let interceptor_shell = fs::canonicalize(&kconfig_interceptor_sh)?
        .into_os_string()
        .into_string()
        .map_err(|e| StringConversionError { cause: e })?;

    // Build our bridge by intercepting the final call of a make defconfig invocation.
    let bridge_library = kconfig_dir.join("autokernel_bridge.so");
    let builder_output = Command::new("bash")
        .args(["-c", "--"])
        .arg("umask 022 && make SHELL=\"$INTERCEPTOR_SHELL\" defconfig")
        .env("INTERCEPTOR_SHELL", interceptor_shell)
        .current_dir(&kernel_dir)
        .stderr(Stdio::inherit())
        .output()
        .map_err(|e| CommandCallError {
            msg: "Failed to execute bridge with interceptor".into(),
            cause: Some(e),
        })?;

    let builder_output = String::from_utf8_lossy(&builder_output.stdout).to_string();
    let builder_output = builder_output
        .split_once("[AUTOKERNEL BRIDGE]")
        .unwrap()
        .1;

    let env = serde_json::from_str(builder_output).unwrap();
    Ok((bridge_library, env))
}

/// Compile bridge library if necessary, then dynamically
/// load it and associated functions and create and return a
/// Bridge object to interface with the C part.
pub fn create_bridge(kernel_dir: PathBuf) -> Result<Bridge, Box<dyn Error>> {
    let (library_path, env) = prepare_bridge(&kernel_dir)?;
    unsafe {
        let library = Library::new(library_path).unwrap();
        let vtable = BridgeVTable::new(&library);

        // TODO: we need the env to be correct inside the shared library.
        // TODO: set it initially inside the shared library by modifying the C global variable
        println!("EEEEEEEEEEEEENV {}", env["HOME"]);
        use std::env;
        println!("EEEEEEEEEEEEENV {}", env::var("HOME").unwrap());
        Ok(Bridge{
            library,
            vtable,
            kernel_dir,
            environment: env,
        })
    }
}
