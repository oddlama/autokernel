use super::types::*;
use anyhow::{Ok, Result};
use libc::{c_char, c_int, c_void, size_t};
use libloading::os::unix::Symbol as RawSymbol;
use libloading::{Library, Symbol as LSymbol};
use std::collections::HashMap;
use std::path::PathBuf;

pub type EnvironMap = HashMap<String, String>;
pub type FuncInit = extern "C" fn(*const *const c_char) -> bool;
pub type FuncGetEnv = extern "C" fn(*const c_char) -> *const c_char;
pub type FuncSymbolCount = extern "C" fn() -> size_t;
pub type FuncGetAllSymbols = extern "C" fn(*mut *mut CSymbol) -> ();
pub type FuncGetChoiceSymbols = extern "C" fn(*mut CSymbol, *mut *mut CSymbol) -> size_t;
pub type FuncSymSetTristateValue = extern "C" fn(*mut CSymbol, Tristate) -> bool;
pub type FuncSymSetStringValue = extern "C" fn(*mut CSymbol, *const c_char) -> bool;
pub type FuncSymGetStringValue = extern "C" fn(*mut CSymbol) -> *const c_char;
pub type FuncSymCalcValue = extern "C" fn(*mut CSymbol) -> c_void;
pub type FuncSymIntGetMin = extern "C" fn(*mut CSymbol) -> u64;
pub type FuncSymIntGetMax = extern "C" fn(*mut CSymbol) -> u64;
pub type FuncSymDirectDepsWithPrompts = extern "C" fn(*mut CSymbol) -> *mut CExpr;
pub type FuncSymPromptCount = extern "C" fn(*mut CSymbol) -> size_t;
pub type FuncConfWrite = extern "C" fn(*const c_char) -> c_int;
pub type FuncConfReadUnchecked = extern "C" fn(*const c_char) -> c_int;

#[derive(Debug)]
pub struct BridgeVTable {
    #[allow(dead_code)]
    library: Library,
    pub c_init: RawSymbol<FuncInit>,
    pub c_get_env: RawSymbol<FuncGetEnv>,
    pub c_symbol_count: RawSymbol<FuncSymbolCount>,
    pub c_get_all_symbols: RawSymbol<FuncGetAllSymbols>,
    pub c_get_choice_symbols: RawSymbol<FuncGetChoiceSymbols>,
    pub c_sym_set_tristate_value: RawSymbol<FuncSymSetTristateValue>,
    pub c_sym_set_string_value: RawSymbol<FuncSymSetStringValue>,
    pub c_sym_get_string_value: RawSymbol<FuncSymGetStringValue>,
    pub c_sym_calc_value: RawSymbol<FuncSymCalcValue>,
    pub c_sym_int_get_min: RawSymbol<FuncSymIntGetMin>,
    pub c_sym_int_get_max: RawSymbol<FuncSymIntGetMax>,
    pub c_sym_direct_deps_with_prompts: RawSymbol<FuncSymDirectDepsWithPrompts>,
    pub c_sym_prompt_count: RawSymbol<FuncSymPromptCount>,
    pub c_conf_write: RawSymbol<FuncConfWrite>,
    pub c_conf_read_unchecked: RawSymbol<FuncConfReadUnchecked>,
}

impl BridgeVTable {
    pub unsafe fn new(library_path: PathBuf) -> Result<BridgeVTable> {
        let library = Library::new(library_path)?;
        macro_rules! load_symbol {
            ($type: ty, $name: expr) => {
                (library.get($name)? as LSymbol<$type>).into_raw() as RawSymbol<$type>
            };
        }

        let c_init = load_symbol!(FuncInit, b"init");
        let c_get_env = load_symbol!(FuncGetEnv, b"autokernel_getenv");
        let c_symbol_count = load_symbol!(FuncSymbolCount, b"symbol_count");
        let c_get_all_symbols = load_symbol!(FuncGetAllSymbols, b"get_all_symbols");
        let c_get_choice_symbols = load_symbol!(FuncGetChoiceSymbols, b"get_choice_symbols");
        let c_sym_set_tristate_value = load_symbol!(FuncSymSetTristateValue, b"sym_set_tristate_value");
        let c_sym_set_string_value = load_symbol!(FuncSymSetStringValue, b"sym_set_string_value");
        let c_sym_get_string_value = load_symbol!(FuncSymGetStringValue, b"sym_get_string_value");
        let c_sym_calc_value = load_symbol!(FuncSymCalcValue, b"sym_calc_value");
        let c_sym_int_get_min = load_symbol!(FuncSymIntGetMin, b"sym_int_get_min");
        let c_sym_int_get_max = load_symbol!(FuncSymIntGetMin, b"sym_int_get_max");
        let c_sym_direct_deps_with_prompts =
            load_symbol!(FuncSymDirectDepsWithPrompts, b"sym_direct_deps_with_prompts");
        let c_sym_prompt_count = load_symbol!(FuncSymPromptCount, b"sym_prompt_count");
        let c_conf_write = load_symbol!(FuncConfWrite, b"conf_write");
        let c_conf_read_unchecked = load_symbol!(FuncConfReadUnchecked, b"conf_read");

        Ok(BridgeVTable {
            library,
            c_init,
            c_symbol_count,
            c_get_env,
            c_get_all_symbols,
            c_get_choice_symbols,
            c_sym_set_tristate_value,
            c_sym_set_string_value,
            c_sym_get_string_value,
            c_sym_calc_value,
            c_sym_int_get_min,
            c_sym_int_get_max,
            c_sym_direct_deps_with_prompts,
            c_sym_prompt_count,
            c_conf_write,
            c_conf_read_unchecked,
        })
    }

    /// needs to make static lifetime of the pointer explicit, otherwise it assumes CSymbol goes
    /// out of scope with the vtable reference that was used to call it
    pub fn get_all_symbols(&self) -> Vec<*mut CSymbol> {
        let count = (self.c_symbol_count)();
        let mut symbols = Vec::with_capacity(count);
        (self.c_get_all_symbols)(symbols.as_mut_ptr() as *mut *mut CSymbol);
        unsafe { symbols.set_len(count) };
        symbols
    }
}
