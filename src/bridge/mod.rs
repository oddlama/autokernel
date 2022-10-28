use anyhow::{ensure, Context, Error, Result};
use libc::c_char;
use std::cell::RefCell;
use std::collections::HashMap;
use std::ffi::{CStr, CString};
use std::fs;
use std::io::prelude::*;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

pub mod satisfier;
mod transaction;
pub use transaction::*;

mod symbol;
// dont show abstraction to parent modules
pub use symbol::*;

mod expr;
pub use expr::Expr;

mod types;
use types::*;
pub use types::{SymbolValue, Tristate};

mod vtable;
use vtable::*;

#[derive(Debug)]
pub struct Bridge {
    #[allow(dead_code)]
    vtable: BridgeVTable,
    pub kernel_dir: PathBuf,

    pub history: RefCell<Vec<Transaction>>,

    pub symbols: Vec<*mut CSymbol>,
    pub name_to_symbol: HashMap<String, *mut CSymbol>,
}

impl Bridge {
    /// Compile bridge library if necessary, then dynamically
    /// load it and associated functions and create and return a
    /// Bridge object to interface with the C part.
    pub fn new(kernel_dir: PathBuf) -> Result<Bridge> {
        let (library_path, env) = prepare_bridge(&kernel_dir)?;
        let vtable = unsafe { BridgeVTable::new(library_path)? };
        // Create env vector
        let env: Vec<CString> = env
            .iter()
            .map(|(k, v)| {
                CString::new(format!("{}={}", k, v)).expect("Could not convert environment variable to CString")
            })
            .collect();

        // Create vector of ptrs with NULL at the end
        let mut ffi_env: Vec<*const c_char> = env.iter().map(|cstr| cstr.as_ptr()).collect();
        ffi_env.push(std::ptr::null());
        (vtable.c_init)(ffi_env.as_ptr());

        // Load all symbols once
        let symbols = vtable.get_all_symbols();
        let mut name_to_symbol = HashMap::new();
        for symbol in &symbols {
            // Skip symbols that have no type (this seems to apply to symbols that just
            // refer to values for other symbols)
            if unsafe { (**symbol).symbol_type } == SymbolType::Unknown {
                continue;
            }

            if let Some(name) = unsafe { (**symbol).name().map(|obj| obj.into_owned()) } {
                name_to_symbol.insert(name, *symbol);
            }
        }

        Ok(Bridge {
            vtable,
            kernel_dir,
            symbols,
            name_to_symbol,
            history: RefCell::new(Vec::new()),
        })
    }

    pub fn wrap_symbol(&self, symbol: *mut CSymbol) -> Symbol {
        Symbol {
            c_symbol: symbol,
            bridge: self,
        }
    }

    pub fn symbol(&self, name: &str) -> Option<Symbol> {
        self.name_to_symbol.get(name).map(|s| self.wrap_symbol(*s))
    }

    /// Saves all modified (unsaved) values
    /// Iterates over all symbols and recalculates them
    pub fn recalculate_all_symbols(&self) {
        //iterate
        for symbol in &self.symbols {
            // skip constant symbols (Can't be changed)
            if unsafe { &**symbol }.flags.intersects(SymbolFlags::CONST) {
                continue;
            }
            //wrap
            let symbol = self.wrap_symbol(*symbol);
            //skip unnamed
            if symbol.name().is_none() {
                continue;
            }
            //recalculate
            symbol.recalculate();
        }
    }

    pub fn write_config(&self, path: impl AsRef<Path>) -> Result<()> {
        println!("Writing {}...", path.as_ref().display());
        let c: CString = CString::new(path.as_ref().to_str().context("Invalid filename")?)?;
        ensure!((self.vtable.c_conf_write)(c.as_ptr()) == 0, "Could not write config");
        Ok(())
    }

    pub fn read_config_unchecked(&self, path: impl AsRef<Path>) -> Result<()> {
        println!("Reading unchecked {}...", path.as_ref().display());
        let c: CString = CString::new(path.as_ref().to_str().context("Invalid filename")?)?;
        ensure!(
            (self.vtable.c_conf_read_unchecked)(c.as_ptr()) == 0,
            "Could not read config unchecked"
        );
        Ok(())
    }

    pub fn get_env(&self, name: &str) -> String {
        let param = CString::new(name).unwrap();
        return unsafe { CStr::from_ptr((self.vtable.c_get_env)(param.as_ptr())) }
            .to_str()
            .unwrap()
            .to_owned();
    }
}

/// Compile (or find existing) bridge shared library.
fn prepare_bridge(kernel_dir: &PathBuf) -> Result<(PathBuf, EnvironMap)> {
    let kconfig_dir = kernel_dir.join("scripts").join("kconfig");

    // Copy bridge.c to kernel scripts directory
    fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .mode(0o644)
        .open(&kconfig_dir.join("autokernel_bridge.c"))?
        .write_all(include_bytes!("cbridge/bridge.c"))?;

    // This interceptor script is used to run autokernel's bridge with the
    // correct environment variables, which are set by the Makefile.
    //
    // We do this by replacing the shell (bash) used internally by the Makefile
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
        .write_all(include_bytes!("cbridge/interceptor.sh"))?;

    let interceptor_shell = fs::canonicalize(&kconfig_interceptor_sh)?
        .into_os_string()
        .into_string()
        .map_err(|e| Error::msg(format!("OsString conversion failed for {:?}", e)))?;

    // Build our bridge by intercepting the final call of a make defconfig invocation.
    println!("Building bridge for {}", kernel_dir.display());
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
        .context("Interceptor output did not contain [AUTOKERNEL BRIDGE]")?
        .1;

    let env = serde_json::from_str(builder_output)?;
    Ok((bridge_library, env))
}
