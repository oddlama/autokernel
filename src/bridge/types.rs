use super::*;
use libc::{c_char, c_void};

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
    pub flags: Flags,
    // TODO where (which type) is this pointing to?
    properties: *mut c_void,
    direct_dependencies: CExprValue,
    reverse_dependencies: CExprValue,
    implied: CExprValue,
}

// TODO handle better (and elsewhere)
use bitflags::bitflags;

bitflags! {
    #[repr(C)]
    pub struct Flags: u32 {
        // WARNING might change in kernel and while unlikely should be checked
        const SYMBOL_CONST     = 0x0001;/* symbol is const */
        const SYMBOL_CHECK     = 0x0008;/* used during dependency checking */
        const SYMBOL_CHOICE    = 0x0010;/* start of a choice block (null name) */
        const SYMBOL_CHOICEVAL = 0x0020;/* used as a value in a choice block */
        const SYMBOL_VALID     = 0x0080;/* set when symbol.curr is calculated */
        const SYMBOL_OPTIONAL  = 0x0100;/* choice is optional - values can be 'n' */
        const SYMBOL_WRITE     = 0x0200;/* write symbol to file (KCONFIG_CONFIG) */
        const SYMBOL_CHANGED   = 0x0400;/* ? */
        const SYMBOL_WRITTEN   = 0x0800;/* track info to avoid double-write to .config */
        const SYMBOL_NO_WRITE  = 0x1000;/* Symbol for internal use only; it will not be written */
        const SYMBOL_CHECKED   = 0x2000;/* used during dependency checking */
        const SYMBOL_WARNED    = 0x8000;/* warning has been issued */
    }
}
