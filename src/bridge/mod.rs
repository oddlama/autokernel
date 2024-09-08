use anyhow::{ensure, Context, Error, Result};
use colored::Colorize;
use libc::c_char;
use std::cell::RefCell;
use std::collections::HashMap;
use std::ffi::{CStr, CString};
use std::io::prelude::*;
use std::os::unix::fs::OpenOptionsExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::Instant;
use std::{fs, io};

pub mod satisfier;
mod transaction;
pub use transaction::*;

mod symbol;
// dont show abstraction to parent modules
pub use symbol::*;

mod expr;
pub use expr::Expr;

pub mod types;
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
    pub fn new(kernel_dir: PathBuf, bash: Option<&str>) -> Result<Bridge> {
        let (library_path, env) = prepare_bridge(&kernel_dir, bash)
            .context(format!("Could not prepare bridge in {}", kernel_dir.display()))?;

        let time_start = Instant::now();
        print!("{:>12} bridge\r", "Initializing".cyan());
        io::stdout().flush().unwrap();

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
        ensure!((vtable.c_init)(ffi_env.as_ptr()), "Failed to initialize C bridge");

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

        let bridge = Bridge {
            vtable,
            kernel_dir,
            symbols,
            name_to_symbol,
            history: RefCell::new(Vec::new()),
        };
        let n_valid_symbols = bridge
            .symbols
            .iter()
            .filter(|s| !unsafe { &***s }.name.is_null() && !unsafe { &***s }.flags.intersects(SymbolFlags::CONST))
            .count();
        println!(
            "{:>12} bridge [kernel {}, {} symbols] in {:.2?}",
            "Initialized".green(),
            bridge.get_env("KERNELVERSION").unwrap(),
            n_valid_symbols,
            time_start.elapsed()
        );
        Ok(bridge)
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
        let c: CString = CString::new(path.as_ref().to_str().context("Invalid filename")?)?;
        ensure!((self.vtable.c_conf_write)(c.as_ptr()) == 0, "Could not write config");
        Ok(())
    }

    pub fn read_config_unchecked(&self, path: impl AsRef<Path>) -> Result<()> {
        let c: CString = CString::new(path.as_ref().to_str().context("Invalid filename")?)?;
        ensure!(
            (self.vtable.c_conf_read_unchecked)(c.as_ptr()) == 0,
            "Error while executing conf_read({:?}). Is the file accessible?",
            path.as_ref()
        );
        Ok(())
    }

    pub fn get_env(&self, name: &str) -> Option<String> {
        let param = CString::new(name).unwrap();
        let ret = (self.vtable.c_get_env)(param.as_ptr());
        if ret.is_null() {
            None
        } else {
            Some(unsafe { CStr::from_ptr(ret) }.to_str().unwrap().to_owned())
        }
    }
}

/// Compile (or find existing) bridge shared library.
fn prepare_bridge(kernel_dir: &PathBuf, bash: Option<&str>) -> Result<(PathBuf, EnvironMap)> {
    let time_start = Instant::now();
    let kconfig_dir = kernel_dir.join("scripts").join("kconfig");

    // Copy bridge.c to kernel scripts directory
    let kconfig_bridge_c = kconfig_dir.join("autokernel_bridge.c");
    fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .mode(0o644)
        .open(&kconfig_bridge_c)
        .context(format!("Could not open {}", kconfig_bridge_c.display()))?
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
    let mut interceptor_file = fs::OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .mode(0o755)
        .open(&kconfig_interceptor_sh)
        .context(format!("Could not open {}", kconfig_interceptor_sh.display()))?;

    let shebang = format!("#!{}\n", bash.unwrap_or("/usr/bin/env bash"));
    interceptor_file.write_all(shebang.as_bytes())?;
    interceptor_file.write_all(include_bytes!("cbridge/interceptor.sh"))?;
    interceptor_file.flush()?;
    drop(interceptor_file);

    let interceptor_shell = fs::canonicalize(&kconfig_interceptor_sh)?
        .into_os_string()
        .into_string()
        .map_err(|e| Error::msg(format!("OsString conversion failed for {:?}", e)))?;

    // Build our bridge by intercepting the final call of a make defconfig invocation.
    print!("{:>12} bridge for {}\r", "Building".cyan(), kernel_dir.display());
    io::stdout().flush().unwrap();
    let bridge_library = kconfig_dir.join("autokernel_bridge.so");
    let builder_output = Command::new("bash")
        .args(["-c", "--"])
        .arg("umask 022 && make SHELL=\"$INTERCEPTOR_SHELL\" defconfig")
        .env("INTERCEPTOR_SHELL", interceptor_shell)
        .current_dir(kernel_dir)
        .stderr(Stdio::inherit())
        .output()?;
    ensure!(builder_output.status.success());

    let builder_output = String::from_utf8_lossy(&builder_output.stdout).to_string();
    let builder_output = builder_output
        .split_once("[AUTOKERNEL BRIDGE]")
        .context("Interceptor output did not contain [AUTOKERNEL BRIDGE]")?
        .1;

    let env = serde_json::from_str(builder_output)?;
    println!(
        "{:>12} bridge for {} in {:.2?}",
        "Built".green(),
        kernel_dir.display(),
        time_start.elapsed()
    );
    Ok((bridge_library, env))
}
