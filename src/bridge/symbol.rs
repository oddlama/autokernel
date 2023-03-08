use crate::bridge::satisfier;
use crate::bridge::satisfier::SolverConfig;

use super::expr::Expr;
use super::satisfier::SolveError;
use super::transaction::Transaction;
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

#[derive(Error, Debug, Clone)]
pub enum SymbolGetError {
    #[error("unknown symbol type")]
    UnknownType,

    #[error("cannot be parsed as an integer")]
    InvalidInt,
    #[error("cannot be parsed as a hex integer")]
    InvalidHex,
}

#[derive(Error, Debug, Clone)]
pub enum SymbolSetError {
    #[error("unknown symbol type")]
    UnknownType,
    #[error("is const")]
    IsConst,
    #[error("cannot be set directly, assign child instead")]
    IsChoice,

    #[error("cannot be parsed as an integer")]
    InvalidInt,
    #[error("cannot be parsed as a hex integer")]
    InvalidHex,
    #[error("valid tristates are: n, m, y")]
    InvalidTristate,
    #[error("valid booleans are: n, y")]
    InvalidBoolean,

    #[error("could not automatically solve symbol dependencies")]
    SatisfyFailed { error: SolveError },
    #[error("cannot set a higher value than {max}, the symbol has unmet dependencies")]
    UnmetDependencies {
        min: Tristate,
        max: Tristate,
        deps: Vec<String>,
        satisfying_configuration: Result<Vec<(String, Tristate)>, SolveError>,
    },
    #[error("cannot set a lower value than {min}, the symbol is required by other symbols")]
    RequiredByOther {
        min: Tristate,
        max: Tristate,
        rev_deps: Vec<String>,
    },
    #[error("this symbol cannot be set manually")]
    CannotSetManually,
    #[error("cannot set directly, instead satisfy any of the reverse dependencies")]
    MustBeSelected { rev_deps: Vec<String> },
    #[error("symbol's minimum visibility is higher than its maximum visibility [min={min}, max={max}]")]
    InvalidVisibility { min: Tristate, max: Tristate },
    #[error("module support is not enabled (try setting MODULES=y beforehand)")]
    ModulesNotEnabled,
    #[error("value must be in range [{min} ({min:#x}), {max} ({max:#x})]")]
    OutOfRange { min: u64, max: u64 },
    #[error("incompatible value type")]
    InvalidValue,
    #[error("value was rejected by kernel for an unknown reason")]
    AssignmentFailed,
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

    pub fn name_owned(&self) -> Option<String> {
        unsafe { (*self.c_symbol).name() }.map(|s| s.to_string())
    }

    pub fn recalculate(&self) {
        (self.bridge.vtable.c_sym_calc_value)(self.c_symbol);
    }

