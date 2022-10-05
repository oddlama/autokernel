use libc::{c_char, c_int, c_void};
use std::ffi::CStr;
use std::borrow::Cow;
use std::fmt;
use std::str::FromStr;

#[derive(Debug, Eq, PartialEq, Ord, PartialOrd, Clone, Copy)]
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

#[derive(Debug)]
pub enum SymbolValue {
    Boolean(bool),
    Tristate(Tristate),
    Int(u64),
    Hex(u64),
    Number(u64),
    String(String),
}

#[derive(Debug)]
pub enum Expr {
    Or(Box<Expr>, Box<Expr>),
    And(Box<Expr>, Box<Expr>),
    Not(Box<Expr>),
    Eq(*mut CSymbol, *mut CSymbol),
    Neq(*mut CSymbol, *mut CSymbol),
    Lth(*mut CSymbol, *mut CSymbol),
    Leq(*mut CSymbol, *mut CSymbol),
    Gth(*mut CSymbol, *mut CSymbol),
    Geq(*mut CSymbol, *mut CSymbol),
    List(Vec<Expr>),
    Symbol(*mut CSymbol),
    Range(u64, u64),
    Const(SymbolValue),
}

impl fmt::Display for Expr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let symstr = |symbol: *mut CSymbol| {
            if symbol.is_null() {
                None
            } else {
                unsafe {
                    (*symbol)
                        .name
                        .as_ref()
                        .map(|obj| String::from_utf8_lossy(CStr::from_ptr(obj).to_bytes()))
                }
            }.unwrap_or(Cow::from("<choice>"))
        };

        match self {
            Expr::Or(l, r) => write!(f, "({l} || {r})"),
            Expr::And(l, r) => write!(f, "({l} && {r})"),
            Expr::Not(e) => write!(f, "!{e}"),
            Expr::Eq(l, r) => write!(f, "{} == {}", symstr(*l), symstr(*r)),
            Expr::Neq(l, r) => write!(f, "{} != {}", symstr(*l), symstr(*r)),
            Expr::Lth(l, r) => write!(f, "{} < {}", symstr(*l), symstr(*r)),
            Expr::Leq(l, r) => write!(f, "{} <= {}", symstr(*l), symstr(*r)),
            Expr::Gth(l, r) => write!(f, "{} > {}", symstr(*l), symstr(*r)),
            Expr::Geq(l, r) => write!(f, "{} >= {}", symstr(*l), symstr(*r)),
            Expr::List(e) => todo!(),
            Expr::Symbol(e) => write!(f, "{}", symstr(*e)),
            Expr::Range(l, r) => write!(f, "[{l}, {r}]"),
            Expr::Const(e) => write!(f, "Const({:?})", e),
        }
    }
}

fn convert_expression(expression: *mut CExpr) -> Result<Option<Expr>, ()> {
    macro_rules! expr {
        ($which: ident) => {
            if expression.is_null() {
                return Err(())
            } else {
                Box::new(convert_expression(unsafe { (*expression).$which.expression })?.unwrap())
            }
        };
    }

    macro_rules! sym {
        ($which: ident) => {
            if expression.is_null() {
                return Err(())
            } else {
                unsafe { (*expression).$which.symbol }
            }
        };
    }

    if expression.is_null() {
        return Ok(None);
    }

    Ok(Some(match unsafe { (*expression).expr_type } {
        CExprType::None => return Err(()),
        CExprType::Or => Expr::Or(expr!(left), expr!(right)),
        CExprType::And => Expr::And(expr!(left), expr!(right)),
        CExprType::Not => Expr::Not(expr!(left)),
        CExprType::Equal => Expr::Eq(sym!(left), sym!(right)),
        CExprType::Unequal => Expr::Neq(sym!(left), sym!(right)),
        CExprType::Lth => Expr::Lth(sym!(left), sym!(right)),
        CExprType::Leq => Expr::Leq(sym!(left), sym!(right)),
        CExprType::Gth => Expr::Gth(sym!(left), sym!(right)),
        CExprType::Geq => Expr::Geq(sym!(left), sym!(right)),
        CExprType::List => todo!(),
        CExprType::Symbol => Expr::Symbol(sym!(left)),
        CExprType::Range => todo!(),
    }))
}

#[derive(Debug, PartialEq, Eq, Clone, Copy)]
#[repr(C)]
#[allow(dead_code)]
pub enum CExprType {
    None,
    Or,
    And,
    Not,
    Equal,
    Unequal,
    Lth,
    Leq,
    Gth,
    Geq,
    List,
    Symbol,
    Range,
}

#[repr(C)]
pub union CExprData {
    expression: *mut CExpr,
    symbol: *mut CSymbol,
}

#[repr(C)]
struct CExpr {
    expr_type: CExprType,
    left: CExprData,
    right: CExprData,
}

#[repr(C)]
pub struct CExprValue {
    expression: *mut CExpr,
    pub tri: Tristate,
}

impl CExprValue {
    pub fn expr(&self) -> Result<Option<Expr>, ()> {
        convert_expression(self.expression)
    }
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
    property: *mut CProperty,
    pub(super) direct_dependencies: CExprValue,
    pub(super) reverse_dependencies: CExprValue,
    pub(super) implied: CExprValue,
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
