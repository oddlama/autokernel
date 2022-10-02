use super::types::*;
use super::Bridge;
use anyhow::Context;
use anyhow::{ensure, Result};
use std::borrow::Cow;
use std::ffi::{CStr, CString};

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

pub struct Symbol<'a> {
    pub(super) c_symbol: *mut CSymbol,
    pub(super) bridge: &'a Bridge,
}

pub enum SymbolValue {
    Auto(String),
    Boolean(bool),
    Tristate(Tristate),
    Int(i64),
    Hex(i64),
    String(String),
    Choice(String),
}

impl<'a> Symbol<'a> {
    pub fn name(&self) -> Option<Cow<'_, str>> {
        unsafe {
            (*self.c_symbol)
                .name
                .as_ref()
                .map(|obj| String::from_utf8_lossy(CStr::from_ptr(obj).to_bytes()))
        }
    }

    pub fn recalculate(&self) {
        (self.bridge.vtable.c_sym_calc_value)(self.c_symbol);
    }

    pub fn get_value(&self) -> &Tristate {
        unsafe { &(*self.c_symbol).current_value.tri }
    }

    pub fn set_symbol_value(&mut self, value: SymbolValue) -> Result<()> {
        match value {
            SymbolValue::Auto(value) => todo!(),
            SymbolValue::Boolean(value) => {
                ensure!(
                    (self.bridge.vtable.c_sym_set_tristate_value)(self.c_symbol, value.into()) == 1,
                    format!("Could not set symbol {:?}", self.name())
                )
            }
            SymbolValue::Tristate(value) => todo!(),
            SymbolValue::Int(value) => todo!(),
            SymbolValue::Hex(value) => todo!(),
            SymbolValue::String(value) => {
                let cstr = CString::new(value)?;
                ensure!(
                    (self.bridge.vtable.c_sym_set_string_value)(self.c_symbol, cstr.as_ptr()) == 1,
                    format!("Could not set symbol {:?}", self.name())
                )
            }
            SymbolValue::Choice(value) => {
                // TODO check that the given symbol belongs to the choice.
                self.bridge
                    .symbol(&value)
                    .context("No such symbol")?
                    .set_symbol_value(SymbolValue::Tristate(Tristate::Yes))?;
            }
        }

        // TODO check if change was successful
        self.bridge.recalculate_all_symbols();
        Ok(())
    }

    pub fn is_choice(&self) -> bool {
        unsafe { &*self.c_symbol }.flags.intersects(SymbolFlags::CHOICE)
    }
}
