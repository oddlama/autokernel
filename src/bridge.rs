use anyhow::{ensure, Context, Error, Result};
use internal::*;
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

mod internal {
    use super::*;
    use libc::{c_char, c_int, c_void};

    #[repr(C)]
    pub struct SymbolValue {
        value: *mut c_void,
        pub tri: Tristate,
    }

    #[repr(C)]
    struct CExprValue {
        expression: *mut c_void,
        tri: Tristate,
    }

    #[repr(C)]
    pub struct CSymbol {
        next: *const c_void, // Not needed
        pub name: *const c_char,
        pub symbol_type: SymbolType,
        pub current_value: SymbolValue,
        default_values: [SymbolValue; 4],
        pub visible: Tristate,
        flags: c_int,
        // TODO where (which type) is this pointing to?
        properties: *mut c_void,
        direct_dependencies: CExprValue,
        reverse_dependencies: CExprValue,
        implied: CExprValue,
    }
}

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

pub struct Symbol {
    c_symbol: *mut CSymbol,
    vtable: Rc<BridgeVTable>,
}

impl Symbol {
    pub fn name(&self) -> Option<Cow<'_, str>> {
        unsafe {
            (*self.c_symbol)
                .name
                .as_ref()
                .map(|obj| String::from_utf8_lossy(CStr::from_ptr(obj).to_bytes()))
        }
    }
    // dependencies()

    pub fn get_value(&self) -> &Tristate {
        unsafe { &(*self.c_symbol).current_value.tri }
    }

    pub fn set_symbol_value_tristate(&mut self, value: Tristate) -> Result<()> {
        ensure!(
            (self.vtable.c_sym_set_tristate_value)(self.c_symbol, value) == 1,
            format!("Could not set symbol {:?}", self.name())
        );
        // TODO this must be called on all symbols.
        (self.vtable.c_sym_calc_value)(self.c_symbol);
        Ok(())
    }

    pub fn set_symbol_value_string(&mut self, value: &str) -> Result<()> {
        let cstr = CString::new(value).unwrap();
        ensure!(
            (self.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr()) == 1,
            format!("Could not set symbol {:?}", self.name())
        );
        // TODO this must be called on all symbols.
        (self.vtable.c_sym_calc_value)(self.c_symbol);
        Ok(())
    }
}

type FuncInit = extern "C" fn(*const *const c_char) -> ();
type FuncSymbolCount = extern "C" fn() -> size_t;
type FuncGetAllSymbols = extern "C" fn(*mut *mut CSymbol) -> ();
type FuncSetSymbolValueTristate = extern "C" fn(*mut CSymbol, Tristate) -> c_int;
type FuncSetSymbolValueString = extern "C" fn(*mut CSymbol, *const c_char) -> c_int;
type FuncSymbolCalcValue = extern "C" fn(*mut CSymbol) -> c_void;
type EnvironMap = HashMap<String, String>;

struct BridgeVTable {
    #[allow(dead_code)]
    library: Library,
    c_init: RawSymbol<FuncInit>,
    c_symbol_count: RawSymbol<FuncSymbolCount>,
    c_get_all_symbols: RawSymbol<FuncGetAllSymbols>,
    c_sym_set_tristate_value: RawSymbol<FuncSetSymbolValueTristate>,
    c_sym_set_string_value: RawSymbol<FuncSetSymbolValueString>,
    c_sym_calc_value: RawSymbol<FuncSymbolCalcValue>,
}

impl BridgeVTable {
    unsafe fn new(library_path: PathBuf) -> BridgeVTable {
        let library = Library::new(&library_path).unwrap();
        macro_rules! load_symbol {
            ($type: ty, $name: expr) => {
                (library.get($name).unwrap() as LSymbol<$type>).into_raw() as RawSymbol<$type>
            };
        }

        let c_init = load_symbol!(FuncInit, b"init");
        let c_symbol_count = load_symbol!(FuncSymbolCount, b"symbol_count");
        let c_get_all_symbols = load_symbol!(FuncGetAllSymbols, b"get_all_symbols");
        let c_sym_set_tristate_value = load_symbol!(FuncSetSymbolValueTristate, b"sym_set_tristate_value");
        let c_sym_set_string_value = load_symbol!(FuncSetSymbolValueString, b"sym_set_string_value");
        let c_sym_calc_value = load_symbol!(FuncSymbolCalcValue, b"sym_calc_value");

        BridgeVTable {
            library,
            c_init,
            c_symbol_count,
            c_get_all_symbols,
            c_sym_set_tristate_value,
            c_sym_set_string_value,
            c_sym_calc_value,
        }
    }

    fn symbol_count(&self) -> usize {
        (self.c_symbol_count)() as usize
    }

    /// needs to make static lifetime of the pointer explicit, otherwise it assumes CSymbol goes
    /// out of scope with the vtable reference that was used to call it
    fn get_all_symbols(&self) -> Vec<*mut CSymbol> {
        let count = self.symbol_count();
        let mut symbols = Vec::with_capacity(count);
        (self.c_get_all_symbols)(symbols.as_mut_ptr() as *mut *mut CSymbol);
        unsafe { symbols.set_len(count) };
        symbols
    }
}

pub struct Bridge {
    #[allow(dead_code)]
    vtable: Rc<BridgeVTable>,
    pub kernel_dir: PathBuf,

    pub symbols: Vec<*mut CSymbol>,
    pub name_to_symbol: HashMap<String, *mut CSymbol>,
}

impl Bridge {
    /// Compile bridge library if necessary, then dynamically
    /// load it and associated functions and create and return a
    /// Bridge object to interface with the C part.
    pub fn new(kernel_dir: PathBuf) -> Result<Bridge> {
        let (library_path, env) = prepare_bridge(&kernel_dir)?;
        let vtable = unsafe { BridgeVTable::new(library_path) };
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

        let vtable = Rc::new(vtable);

        // Load all symbols once
        let symbols = vtable.get_all_symbols();
        let mut name_to_symbol = HashMap::new();
        for symbol in &symbols {
            let name = unsafe {
                (**symbol)
                    .name
                    .as_ref()
                    .map(|obj| String::from_utf8_lossy(CStr::from_ptr(obj).to_bytes()).into_owned())
            };
            if let Some(name) = name {
                name_to_symbol.insert(name, *symbol);
            }
        }

        Ok(Bridge {
            vtable,
            kernel_dir,
            symbols,
            name_to_symbol,
        })
    }

    fn wrap_symbol(&self, symbol: *mut CSymbol) -> Symbol {
        Symbol {
            c_symbol: symbol,
            vtable: self.vtable.clone(),
        }
    }

    pub fn symbol(&self, name: &str) -> Option<Symbol> {
        self.name_to_symbol.get(name).map(|s| self.wrap_symbol(*s))
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
