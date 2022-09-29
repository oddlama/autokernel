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
    pub flags: SymbolFlags,
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
    pub struct SymbolFlags: u32 {
        // WARNING might change in kernel and while unlikely should be checked
        const CONST     = 0x0001;
        const CHECK     = 0x0008;
        const CHOICE    = 0x0010;
        const CHOICEVAL = 0x0020;
        const VALID     = 0x0080;
        const OPTIONAL  = 0x0100;
        const WRITE     = 0x0200;
        const CHANGED   = 0x0400;
        const WRITTEN   = 0x0800;
        const NOWRITE   = 0x1000;
        const CHECKED   = 0x2000;
        const WARNED    = 0x8000;
    }
}
