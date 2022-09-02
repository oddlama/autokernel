/*
 * Helper script to dump the kernel config.
 * - run `make defconfig` in the kernel directory
 * - copy the bridge.c to the kernel directory
 * - build and run it with gcc
 */

use anyhow::{ensure, Context, Error, Result};
use libc::{c_char, c_int, c_void, size_t};
use libloading::os::unix::Symbol as RawSymbol;
use libloading::{Library, Symbol as LSymbol};
use std::borrow::Cow;
use std::collections::HashMap;
use std::ffi::{CStr, CString};
use std::fs;
use std::io::prelude::*;
use std::os::unix::fs::OpenOptionsExt;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::rc::Rc;

#[derive(Debug, Eq, PartialEq, Ord, PartialOrd)]
#[repr(u8)]
#[allow(dead_code)]
pub enum Tristate {
    No,
    Mod,
    Yes,
}

#[derive(Debug)]
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
pub struct SymbolValue {
    value: *mut c_void,
    tri: Tristate,
}

#[repr(C)]
pub struct CExprValue {
    expression: *mut c_void,
    tri: Tristate,
}

#[repr(C)]
struct CSymbol {
    next: *const c_void, // Not needed
    name: *const c_char,
    pub symbol_type: SymbolType,
    current_value: SymbolValue,
    default_values: [SymbolValue; 4],
    pub visible: Tristate,
    flags: c_int,
    // TODO where (which type) is this pointing to?
    properties: *mut c_void,
    direct_dependencies: CExprValue,
    reverse_dependencies: CExprValue,
    implied: CExprValue,
}

//pub struct Symbol<'a> {
//    c_symbol: &'a mut CSymbol,
//    vtable: &'a BridgeVTable,
//}
pub struct Symbol<'a> {
    c_symbol: &'a mut CSymbol,
    vtable: Rc<BridgeVTable>,
}

impl Symbol<'_> {
    pub fn name(&self) -> Option<Cow<'_, str>> {
        unsafe {
            self.c_symbol
                .name
                .as_ref()
                .map(|obj| String::from_utf8_lossy(CStr::from_ptr(obj).to_bytes()))
        }
    }
    // dependencies()

    pub fn get_value(&self) -> &Tristate {
        &self.c_symbol.current_value.tri
    }

    #[allow(dead_code)]
    pub fn get_defaults(&self) -> impl Iterator<Item = &Tristate> {
        self.c_symbol.default_values.iter().map(|v| &v.tri)
    }

    pub fn set_symbol_value_tristate(&mut self, value: Tristate) -> Result<()> {
        ensure!(
            (self.vtable.set_symbol_value_tristate)(self.c_symbol, value) == 1,
            format!("Could not set symbol {:?}", self.name())
        );
        Ok(())
    }

    pub fn set_symbol_value_string(&mut self, value: &str) -> Result<()> {
        let cstr = CString::new(value).unwrap();
        ensure!(
            (self.vtable.set_symbol_value_string)(self.c_symbol, cstr.as_ptr()) == 1,
            format!("Could not set symbol {:?}", self.name())
        );
        Ok(())
    }
}

type FuncInit = extern "C" fn(*const *const c_char) -> ();
type FuncSymbolCount = extern "C" fn() -> size_t;
type FuncGetAllSymbols = extern "C" fn(*mut *mut CSymbol) -> ();
type FuncSetSymbolValueTristate = extern "C" fn(*mut CSymbol, Tristate) -> c_int;
type FuncSetSymbolValueString = extern "C" fn(*mut CSymbol, *const c_char) -> c_int;
type EnvironMap = HashMap<String, String>;

struct BridgeVTable {
    init: RawSymbol<FuncInit>,
    symbol_count: RawSymbol<FuncSymbolCount>,
    get_all_symbols: RawSymbol<FuncGetAllSymbols>,
    set_symbol_value_tristate: RawSymbol<FuncSetSymbolValueTristate>,
    set_symbol_value_string: RawSymbol<FuncSetSymbolValueString>,
}

impl BridgeVTable {
    unsafe fn new(library: &Library) -> BridgeVTable {
        let fn_init: LSymbol<FuncInit> = library.get(b"init").unwrap();
        let fn_symbol_count: LSymbol<FuncSymbolCount> = library.get(b"symbol_count").unwrap();
        let fn_get_all_symbols: LSymbol<FuncGetAllSymbols> = library.get(b"get_all_symbols").unwrap();
        let fn_set_symbol_value_tristate: LSymbol<FuncSetSymbolValueTristate> =
            library.get(b"sym_set_tristate_value").unwrap();
        let fn_set_symbol_value_string: LSymbol<FuncSetSymbolValueString> =
            library.get(b"sym_set_string_value").unwrap();

        BridgeVTable {
            init: fn_init.into_raw(),
            symbol_count: fn_symbol_count.into_raw(),
            get_all_symbols: fn_get_all_symbols.into_raw(),
            set_symbol_value_tristate: fn_set_symbol_value_tristate.into_raw(),
            set_symbol_value_string: fn_set_symbol_value_string.into_raw(),
        }
    }

    fn c_symbol_count(&self) -> usize {
        (self.symbol_count)() as usize
    }

    /// needs to make static lifetime of the pointer explicit, otherwise it assumes CSymbol goes
    /// out of scope with the vtable reference that was used to call it
    fn c_get_all_symbols(&self) -> Vec<&'static mut CSymbol> {
        let count = self.c_symbol_count();
        let mut symbols = Vec::with_capacity(count);
        (self.get_all_symbols)(symbols.as_mut_ptr() as *mut *mut CSymbol);
        unsafe { symbols.set_len(count) };
        symbols
    }
}

pub struct Bridge<'a> {
    #[allow(dead_code)]
    library: Library,
    #[allow(dead_code)]
    vtable: Rc<BridgeVTable>,
    pub kernel_dir: PathBuf,

    pub symbols: Vec<Symbol<'a>>,
}

impl<'a> Bridge<'a> {
    /// Compile bridge library if necessary, then dynamically
    /// load it and associated functions and create and return a
    /// Bridge object to interface with the C part.
    pub fn new(kernel_dir: PathBuf) -> Result<Bridge<'static>> {
        // TODO move in Bridge::new
        let (library_path, env) = prepare_bridge(&kernel_dir)?;
        let library = unsafe { Library::new(library_path).unwrap() };
        let vtable = unsafe { BridgeVTable::new(&library) };
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
        (vtable.init)(ffi_env.as_ptr());

        let vtable = Rc::new(vtable);

        // Load all symbols once
        let c_symbols = vtable.c_get_all_symbols();
        let symbols = c_symbols
            .into_iter()
            .map(|s| Symbol {
                c_symbol: s,
                vtable: vtable.clone(),
            })
            .collect();

        Ok(Bridge {
            library,
            vtable,
            kernel_dir,
            symbols,
        })
    }

    #[allow(dead_code)]
    /// TODO This does not work since the whole bridge is still in a mutable borrow state
    pub fn get_symbol_by_name_mut(&mut self, name: &str) -> Option<&'a mut Symbol> {
        let p = self.get_symbol_pos_by_name(name);
        if let Some(pos) = p {
            return Some(&mut self.symbols[pos]);
        }
        None
    }
    pub fn get_symbol_pos_by_name(&self, name: &str) -> Option<usize> {
        self.symbols
            .iter()
            .position(|sym| sym.name().map_or(false, |n| n.eq_ignore_ascii_case(name)))
    }
}

/// Compile (or find existing) bridge shared library.
pub fn prepare_bridge(kernel_dir: &PathBuf) -> Result<(PathBuf, EnvironMap)> {
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
