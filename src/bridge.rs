/*
 * Helper script to dump the kernel config.
 * - run `make defconfig` in the kernel directory
 * - copy the bridge.c to the kernel directory
 * - build and run it with gcc
 */

use anyhow::{Context, Error, Result};
use libc::{c_char, c_int, size_t, c_void};
use libloading::os::unix::Symbol as RawSymbol;
use libloading::{Library, Symbol};
use std::collections::HashMap;
use std::ffi::CStr;
use std::borrow::Cow;
use std::fs;
use std::io::prelude::*;
use std::os::unix::fs::OpenOptionsExt;
use std::path::PathBuf;
use std::process::{Command, Stdio};

#[repr(u8)]
#[allow(dead_code)]
pub enum Tristate {
    No,
    Mod,
    Yes,
}

#[repr(u8)]
#[allow(dead_code)]
pub enum SymbolType {
    Unknown,
    Boolean,
    Tristate,
    Int,
    Hex,
    String,
}

#[repr(C)]
pub struct CSymbolValue {
    value: *mut c_void,
    tri: Tristate,
}

#[repr(C)]
pub struct CExprValue {
    expression: *mut c_void,
    tri: Tristate,
}

#[repr(C)]
pub struct CSymbol {
    next: *mut CSymbol,
    name: *const c_char,
    symbol_type: SymbolType,
    current_value: CSymbolValue,
    default_values: [CSymbolValue; 4],
    visible: Tristate,
    flags: c_int,
    properties: *mut c_void,
    direct_dependencies: CExprValue,
    reverse_dependencies: CExprValue,
    implied: CExprValue,
}

impl CSymbol {
    pub fn name(&self) -> Cow<'_, str> {
        unsafe {
            match self.name.as_ref() {
                Some(obj) => String::from_utf8_lossy(CStr::from_ptr(obj).to_bytes()),
                None => Cow::from("(null)"),
            }
        }
    }
}

type FuncInit = extern "C" fn() -> ();
type FuncSymbolCount = extern "C" fn() -> size_t;
type FuncGetAllSymbols = extern "C" fn(*mut *mut CSymbol) -> ();
type Env = HashMap<String, String>;

struct BridgeVTable {
    init: RawSymbol<FuncInit>,
    symbol_count: RawSymbol<FuncSymbolCount>,
    get_all_symbols: RawSymbol<FuncGetAllSymbols>,
}

impl BridgeVTable {
    unsafe fn new(library: &Library) -> BridgeVTable {
        let fn_init: Symbol<FuncInit> = library.get(b"init").unwrap();
        let fn_symbol_count: Symbol<FuncSymbolCount> = library.get(b"symbol_count").unwrap();
        let fn_get_all_symbols: Symbol<FuncGetAllSymbols> = library.get(b"get_all_symbols").unwrap();

        BridgeVTable {
            init: fn_init.into_raw(),
            symbol_count: fn_symbol_count.into_raw(),
            get_all_symbols: fn_get_all_symbols.into_raw(),
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
    pub fn init(&self) {
        (self.vtable.init)();
    }

    pub fn symbol_count(&self) -> usize {
        (self.vtable.symbol_count)() as usize
    }

    pub fn get_all_symbols(&self) -> Vec<*mut CSymbol> {
        let count = self.symbol_count();
        let mut symbols = Vec::with_capacity(count);
        (self.vtable.get_all_symbols)(symbols.as_mut_ptr());
        unsafe { symbols.set_len(count) };
        symbols
    }
}

/// Compile (or find existing) bridge shared library.
pub fn prepare_bridge(kernel_dir: &PathBuf) -> Result<(PathBuf, Env)> {
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
        .map_err(|e| Error::msg(format!("OsString conversion failed for {:?}", e)))?;
    //.with?;

    // Build our bridge by intercepting the final call of a make defconfig invocation.
    let bridge_library = kconfig_dir.join("autokernel_bridge.so");
    let builder_output = Command::new("bash")
        .args(["-c", "--"])
        .arg("umask 022 && make SHELL=\"$INTERCEPTOR_SHELL\" defconfig")
        .env("INTERCEPTOR_SHELL", interceptor_shell)
        .current_dir(&kernel_dir)
        .stderr(Stdio::inherit())
        .output()?;

    let builder_output = String::from_utf8_lossy(&builder_output.stdout).to_string();
    let builder_output = builder_output
        .split_once("[AUTOKERNEL BRIDGE]")
        .context("interceptor output did not containe [AUTOKERNEL BRIDGE]")?
        .1;

    let env = serde_json::from_str(builder_output)?;
    Ok((bridge_library, env))
}

/// Compile bridge library if necessary, then dynamically
/// load it and associated functions and create and return a
/// Bridge object to interface with the C part.
pub fn create_bridge(kernel_dir: PathBuf) -> Result<Bridge> {
    let (library_path, env) = prepare_bridge(&kernel_dir)?;
    unsafe {
        let library = Library::new(library_path).unwrap();
        let vtable = BridgeVTable::new(&library);

        // TODO: this is temporary
        for (key, value) in &env {
            std::env::set_var(key, value)
        }

        // TODO: we need the env to be correct inside the shared library.
        // TODO: set it initially inside the shared library by modifying the C global variable
        let bridge = Bridge {
            library,
            vtable,
            kernel_dir,
            environment: env,
        };
        bridge.init();
        Ok(bridge)
    }
}
