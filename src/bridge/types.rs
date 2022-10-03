use std::str::FromStr;
use libc::{c_char, c_int, c_void};

#[derive(Debug, Eq, PartialEq, Ord, PartialOrd)]
#[repr(u8)]
#[allow(dead_code)]
pub enum Tristate {
    No,
    Mod,
    Yes,
}

impl From<bool> for Tristate {
    fn from(value: bool) -> Self {
        if value {
            Tristate::Yes
        } else {
            Tristate::No
        }
    }
}

impl FromStr for Tristate {
    type Err = ();
    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value {
            "n" => Ok(Tristate::No),
            "m" => Ok(Tristate::Mod),
            "y" => Ok(Tristate::Yes),
            _ => Err(()),
        }
    }
}

#[derive(Debug, PartialEq, Eq, Clone, Copy)]
#[repr(C)]
#[allow(dead_code)]
pub enum SymbolType {
    Unknown,
    Boolean,
    Tristate,
    Int,
    Hex,
    String,
}

#[derive(Debug)]
#[repr(C)]
#[allow(dead_code)]
enum PropertyType {
    Unknown,
    Prompt,  /* prompt "foo prompt" or "BAZ Value" */
    Comment, /* text associated with a comment */
    Menu,    /* prompt associated with a menu or menuconfig symbol */
    Default, /* default y */
    Choice,  /* choice value */
    Select,  /* select BAR */
    Imply,   /* imply BAR */
    Range,   /* range 7..100 (for a symbol) */
    Symbol,  /* where a symbol is defined */
}

#[repr(C)]
#[allow(dead_code)]
struct CProperty {
    next: *mut CProperty,
    prop_type: PropertyType,
    text: *const c_char,
    visible: CExprValue,
    expr: *mut c_void,
    menu: *mut c_void,
    file: *mut c_void,
    lineno: c_int,
}

#[repr(C)]
pub struct CSymbolValue {
    value: *mut SymbolType,
    pub tri: Tristate,
}

pub enum SymbolValue {
    Auto(String),
    Boolean(bool),
    Tristate(Tristate),
    Int(u64),
    Hex(u64),
    Number(u64),
    String(String),
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
    pub current_value: CSymbolValue,
    default_values: [CSymbolValue; 4],
    pub visible: Tristate,
    pub flags: SymbolFlags,
    // TODO where (which type) is this pointing to?
    properties: *mut CProperty,
    direct_dependencies: CExprValue,
    reverse_dependencies: CExprValue,
    implied: CExprValue,
}

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