    pub fn set_value(&mut self, value: SymbolValue) -> Result<(), SymbolSetError> {
        ensure!(!self.is_const(), SymbolSetError::IsConst);
        ensure!(!self.is_choice(), SymbolSetError::IsChoice);
        ensure!(self.prompt_count() > 0, SymbolSetError::CannotSetManually);

        let set_tristate = |value: Tristate| -> Result<(), SymbolSetError> {
            let min = unsafe { (*self.c_symbol).reverse_dependencies.tri };
            let max = self.visible();
            if value > max {
                let deps = self
                    .visibility_expression_bare()
                    .unwrap()
                    .ok_or(SymbolSetError::MustBeSelected {
                        rev_deps: self
                            .reverse_dependencies()
                            .unwrap()
                            .or_clauses()
                            .into_iter()
                            .map(|x| x.display(self.bridge).to_string())
                            .collect_vec(),
                    })?
                    .and_clauses()
                    .into_iter()
                    .map(|x| x.display(self.bridge).to_string())
                    .collect_vec();

                let satisfying_configuration = self.satisfy(SolverConfig {
                    recursive: true,
                    desired_value: value,
                    ..SolverConfig::default()
                });
                return Err(SymbolSetError::UnmetDependencies {
                    min,
                    max,
                    deps,
                    satisfying_configuration,
                });
            }
            if value < min {
                return Err(SymbolSetError::RequiredByOther {
                    min,
                    max,
                    rev_deps: self
                        .reverse_dependencies()
                        .unwrap()
                        .or_clauses()
                        .into_iter()
                        .map(|x| x.display(self.bridge).to_string())
                        .collect_vec(),
                });
            }
            ensure!(max >= min, SymbolSetError::InvalidVisibility { min, max });
            ensure!(
                !(value == Tristate::Mod
                    && self.bridge.symbol("MODULES").unwrap().get_tristate_value() == Tristate::No),
                SymbolSetError::ModulesNotEnabled
            );
            ensure!(
                (self.bridge.vtable.c_sym_set_tristate_value)(self.c_symbol, value),
                SymbolSetError::AssignmentFailed
            );
            Ok(())
        };

        match (self.symbol_type(), value) {
            (SymbolType::Unknown, SymbolValue::Auto(_)) => return Err(SymbolSetError::UnknownType),
            (SymbolType::Boolean, SymbolValue::Auto(value)) => {
                // Allowed "y" "n"
                ensure!(matches!(value.as_str(), "y" | "n"), SymbolSetError::InvalidBoolean);
                self.set_value(SymbolValue::Boolean(
                    value.parse::<Tristate>().unwrap() == Tristate::Yes,
                ))?
            }
            (SymbolType::Tristate, SymbolValue::Auto(value)) => {
                // Allowed "y" "m" "n"
                let value = value.parse::<Tristate>().map_err(|_| SymbolSetError::InvalidTristate)?;
                self.set_value(SymbolValue::Tristate(value))?
            }
            (SymbolType::Int, SymbolValue::Auto(value)) => {
                // Allowed: Any u64 integer
                let value = value.parse::<u64>().map_err(|_| SymbolSetError::InvalidInt)?;
                self.set_value(SymbolValue::Int(value))?
            }
            (SymbolType::Hex, SymbolValue::Auto(value)) => {
                // Allowed: Any u64 integer
                ensure!(&value[..2] == "0x", SymbolSetError::InvalidHex);
                let value = u64::from_str_radix(&value[2..], 16).map_err(|_| SymbolSetError::InvalidHex)?;
                self.set_value(SymbolValue::Hex(value))?
            }
            (SymbolType::String, SymbolValue::Auto(value)) => self.set_value(SymbolValue::String(value))?,
            (SymbolType::Boolean | SymbolType::Tristate, SymbolValue::Boolean(value)) => set_tristate(value.into())?,
            (SymbolType::Boolean, SymbolValue::Tristate(value)) if value != Tristate::Mod => set_tristate(value)?,
            (SymbolType::Tristate, SymbolValue::Tristate(value)) => set_tristate(value)?,
            (SymbolType::Int, SymbolValue::Int(value)) => {
                let min = (self.bridge.vtable.c_sym_int_get_min)(self.c_symbol);
                let max = (self.bridge.vtable.c_sym_int_get_max)(self.c_symbol);
                ensure!(
                    (min == 0 && max == 0) || (value >= min && value <= max),
                    SymbolSetError::OutOfRange { min, max }
                );
                let cstr = CString::new(value.to_string()).unwrap();
                ensure!(
                    (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr()),
                    SymbolSetError::AssignmentFailed
                );
            }
            (SymbolType::Hex, SymbolValue::Hex(value)) => {
                let min = (self.bridge.vtable.c_sym_int_get_min)(self.c_symbol);
                let max = (self.bridge.vtable.c_sym_int_get_max)(self.c_symbol);
                ensure!(
                    (min == 0 && max == 0) || (value >= min && value <= max),
                    SymbolSetError::OutOfRange { min, max }
                );
                let cstr = CString::new(format!("{:#x}", value)).unwrap();
                ensure!(
                    (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr()),
                    SymbolSetError::AssignmentFailed
                );
            }
            (SymbolType::String, SymbolValue::String(value)) => {
                let cstr = CString::new(value).unwrap();
                ensure!(
                    (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr()),
                    SymbolSetError::AssignmentFailed
                );
            }
            (SymbolType::Int, SymbolValue::Number(value)) => return self.set_value(SymbolValue::Int(value)),
            (SymbolType::Hex, SymbolValue::Number(value)) => return self.set_value(SymbolValue::Hex(value)),
            (_, _) => return Err(SymbolSetError::InvalidValue),
        };

        self.bridge.recalculate_all_symbols();
        Ok(())
    }

    /// Sets the symbol parameters, tracking the transaction.
    /// parameters:
    /// - value: The symbol value
    /// - from: The location (file) it was set from
    /// - traceback: optional
    pub fn set_value_tracked(
        &mut self,
        value: SymbolValue,
        file: String,
        line: u32,
        traceback: Option<String>,
    ) -> Result<(), SymbolSetError> {
        let current_value = self.get_value().unwrap();
        let ret = self.set_value(value.clone());
        self.bridge.history.borrow_mut().push(Transaction {
            symbol: self.name().unwrap().to_string(),
            file,
            line,
            traceback,
            value,
            value_before: current_value,
            value_after: self.get_value().unwrap(),
            error: ret.clone().err(),
        });
        ret
    }

