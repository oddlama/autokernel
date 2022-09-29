use super::symbol::*;
use super::types::*;
use libc::{c_char, c_int, c_void, size_t};
use libloading::os::unix::Symbol as RawSymbol;
use libloading::{Library, Symbol as LSymbol};
use std::collections::HashMap;
use std::path::PathBuf;

pub type FuncInit = extern "C" fn(*const *const c_char) -> ();
pub type FuncSymbolCount = extern "C" fn() -> size_t;
pub type FuncGetAllSymbols = extern "C" fn(*mut *mut CSymbol) -> ();
pub type FuncSetSymbolValueTristate = extern "C" fn(*mut CSymbol, Tristate) -> c_int;
pub type FuncSetSymbolValueString = extern "C" fn(*mut CSymbol, *const c_char) -> c_int;
pub type FuncSymbolCalcValue = extern "C" fn(*mut CSymbol) -> c_void;
pub type EnvironMap = HashMap<String, String>;

pub struct BridgeVTable {
    #[allow(dead_code)]
    library: Library,
    pub c_init: RawSymbol<FuncInit>,
    pub c_symbol_count: RawSymbol<FuncSymbolCount>,
    pub c_get_all_symbols: RawSymbol<FuncGetAllSymbols>,
    pub c_sym_set_tristate_value: RawSymbol<FuncSetSymbolValueTristate>,
    pub c_sym_set_string_value: RawSymbol<FuncSetSymbolValueString>,
    pub c_sym_calc_value: RawSymbol<FuncSymbolCalcValue>,
}

impl BridgeVTable {
    pub unsafe fn new(library_path: PathBuf) -> BridgeVTable {
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

    pub fn symbol_count(&self) -> usize {
        (self.c_symbol_count)() as usize
    }

    /// needs to make static lifetime of the pointer explicit, otherwise it assumes CSymbol goes
    /// out of scope with the vtable reference that was used to call it
    pub fn get_all_symbols(&self) -> Vec<*mut CSymbol> {
        let count = self.symbol_count();
        let mut symbols = Vec::with_capacity(count);
        (self.c_get_all_symbols)(symbols.as_mut_ptr() as *mut *mut CSymbol);
        unsafe { symbols.set_len(count) };
        symbols
    }
}
