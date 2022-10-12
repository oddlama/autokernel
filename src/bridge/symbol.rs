use super::expr::Expr;
use super::types::*;
use super::Bridge;
use colored::{Color, Colorize};
use itertools::Itertools;
use std::borrow::Cow;
use std::ffi::{CStr, CString};
use std::fmt;
use thiserror::Error;

macro_rules! ensure {
    ($condition: expr, $error: expr) => {
        if !$condition {
            return Err($error);
        }
    };
}

#[derive(Error, Debug)]
pub enum SymbolSetAutoError<'a> {
    #[error(transparent)]
    SymbolSetError(SymbolSetError<'a>),
    #[error("{symbol} cannot be set to {value:?}: Cannot be parsed as an integer")]
    InvalidInt { symbol: Symbol<'a>, value: &'a str },
    #[error("{symbol} cannot be set to {value:?}: Cannot be parsed as a hex integer")]
    InvalidHex { symbol: Symbol<'a>, value: &'a str },
    #[error("{symbol} cannot be set to {value}: Valid tristates are 'n', 'm', 'y'")]
    InvalidTristate { symbol: Symbol<'a>, value: &'a str },
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

impl<'a> From<SymbolSetError<'a>> for SymbolSetAutoError<'a> {
    fn from(err: SymbolSetError<'a>) -> SymbolSetAutoError<'a> {
        SymbolSetAutoError::SymbolSetError(err)
    }
}

#[derive(Error, Debug)]
pub enum SymbolSetError<'a> {
    #[error("{0} has unknown symbol type")]
    UnknownType(Symbol<'a>),
    #[error("{0} is const")]
    IsConst(Symbol<'a>),
    #[error("{0} cannot be set directly, assign child instead")]
    IsChoice(Symbol<'a>),
    #[error("{0} cannot be set to {1}: TODO visibility (upper bound) is {}. TODO {}",
        symbol.visible(),
        symbol.reverse_dependencies().unwrap().unwrap_or(Expr::Const(true)).display(symbol.bridge)
    )]
    VisibilityTooLow { symbol: Symbol<'a>, value: Tristate },
    #[error("TODO")]
    RequiredByOther { symbol: Symbol<'a>, value: Tristate },
    #[error("TODO")]
    InvalidVisibility { symbol: Symbol<'a>, value: Tristate },
    #[error("{symbol} cannot be set to {value}: module support is not enabled (set MODULES to y)")]
    ModulesNotEnabled { symbol: Symbol<'a>, value: Tristate },
    #[error("{symbol} cannot be set to {value}: value must be in range [{min:#x}, {max:#x}]")]
    OutOfRangeHex {
        symbol: Symbol<'a>,
        value: u64,
        min: u64,
        max: u64,
    },
    #[error("{symbol} cannot be set to {value}: value must be in range [{min}, {max}]")]
    OutOfRangeInt {
        symbol: Symbol<'a>,
        value: u64,
        min: u64,
        max: u64,
    },
    #[error("{symbol} cannot be set to {value:?}: incompatible value type")]
    InvalidValue { symbol: Symbol<'a>, value: SymbolValue },
    #[error("{symbol} cannot be set to {value:?}: value was rejected by kernel")]
    AssignmentFailed { symbol: Symbol<'a>, value: SymbolValue },
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

#[derive(Clone, Copy, Debug)]
pub struct Symbol<'a> {
    pub(super) c_symbol: *mut CSymbol,
    pub bridge: &'a Bridge,
}

impl<'a> Symbol<'a> {
    pub fn name(&self) -> Option<Cow<'_, str>> {
        unsafe { (*self.c_symbol).name() }
    }

    pub fn recalculate(&self) {
        (self.bridge.vtable.c_sym_calc_value)(self.c_symbol);
    }

    pub fn set_symbol_value_auto(&mut self, value: &str) -> Result<(), SymbolSetAutoError> {
        match self.symbol_type() {
            SymbolType::Unknown => return Err(SymbolSetAutoError::SymbolSetError(SymbolSetError::UnknownType(*self))),
            SymbolType::Boolean => {
                // Allowed "y" "n"
                ensure!(
                    matches!(value, "y" | "n"),
                    SymbolSetAutoError::Other(anyhow::anyhow!("TODO"))
                );
                self.set_symbol_value(SymbolValue::Boolean(
                    value.parse::<Tristate>().unwrap() == Tristate::Yes,
                ))
            }
            SymbolType::Tristate => {
                // Allowed "y" "m" "n"
                let value = value
                    .parse::<Tristate>()
                    .map_err(|_| SymbolSetAutoError::InvalidTristate { symbol: *self, value })?;
                self.set_symbol_value(SymbolValue::Tristate(value))
            }
            SymbolType::Int => {
                // Allowed: Any u64 integer
                let value = value
                    .parse::<u64>()
                    .map_err(|_| SymbolSetAutoError::InvalidInt { symbol: *self, value })?;
                self.set_symbol_value(SymbolValue::Int(value))
            }
            SymbolType::Hex => {
                // Allowed: Any u64 integer
                ensure!(
                    &value[..2] == "0x",
                    SymbolSetAutoError::InvalidHex { symbol: *self, value }
                );
                let value = u64::from_str_radix(&value[2..], 16)
                    .map_err(|_| SymbolSetAutoError::InvalidHex { symbol: *self, value })?;
                self.set_symbol_value(SymbolValue::Hex(value))
            }
            SymbolType::String => self.set_symbol_value(SymbolValue::String(value.to_owned())),
        }
        .map_err(SymbolSetAutoError::SymbolSetError)
    }

    pub fn set_symbol_value(&mut self, value: SymbolValue) -> Result<(), SymbolSetError> {
        // TODO track which symbols were assigned to report conflicting later assignments.
        // TODO for choices there is no symbol name. track whether other choices were set and if
        //      they are overwritten. Tracking must have a disable switch to load external kconfig
        //      (defconfig) for example. Or a function that resets tracking state for one/all symbols.
        ensure!(!self.is_const(), SymbolSetError::IsConst(*self));
        ensure!(!self.is_choice(), SymbolSetError::IsChoice(*self));

        let set_tristate = |value: Tristate| -> Result<bool, SymbolSetError> {
            let rev_dep_tri = unsafe { (*self.c_symbol).reverse_dependencies.tri };
            ensure!(
                value <= self.visible(),
                SymbolSetError::VisibilityTooLow { symbol: *self, value }
            );
            ensure!(
                value >= rev_dep_tri,
                SymbolSetError::RequiredByOther { symbol: *self, value }
            );
            ensure!(
                self.visible() > rev_dep_tri,
                SymbolSetError::InvalidVisibility { symbol: *self, value }
            );
            ensure!(
                !(value == Tristate::Mod
                    && self.bridge.symbol("MODULES").unwrap().get_tristate_value() == Tristate::No),
                SymbolSetError::ModulesNotEnabled { symbol: *self, value }
            );
            Ok((self.bridge.vtable.c_sym_set_tristate_value)(self.c_symbol, value))
        };

        let ret = match (self.symbol_type(), value) {
            (SymbolType::Boolean | SymbolType::Tristate, SymbolValue::Boolean(value)) => set_tristate(value.into())?,
            (SymbolType::Boolean, SymbolValue::Tristate(value)) if value != Tristate::Mod => set_tristate(value)?,
            (SymbolType::Tristate, SymbolValue::Tristate(value)) => set_tristate(value)?,
            (SymbolType::Int, SymbolValue::Int(value)) => {
                let min = (self.bridge.vtable.c_sym_int_get_min)(self.c_symbol);
                let max = (self.bridge.vtable.c_sym_int_get_max)(self.c_symbol);
                ensure!(
                    value >= min && value <= max,
                    SymbolSetError::OutOfRangeInt {
                        symbol: *self,
                        value,
                        min,
                        max
                    }
                );
                let cstr = CString::new(value.to_string()).unwrap();
                (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr())
            }
            (SymbolType::Hex, SymbolValue::Hex(value)) => {
                let min = (self.bridge.vtable.c_sym_int_get_min)(self.c_symbol);
                let max = (self.bridge.vtable.c_sym_int_get_max)(self.c_symbol);
                ensure!(
                    value >= min && value <= max,
                    SymbolSetError::OutOfRangeHex {
                        symbol: *self,
                        value,
                        min,
                        max
                    }
                );
                let cstr = CString::new(format!("{:#x}", value)).unwrap();
                (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr())
            }
            (SymbolType::String, SymbolValue::String(value)) => {
                let cstr = CString::new(value).unwrap();
                (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr())
            }
            (SymbolType::Int, SymbolValue::Number(value)) => return self.set_symbol_value(SymbolValue::Int(value)),
            (SymbolType::Hex, SymbolValue::Number(value)) => return self.set_symbol_value(SymbolValue::Hex(value)),
            (st, v) => return Err(SymbolSetError::InvalidValue { symbol: *self, value }),
        };

        ensure!(ret, SymbolSetError::AssignmentFailed { symbol: *self, value });

        // TODO only recalculate the current symbol except when this was a choice?
        // not sure, check C code. Probably we need to go through all deps and recalculate those
        //self.recalculate();
        self.bridge.recalculate_all_symbols();

        Ok(())
    }

    pub fn symbol_type(&self) -> SymbolType {
        unsafe { &*self.c_symbol }.symbol_type
    }

    pub fn is_const(&self) -> bool {
        unsafe { &*self.c_symbol }.flags.intersects(SymbolFlags::CONST)
    }

    pub fn is_choice(&self) -> bool {
        unsafe { &*self.c_symbol }.flags.intersects(SymbolFlags::CHOICE)
    }

    pub fn visible(&self) -> Tristate {
        unsafe { &*self.c_symbol }.visible
    }

    pub fn choices(&self) -> anyhow::Result<Vec<*mut CSymbol>> {
        anyhow::ensure!(
            self.is_choice(),
            "The symbol must be a choice symbol to call .choices()"
        );
        let count = (self.bridge.vtable.c_get_choice_symbols)(self.c_symbol, std::ptr::null_mut() as *mut *mut CSymbol);
        let mut symbols = Vec::with_capacity(count);
        (self.bridge.vtable.c_get_choice_symbols)(self.c_symbol, symbols.as_mut_ptr() as *mut *mut CSymbol);
        unsafe { symbols.set_len(count) };
        Ok(symbols)
    }

    pub fn get_tristate_value(&self) -> Tristate {
        unsafe { &*self.c_symbol }.get_tristate_value()
    }

    pub fn visibility_expression(&self) -> Result<Option<Expr>, ()> {
        todo!("Ughh..")
    }

    pub fn direct_dependencies(&self) -> Result<Option<Expr>, ()> {
        unsafe { &(*self.c_symbol).direct_dependencies }.expr()
        // TODO directly assign proper default here. .unwrap_or(Expr::Const(false))
    }

    pub fn reverse_dependencies(&self) -> Result<Option<Expr>, ()> {
        unsafe { &(*self.c_symbol).reverse_dependencies }.expr()
    }

    pub fn get_string_value(&self) -> String {
        return unsafe { CStr::from_ptr((self.bridge.vtable.c_sym_get_string_value)(self.c_symbol)) }
            .to_str()
            .unwrap()
            .to_owned();
    }
}

impl<'a> fmt::Display for Symbol<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(name) = self.name() {
            let color = match self.get_tristate_value() {
                Tristate::No => Color::Red,
                Tristate::Mod => Color::Yellow,
                Tristate::Yes => Color::Green,
            };
            write!(f, "{}={}", name.color(color), self.get_tristate_value())
        } else {
            if self.is_choice() {
                let choices = self.choices().unwrap().into_iter().map(|s| self.bridge.wrap_symbol(s));
                write!(f, "<choice>[{}]", choices.format(", "))
            } else {
                write!(f, "?")
            }
        }
    }
}