    pub fn get_value(&self) -> Result<SymbolValue, SymbolGetError> {
        match self.symbol_type() {
            SymbolType::Unknown => Err(SymbolGetError::UnknownType),
            SymbolType::Boolean => Ok(SymbolValue::Boolean(self.get_tristate_value() == Tristate::Yes)),
            SymbolType::Tristate => Ok(SymbolValue::Tristate(self.get_tristate_value())),
            SymbolType::Int => Ok(SymbolValue::Int(
                self.get_string_value()
                    .parse::<u64>()
                    .map_err(|_| SymbolGetError::InvalidInt)?,
            )),
            SymbolType::Hex => Ok(SymbolValue::Hex(
                u64::from_str_radix(&self.get_string_value()[2..], 16).map_err(|_| SymbolGetError::InvalidHex)?,
            )),
            SymbolType::String => Ok(SymbolValue::String(self.get_string_value())),
        }
    }

    pub fn symbol_type(&self) -> SymbolType {
        unsafe { &*self.c_symbol }.symbol_type()
    }

    pub fn flags(&self) -> SymbolFlags {
        unsafe { &*self.c_symbol }.flags
    }

    pub fn is_const(&self) -> bool {
        unsafe { &*self.c_symbol }.is_const()
    }

    pub fn is_choice(&self) -> bool {
        unsafe { &*self.c_symbol }.is_choice()
    }

    pub fn prompt_count(&self) -> usize {
        (self.bridge.vtable.c_sym_prompt_count)(self.c_symbol)
    }

    pub fn visible(&self) -> Tristate {
        self.recalculate();
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

    pub fn visibility_expression_bare(&self) -> Result<Option<Expr>, ExprConvertError> {
        unsafe { &mut *(self.bridge.vtable.c_sym_direct_deps_with_prompts)(self.c_symbol) }.expr()
    }

    pub fn visibility_expression(&self) -> Result<Expr, ExprConvertError> {
        Ok(self.visibility_expression_bare()?.unwrap_or(Expr::Const(true)))
    }

    pub fn reverse_dependencies_bare(&self) -> Result<Option<Expr>, ExprConvertError> {
        unsafe { &(*self.c_symbol).reverse_dependencies }.expr()
    }

    pub fn reverse_dependencies(&self) -> Result<Expr, ExprConvertError> {
        Ok(unsafe { &(*self.c_symbol).reverse_dependencies }
            .expr()?
            .unwrap_or(Expr::Const(false)))
    }

    pub fn get_string_value(&self) -> String {
        return unsafe { CStr::from_ptr((self.bridge.vtable.c_sym_get_string_value)(self.c_symbol)) }
            .to_str()
            .unwrap()
            .to_owned();
    }

    pub fn satisfy(&self, config: SolverConfig) -> Result<Vec<(String, Tristate)>, SolveError> {
        satisfier::satisfy(self.bridge, self.name_owned().ok_or(SolveError::InvalidSymbol)?, config)
    }

    pub fn satisfy_track_error(
        &mut self,
        value: SymbolValue,
        file: String,
        line: u32,
        traceback: Option<String>,
        config: SolverConfig,
    ) -> Result<Vec<(String, Tristate)>, SolveError> {
        let ret = self.satisfy(config);
        if ret.is_ok() {
            return ret;
        }

        let current_value = self.get_value().unwrap();
        self.bridge.history.borrow_mut().push(Transaction {
            symbol: self.name().unwrap().to_string(),
            file,
            line,
            traceback,
            value,
            value_before: current_value.clone(),
            value_after: current_value,
            error: Some(SymbolSetError::SatisfyFailed {
                error: ret.clone().unwrap_err(),
            }),
        });
        ret
    }
}

impl<'a> fmt::Display for Symbol<'a> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if let Some(name) = self.name() {
            let (name_color, value_indicator) = match self.get_value() {
                Ok(SymbolValue::Boolean(value)) => (
                    match value {
                        false => Color::Red,
                        true => Color::Green,
                    },
                    format!("={}", Tristate::from(value)),
                ),
                Ok(SymbolValue::Tristate(value)) => (value.color(), format!("={}", value)),
                Ok(SymbolValue::Int(value)) => (Color::White, format!("={}", value)),
                Ok(SymbolValue::Hex(value)) => (Color::White, format!("={:x}", value)),
                Ok(SymbolValue::String(value)) => (Color::White, format!("=\"{}\"", value)),
                _ => (Color::Blue, "".into()),
            };
            write!(f, "{}{}", name.color(name_color), value_indicator.dimmed())
        } else if self.is_choice() {
            let choices = self.choices().unwrap().into_iter().map(|s| self.bridge.wrap_symbol(s));
            write!(f, "<choice>[{}]", choices.format(", "))
        } else {
            write!(f, "<??>")
        }
    }
}
